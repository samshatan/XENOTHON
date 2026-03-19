"""
Anomaly Scorer Agent – analyses structural and metadata anomalies in documents.

Checks:
    - PDF metadata (creation date, modification date, author, producer, keywords)
    - Future dates or missing critical metadata fields
    - Modified after creation (potential tampering)
    - Font diversity (many different fonts may indicate pasted content)
    - OCR confidence variance (high variance = potentially manipulated regions)

Outputs (stored in state["anomaly_results"]):
    metadata_score      : 0-100 (higher = more anomalous metadata)
    font_score          : 0-100 (higher = more font anomalies)
    confidence_score    : 0-100 (higher = more OCR confidence anomalies)
    anomalies           : list of anomaly description strings
    font_list           : list of unique fonts found
    overall_anomaly_score : 0-100
"""

from __future__ import annotations

import asyncio
import logging
import os
import statistics
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _parse_pdf_date(date_str: str) -> datetime | None:
    """Parse a PDF date string like D:20230101120000+05'30' into datetime."""
    if not date_str:
        return None
    try:
        # Strip leading 'D:' if present
        s = date_str.strip()
        if s.startswith("D:"):
            s = s[2:]
        # Take first 14 chars: YYYYMMDDHHmmss
        s = s[:14]
        return datetime.strptime(s, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _analyse_pdf(file_path: str) -> Dict[str, Any]:
    import fitz

    doc = fitz.open(file_path)
    metadata = doc.metadata or {}
    anomalies: List[str] = []
    metadata_score = 0

    now = datetime.now(tz=timezone.utc)

    # ── Metadata checks ────────────────────────────────────────────────────
    creation_date = _parse_pdf_date(metadata.get("creationDate", ""))
    mod_date = _parse_pdf_date(metadata.get("modDate", ""))

    if not creation_date:
        anomalies.append("Missing creation date in PDF metadata")
        metadata_score += 20
    elif creation_date > now:
        anomalies.append(f"Creation date is in the future: {creation_date.date()}")
        metadata_score += 40

    if mod_date and creation_date and mod_date > creation_date:
        delta = (mod_date - creation_date).total_seconds()
        if delta > 0:
            anomalies.append(
                f"Document modified after creation (delta {int(delta/3600)}h) – potential tampering"
            )
            metadata_score += 25

    if mod_date and mod_date > now:
        anomalies.append(f"Modification date is in the future: {mod_date.date()}")
        metadata_score += 30

    if not metadata.get("author", "").strip():
        anomalies.append("Author field is empty")
        metadata_score += 10

    producer = metadata.get("producer", "").lower()
    suspicious_producers = ["ghostscript", "ilovepdf", "smallpdf", "sodapdf", "img2pdf"]
    for sp in suspicious_producers:
        if sp in producer:
            anomalies.append(f"Document produced by potentially suspicious tool: {producer}")
            metadata_score += 15
            break

    metadata_score = min(metadata_score, 100)

    # ── Font analysis ───────────────────────────────────────────────────────
    font_set: set = set()
    for page in doc:
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 0:  # 0 = text block
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    fname = span.get("font", "")
                    if fname:
                        font_set.add(fname)

    font_list = sorted(font_set)
    font_count = len(font_list)
    font_score = 0

    if font_count == 0:
        font_score = 10
        anomalies.append("No fonts detected in document")
    elif font_count > 10:
        font_score = min((font_count - 5) * 8, 80)
        anomalies.append(
            f"Unusually high number of fonts ({font_count}) – may indicate pasted/edited content"
        )
    elif font_count > 6:
        font_score = (font_count - 4) * 10
        anomalies.append(f"Multiple fonts detected ({font_count})")

    doc.close()
    return {
        "metadata": {
            "author": metadata.get("author", ""),
            "producer": metadata.get("producer", ""),
            "creation_date": creation_date.isoformat() if creation_date else None,
            "mod_date": mod_date.isoformat() if mod_date else None,
            "title": metadata.get("title", ""),
            "subject": metadata.get("subject", ""),
        },
        "anomalies": anomalies,
        "metadata_score": metadata_score,
        "font_score": font_score,
        "font_list": font_list,
        "font_count": font_count,
    }


def _analyse_image(_file_path: str) -> Dict[str, Any]:
    """Images have minimal metadata – return a baseline result."""
    return {
        "metadata": {},
        "anomalies": ["Image file – limited metadata available"],
        "metadata_score": 5,
        "font_score": 0,
        "font_list": [],
        "font_count": 0,
    }


async def run_anomaly_scorer(state: dict) -> dict:
    file_path: str = state.get("file_path", "")
    ocr_results: Dict[str, Any] = state.get("ocr_results", {})

    if not file_path or not os.path.exists(file_path):
        logger.error("Anomaly scorer: file not found at %s", file_path)
        state["anomaly_results"] = {
            "metadata_score": 0,
            "font_score": 0,
            "confidence_score": 0,
            "anomalies": [f"File not found: {file_path}"],
            "font_list": [],
            "overall_anomaly_score": 0,
            "error": f"File not found: {file_path}",
        }
        return state

    ext = os.path.splitext(file_path)[1].lower()
    loop = asyncio.get_event_loop()

    try:
        if ext == ".pdf":
            doc_analysis = await loop.run_in_executor(None, _analyse_pdf, file_path)
        else:
            doc_analysis = await loop.run_in_executor(None, _analyse_image, file_path)
    except Exception as exc:
        logger.exception("Anomaly scorer structural analysis failed: %s", exc)
        doc_analysis = {
            "metadata": {},
            "anomalies": [f"Analysis error: {exc}"],
            "metadata_score": 0,
            "font_score": 0,
            "font_list": [],
            "font_count": 0,
        }

    # ── OCR confidence variance ─────────────────────────────────────────────
    pages_data = ocr_results.get("pages_data", [])
    confidence_score = 0
    conf_anomalies: List[str] = []

    if len(pages_data) >= 2:
        confidences = [p.get("confidence", 100) for p in pages_data]
        try:
            stdev = statistics.stdev(confidences)
        except statistics.StatisticsError:
            stdev = 0.0

        if stdev > 30:
            confidence_score = min(int(stdev), 80)
            conf_anomalies.append(
                f"High OCR confidence variance across pages (σ={stdev:.1f}) – "
                "some regions may have been digitally altered"
            )
        elif stdev > 15:
            confidence_score = int(stdev * 1.5)
            conf_anomalies.append(
                f"Moderate OCR confidence variance (σ={stdev:.1f})"
            )
    elif pages_data:
        avg_conf = pages_data[0].get("confidence", 100)
        if avg_conf < 40:
            confidence_score = 60
            conf_anomalies.append(
                f"Very low OCR confidence ({avg_conf:.1f}%) – document may be low quality or tampered"
            )

    all_anomalies = doc_analysis["anomalies"] + conf_anomalies

    # ── Overall anomaly score (weighted average) ────────────────────────────
    metadata_score: int = doc_analysis["metadata_score"]
    font_score: int = doc_analysis["font_score"]
    overall = int(
        metadata_score * 0.40
        + font_score * 0.30
        + confidence_score * 0.30
    )
    overall = max(0, min(overall, 100))

    state["anomaly_results"] = {
        "metadata_score": metadata_score,
        "font_score": font_score,
        "confidence_score": confidence_score,
        "anomalies": all_anomalies,
        "font_list": doc_analysis["font_list"],
        "font_count": doc_analysis.get("font_count", 0),
        "metadata": doc_analysis.get("metadata", {}),
        "overall_anomaly_score": overall,
    }

    logger.info(
        "Anomaly scorer complete – overall_score=%d  anomalies=%d",
        overall,
        len(all_anomalies),
    )
    return state
