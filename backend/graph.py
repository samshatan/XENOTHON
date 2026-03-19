"""
LangGraph workflow for VerifyFlow document fraud detection.

Pipeline:
    ocr_node → ner_node → web_checker_node
                       → anomaly_node
    (both web_checker and anomaly run after NER, then)
    → vision_node → aggregate_node

Trust score composition:
    OCR confidence   20 %
    NER completeness 10 %
    Web checker      25 %
    Anomaly (inv.)   25 %
    Vision           20 %

Verdict:
    75-100  AUTHENTIC
    40-74   SUSPICIOUS
    0-39    FRAUDULENT
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, TypedDict

from langgraph.graph import END, StateGraph

from agents.anomaly_scorer import run_anomaly_scorer
from agents.ner_agent import run_ner_agent
from agents.ocr_agent import run_ocr_agent
from agents.vision_agent import run_vision_agent
from agents.web_checker_agent import run_web_checker_agent
from models import JobResult, RedFlag

logger = logging.getLogger(__name__)


# ── State schema ────────────────────────────────────────────────────────────

class GraphState(TypedDict, total=False):
    job_id: str
    file_path: str
    filename: str
    ocr_results: Dict[str, Any]
    ner_results: Dict[str, Any]
    web_checker_results: Dict[str, Any]
    anomaly_results: Dict[str, Any]
    vision_results: Dict[str, Any]
    final_result: Dict[str, Any]
    agent_updates: List[Dict[str, Any]]  # status events emitted during run


# ── Helper: emit agent update ───────────────────────────────────────────────

def _emit(state: dict, agent: str, status: str, message: str = "") -> None:
    updates: List[Dict[str, Any]] = state.setdefault("agent_updates", [])
    updates.append(
        {
            "agent": agent,
            "status": status,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


# ── Node wrappers ────────────────────────────────────────────────────────────

async def ocr_node(state: dict) -> dict:
    _emit(state, "ocr", "running", "Extracting text from document")
    try:
        state = await run_ocr_agent(state)
        wc = state.get("ocr_results", {}).get("word_count", 0)
        _emit(state, "ocr", "done", f"Extracted {wc} words")
    except Exception as exc:
        logger.exception("ocr_node failed: %s", exc)
        _emit(state, "ocr", "error", str(exc))
        state.setdefault("ocr_results", {})["error"] = str(exc)
    return state


async def ner_node(state: dict) -> dict:
    _emit(state, "ner", "running", "Extracting named entities")
    try:
        state = await run_ner_agent(state)
        orgs = len(state.get("ner_results", {}).get("organisations", []))
        _emit(state, "ner", "done", f"Found {orgs} organisations")
    except Exception as exc:
        logger.exception("ner_node failed: %s", exc)
        _emit(state, "ner", "error", str(exc))
        state.setdefault("ner_results", {})["error"] = str(exc)
    return state


async def web_checker_node(state: dict) -> dict:
    _emit(state, "web_checker", "running", "Verifying companies online")
    try:
        state = await run_web_checker_agent(state)
        checked = state.get("web_checker_results", {}).get("checked_count", 0)
        _emit(state, "web_checker", "done", f"Checked {checked} companies")
    except Exception as exc:
        logger.exception("web_checker_node failed: %s", exc)
        _emit(state, "web_checker", "error", str(exc))
        state.setdefault("web_checker_results", {})["error"] = str(exc)
    return state


async def anomaly_node(state: dict) -> dict:
    _emit(state, "anomaly_scorer", "running", "Analysing document anomalies")
    try:
        state = await run_anomaly_scorer(state)
        score = state.get("anomaly_results", {}).get("overall_anomaly_score", 0)
        _emit(state, "anomaly_scorer", "done", f"Anomaly score: {score}/100")
    except Exception as exc:
        logger.exception("anomaly_node failed: %s", exc)
        _emit(state, "anomaly_scorer", "error", str(exc))
        state.setdefault("anomaly_results", {})["error"] = str(exc)
    return state


async def vision_node(state: dict) -> dict:
    _emit(state, "vision", "running", "Visual fraud analysis with Gemini")
    try:
        state = await run_vision_agent(state)
        vs = state.get("vision_results", {}).get("visual_score", 50)
        _emit(state, "vision", "done", f"Visual trust score: {vs}/100")
    except Exception as exc:
        logger.exception("vision_node failed: %s", exc)
        _emit(state, "vision", "error", str(exc))
        state.setdefault("vision_results", {})["error"] = str(exc)
    return state


# ── Parallel runner for web_checker + anomaly ────────────────────────────────

async def parallel_analysis_node(state: dict) -> dict:
    """Run web checker and anomaly scorer concurrently."""
    results = await asyncio.gather(
        web_checker_node(dict(state)),
        anomaly_node(dict(state)),
        return_exceptions=True,
    )

    for res in results:
        if isinstance(res, Exception):
            logger.error("Parallel analysis sub-task error: %s", res)
            continue
        # Merge results back
        for key in ("web_checker_results", "anomaly_results", "agent_updates"):
            if key in res:
                if key == "agent_updates":
                    state.setdefault("agent_updates", []).extend(res[key])
                else:
                    state[key] = res[key]

    return state


# ── Aggregator ───────────────────────────────────────────────────────────────

def _build_red_flags(
    ocr: Dict[str, Any],
    ner: Dict[str, Any],
    web: Dict[str, Any],
    anomaly: Dict[str, Any],
    vision: Dict[str, Any],
) -> List[RedFlag]:
    flags: List[RedFlag] = []

    # OCR
    if ocr.get("avg_confidence", 100) < 40:
        flags.append(RedFlag(
            severity="high",
            category="OCR Quality",
            description=f"Very low OCR confidence ({ocr['avg_confidence']:.1f}%) – document may be blurred or tampered",
        ))
    elif ocr.get("avg_confidence", 100) < 65:
        flags.append(RedFlag(
            severity="medium",
            category="OCR Quality",
            description=f"Low OCR confidence ({ocr['avg_confidence']:.1f}%)",
        ))

    if ocr.get("word_count", 1) < 20:
        flags.append(RedFlag(
            severity="medium",
            category="Content",
            description="Document contains very little text",
        ))

    # NER
    if not ner.get("organisations") and not ner.get("persons"):
        flags.append(RedFlag(
            severity="medium",
            category="Identity",
            description="No named entities (companies or persons) found in document",
        ))

    # Web checker
    for company in web.get("suspicious", []):
        flags.append(RedFlag(
            severity="critical",
            category="Company Verification",
            description=f"Company '{company}' flagged as suspicious online",
        ))
    if web.get("unverified"):
        unverified_list = ", ".join(web["unverified"][:3])
        flags.append(RedFlag(
            severity="low",
            category="Company Verification",
            description=f"Could not verify online presence for: {unverified_list}",
        ))

    # Anomaly scorer
    for anomaly_desc in anomaly.get("anomalies", []):
        severity = "medium"
        lower = anomaly_desc.lower()
        if "future" in lower or "tampering" in lower or "tampered" in lower:
            severity = "high"
        elif "missing" in lower or "empty" in lower:
            severity = "low"
        flags.append(RedFlag(
            severity=severity,
            category="Document Anomaly",
            description=anomaly_desc,
        ))

    # Vision
    for vflag in vision.get("visual_flags", []):
        flags.append(RedFlag(
            severity="high",
            category="Visual Analysis",
            description=vflag,
        ))
    for ti in vision.get("tampering_indicators", []):
        flags.append(RedFlag(
            severity="critical",
            category="Tampering",
            description=ti,
        ))

    return flags


async def aggregate_node(state: dict) -> dict:
    _emit(state, "aggregator", "running", "Computing final trust score")

    ocr: Dict[str, Any] = state.get("ocr_results", {})
    ner: Dict[str, Any] = state.get("ner_results", {})
    web: Dict[str, Any] = state.get("web_checker_results", {})
    anomaly: Dict[str, Any] = state.get("anomaly_results", {})
    vision: Dict[str, Any] = state.get("vision_results", {})

    # ── Component scores (each 0-100, higher = more trustworthy) ────────────

    # OCR confidence (20%)
    ocr_conf = float(ocr.get("avg_confidence", 50))
    ocr_score = ocr_conf  # already 0-100

    # NER completeness (10%)
    has_org = bool(ner.get("organisations"))
    has_person = bool(ner.get("persons"))
    has_date = bool(ner.get("dates"))
    ner_completeness = (int(has_org) + int(has_person) + int(has_date)) / 3 * 100
    ner_score = ner_completeness

    # Web checker (25%)
    checked = web.get("checked_count", 0)
    if checked == 0:
        web_score = 50.0  # neutral when nothing to check
    else:
        verified_count = len(web.get("verified", []))
        suspicious_count = len(web.get("suspicious", []))
        web_score = (
            (verified_count / checked) * 100
            - (suspicious_count / checked) * 50
        )
        web_score = max(0.0, min(100.0, web_score))

    # Anomaly score inverted (25%): low anomaly = high trust
    raw_anomaly = float(anomaly.get("overall_anomaly_score", 0))
    anomaly_score = 100.0 - raw_anomaly

    # Vision (20%)
    vision_score = float(vision.get("visual_score", 50))

    # ── Weighted total ────────────────────────────────────────────────────────
    trust_score = (
        ocr_score * 0.20
        + ner_score * 0.10
        + web_score * 0.25
        + anomaly_score * 0.25
        + vision_score * 0.20
    )
    trust_score = round(max(0.0, min(100.0, trust_score)), 2)

    # ── Verdict ───────────────────────────────────────────────────────────────
    if trust_score >= 75:
        verdict = "AUTHENTIC"
    elif trust_score >= 40:
        verdict = "SUSPICIOUS"
    else:
        verdict = "FRAUDULENT"

    # ── Red flags ─────────────────────────────────────────────────────────────
    red_flags = _build_red_flags(ocr, ner, web, anomaly, vision)

    # ── Summary ───────────────────────────────────────────────────────────────
    gemini_analysis = vision.get("gemini_analysis", "")
    summary = (
        f"Document analysis complete. Trust score: {trust_score:.1f}/100 ({verdict}). "
        f"{len(red_flags)} issue(s) detected. "
        f"OCR confidence: {ocr_conf:.1f}%. "
        f"Anomaly score: {raw_anomaly:.0f}/100. "
    )
    if gemini_analysis:
        summary += f"Visual analysis: {gemini_analysis[:300]}"

    result = JobResult(
        job_id=state.get("job_id", ""),
        trust_score=trust_score,
        verdict=verdict,
        red_flags=red_flags,
        agent_results={
            "ocr": ocr,
            "ner": ner,
            "web_checker": web,
            "anomaly": anomaly,
            "vision": vision,
        },
        summary=summary,
    )

    state["final_result"] = result.model_dump(mode="json")
    _emit(
        state,
        "aggregator",
        "done",
        f"Trust score: {trust_score:.1f} – {verdict}",
    )
    logger.info("Aggregation complete – score=%.1f  verdict=%s", trust_score, verdict)
    return state


# ── Build graph ───────────────────────────────────────────────────────────────

def build_graph() -> Any:
    """Construct and compile the LangGraph StateGraph."""
    graph = StateGraph(dict)

    graph.add_node("ocr", ocr_node)
    graph.add_node("ner", ner_node)
    graph.add_node("parallel_analysis", parallel_analysis_node)
    graph.add_node("vision", vision_node)
    graph.add_node("aggregate", aggregate_node)

    graph.set_entry_point("ocr")
    graph.add_edge("ocr", "ner")
    graph.add_edge("ner", "parallel_analysis")
    graph.add_edge("parallel_analysis", "vision")
    graph.add_edge("vision", "aggregate")
    graph.add_edge("aggregate", END)

    return graph.compile()


# Module-level compiled graph (singleton)
compiled_graph = build_graph()


async def run_pipeline(initial_state: Dict[str, Any]) -> Dict[str, Any]:
    """Run the full LangGraph pipeline and return the final state."""
    initial_state.setdefault("agent_updates", [])
    final_state = await compiled_graph.ainvoke(initial_state)
    return final_state
