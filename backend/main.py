"""
VerifyFlow – FastAPI application entry point.

Endpoints:
    POST /upload              – upload document, start background job
    GET  /status/{job_id}     – current job status + agent states
    GET  /result/{job_id}     – final analysis result
    GET  /stream/{job_id}     – Server-Sent Events (live agent updates)
    GET  /health              – health check
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict

import aiofiles
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from models import AgentStatus, JobState, JobStatus

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".tif"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/tiff",
}

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ── In-memory job store ──────────────────────────────────────────────────────
jobs: Dict[str, JobState] = {}

# Per-job asyncio Events used to signal SSE subscribers
_job_events: Dict[str, asyncio.Event] = {}

# ── FastAPI app ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="VerifyFlow API",
    description="Document fraud detection powered by AI agents",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_job_or_404(job_id: str) -> JobState:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return job


def _signal_job_update(job_id: str) -> None:
    """Wake any SSE consumers waiting on this job."""
    event = _job_events.get(job_id)
    if event:
        event.set()
        event.clear()


def _init_agents(job: JobState) -> None:
    """Pre-populate agent statuses so the front-end can show them immediately."""
    agent_names = ["ocr", "ner", "web_checker", "anomaly_scorer", "vision", "aggregator"]
    for name in agent_names:
        job.agents[name] = AgentStatus(name=name, status="pending")


def _apply_agent_updates(job: JobState, updates: list) -> None:
    """Merge agent_updates list from graph state into the job's agent dict."""
    for update in updates:
        agent_name: str = update.get("agent", "")
        status: str = update.get("status", "")
        message: str = update.get("message", "")
        ts_str: str = update.get("timestamp", "")

        if not agent_name:
            continue

        ts = None
        try:
            ts = datetime.fromisoformat(ts_str) if ts_str else None
        except ValueError:
            pass

        existing = job.agents.get(agent_name, AgentStatus(name=agent_name))
        existing.status = status
        existing.message = message

        if status == "running" and ts:
            existing.started_at = ts
        elif status in ("done", "error") and ts:
            existing.completed_at = ts

        job.agents[agent_name] = existing


# ── Background processing ─────────────────────────────────────────────────────

async def _process_job(job_id: str) -> None:
    """Main background task: runs the LangGraph pipeline for a job."""
    from graph import run_pipeline

    job = jobs.get(job_id)
    if not job:
        logger.error("Background task: job %s not found", job_id)
        return

    job.status = JobStatus.PROCESSING
    _signal_job_update(job_id)

    initial_state: Dict[str, Any] = {
        "job_id": job_id,
        "file_path": job.file_path,
        "filename": job.filename,
        "agent_updates": [],
    }

    try:
        final_state = await run_pipeline(initial_state)

        # Apply agent status updates collected during the run
        _apply_agent_updates(job, final_state.get("agent_updates", []))

        raw_result = final_state.get("final_result")
        if raw_result:
            from models import JobResult

            job.result = JobResult(**raw_result)
        else:
            raise RuntimeError("Pipeline produced no final_result")

        job.status = JobStatus.COMPLETED
        logger.info("Job %s completed – verdict=%s", job_id, job.result.verdict)

    except Exception as exc:
        logger.exception("Job %s failed: %s", job_id, exc)
        job.status = JobStatus.FAILED
        job.error = str(exc)

    finally:
        _signal_job_update(job_id)
        # Clean up uploaded file
        try:
            if job.file_path and os.path.exists(job.file_path):
                os.remove(job.file_path)
                logger.info("Cleaned up file %s", job.file_path)
        except Exception as cleanup_err:
            logger.warning("Failed to clean up file: %s", cleanup_err)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Utility"])
async def health_check() -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "VerifyFlow API"})


@app.post("/upload", tags=["Jobs"])
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> JSONResponse:
    """Accept a document, validate it, persist it, and queue background analysis."""

    # Validate content type
    content_type = file.content_type or ""
    ext = Path(file.filename or "").suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Read file content & validate size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE_MB} MB.",
        )
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Persist file
    job_id = str(uuid.uuid4())
    safe_filename = f"{job_id}{ext}"
    dest_path = UPLOAD_DIR / safe_filename

    async with aiofiles.open(dest_path, "wb") as f:
        await f.write(content)

    # Create job record
    job = JobState(
        job_id=job_id,
        filename=file.filename or safe_filename,
        file_path=str(dest_path),
        status=JobStatus.PENDING,
    )
    _init_agents(job)
    jobs[job_id] = job
    _job_events[job_id] = asyncio.Event()

    # Queue background processing
    background_tasks.add_task(_process_job, job_id)

    logger.info("Job %s created for file '%s'", job_id, file.filename)
    return JSONResponse(
        status_code=202,
        content={
            "job_id": job_id,
            "status": job.status.value,
            "filename": job.filename,
            "message": "Document received. Analysis started.",
        },
    )


@app.get("/status/{job_id}", tags=["Jobs"])
async def get_job_status(job_id: str) -> JSONResponse:
    """Return the current job status and per-agent progress."""
    job = _get_job_or_404(job_id)

    agents_payload = {
        name: {
            "name": agent.name,
            "status": agent.status,
            "message": agent.message,
            "started_at": agent.started_at.isoformat() if agent.started_at else None,
            "completed_at": agent.completed_at.isoformat() if agent.completed_at else None,
        }
        for name, agent in job.agents.items()
    }

    return JSONResponse(
        {
            "job_id": job.job_id,
            "status": job.status.value,
            "filename": job.filename,
            "created_at": job.created_at.isoformat(),
            "agents": agents_payload,
            "error": job.error,
        }
    )


@app.get("/result/{job_id}", tags=["Jobs"])
async def get_job_result(job_id: str) -> JSONResponse:
    """Return the final analysis result for a completed job."""
    job = _get_job_or_404(job_id)

    if job.status == JobStatus.FAILED:
        raise HTTPException(
            status_code=500,
            detail=f"Job failed: {job.error or 'Unknown error'}",
        )

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=202,
            detail=f"Job is still {job.status.value}. Poll /status/{job_id} for updates.",
        )

    if not job.result:
        raise HTTPException(status_code=500, detail="Job completed but result is missing")

    return JSONResponse(job.result.model_dump(mode="json"))


@app.get("/stream/{job_id}", tags=["Jobs"])
async def stream_job_updates(job_id: str) -> StreamingResponse:
    """Server-Sent Events stream that pushes live agent updates."""
    job = _get_job_or_404(job_id)

    async def event_generator() -> AsyncGenerator[str, None]:
        # Send initial snapshot
        yield _sse_event("status", _job_snapshot(job))

        # If job is already terminal, send result and close
        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            yield _sse_event("complete", _job_snapshot(job))
            return

        event = _job_events.get(job_id, asyncio.Event())
        while True:
            try:
                await asyncio.wait_for(asyncio.shield(event.wait()), timeout=25.0)
            except asyncio.TimeoutError:
                # Send heartbeat to keep connection alive
                yield ": heartbeat\n\n"
                continue

            # Re-fetch fresh job state
            current_job = jobs.get(job_id)
            if not current_job:
                yield _sse_event("error", {"message": "Job not found"})
                break

            yield _sse_event("status", _job_snapshot(current_job))

            if current_job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                yield _sse_event("complete", _job_snapshot(current_job))
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── SSE helpers ───────────────────────────────────────────────────────────────

def _sse_event(event_type: str, data: Any) -> str:
    payload = json.dumps(data, default=str)
    return f"event: {event_type}\ndata: {payload}\n\n"


def _job_snapshot(job: JobState) -> Dict[str, Any]:
    agents_payload = {
        name: {
            "name": agent.name,
            "status": agent.status,
            "message": agent.message,
            "started_at": agent.started_at.isoformat() if agent.started_at else None,
            "completed_at": agent.completed_at.isoformat() if agent.completed_at else None,
        }
        for name, agent in job.agents.items()
    }
    snapshot: Dict[str, Any] = {
        "job_id": job.job_id,
        "status": job.status.value,
        "filename": job.filename,
        "agents": agents_payload,
        "error": job.error,
    }
    if job.result:
        snapshot["result"] = job.result.model_dump(mode="json")
    return snapshot


# ── Dev server entrypoint ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
