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
    # ── New: ungameable layer agents ──────────────────────────────────────────
    consistency_results: Dict[str, Any]
    email_results: Dict[str, Any]
    govt_results: Dict[str, Any]
    linguistic_results: Dict[str, Any]
    statistical_results: Dict[str, Any]
    # ─────────────────────────────────────────────────────────────────────────
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


# ── New: Semantic + ground-truth agent nodes ─────────────────────────────────

async def consistency_node(state: dict) -> dict:
    _emit(state, "consistency", "running", "Checking cross-field logical consistency")
    try:
        from agents.consistency_checker import check_consistency  # type: ignore
        ocr_text = state.get("ocr_results", {}).get("full_text", "")
        entities = state.get("ner_results", {})
        state["consistency_results"] = check_consistency(entities, ocr_text)
        pen = state["consistency_results"].get("consistency_penalty", 0)
        _emit(state, "consistency", "done", f"Consistency penalty: {pen} pts")
    except Exception as exc:
        logger.exception("consistency_node failed: %s", exc)
        _emit(state, "consistency", "error", str(exc))
        state["consistency_results"] = {"consistency_penalty": 0, "consistency_flags": []}
    return state


async def email_verify_node(state: dict) -> dict:
    _emit(state, "email_verify", "running", "Verifying email domain authenticity")
    try:
        from agents.email_verifier import extract_email_from_text, verify_email_domain  # type: ignore
        ocr_text = state.get("ocr_results", {}).get("full_text", "")
        company = (state.get("ner_results", {}).get("organisations") or [""])[0]
        email = extract_email_from_text(ocr_text)
        state["email_results"] = verify_email_domain(email, company)
        pen = state["email_results"].get("email_penalty", 0)
        _emit(state, "email_verify", "done", f"Email penalty: {pen} pts")
    except Exception as exc:
        logger.exception("email_verify_node failed: %s", exc)
        _emit(state, "email_verify", "error", str(exc))
        state["email_results"] = {"email_penalty": 0, "flags": []}
    return state


async def govt_verify_node(state: dict) -> dict:
    _emit(state, "govt_verify", "running", "Validating GSTIN and CIN registration numbers")
    try:
        from agents.govt_verifier import cross_verify_ids  # type: ignore
        entities = state.get("ner_results", {})
        state["govt_results"] = cross_verify_ids(entities)
        pen = state["govt_results"].get("govt_penalty", 0)
        _emit(state, "govt_verify", "done", f"Govt penalty: {pen} pts")
    except Exception as exc:
        logger.exception("govt_verify_node failed: %s", exc)
        _emit(state, "govt_verify", "error", str(exc))
        state["govt_results"] = {"govt_penalty": 0, "govt_flags": []}
    return state


async def linguistic_node(state: dict) -> dict:
    _emit(state, "linguistic", "running", "Linguistic fingerprinting analysis")
    try:
        from agents.linguistic_agent import analyze_linguistics  # type: ignore
        ocr_text = state.get("ocr_results", {}).get("full_text", "")
        doc_type = state.get("vision_results", {}).get("document_type", "unknown")
        company = (state.get("ner_results", {}).get("organisations") or ["unknown"])[0]
        cache_key = f"ling_{hash(ocr_text[:150]) % 999_999}"
        state["linguistic_results"] = analyze_linguistics(ocr_text, company, doc_type, cache_key=cache_key)
        pen = state["linguistic_results"].get("linguistic_penalty", 0)
        _emit(state, "linguistic", "done", f"Linguistic penalty: {pen} pts")
    except Exception as exc:
        logger.exception("linguistic_node failed: %s", exc)
        _emit(state, "linguistic", "error", str(exc))
        state["linguistic_results"] = {"linguistic_penalty": 0, "linguistic_flags": []}
    return state


async def statistical_node(state: dict) -> dict:
    _emit(state, "statistical", "running", "Statistical anomaly detection")
    try:
        from agents.statistical_analyzer import detect_statistical_anomalies  # type: ignore
        ocr_text = state.get("ocr_results", {}).get("full_text", "")
        doc_type = state.get("vision_results", {}).get("document_type", "unknown")
        state["statistical_results"] = detect_statistical_anomalies(ocr_text, doc_type)
        pen = state["statistical_results"].get("stat_penalty", 0)
        _emit(state, "statistical", "done", f"Statistical penalty: {pen} pts")
    except Exception as exc:
        logger.exception("statistical_node failed: %s", exc)
        _emit(state, "statistical", "error", str(exc))
        state["statistical_results"] = {"stat_penalty": 0, "stat_flags": []}
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
    _emit(state, "aggregator", "running", "Computing final trust score (4-layer)")

    ocr: Dict[str, Any] = state.get("ocr_results", {})
    ner: Dict[str, Any] = state.get("ner_results", {})
    web: Dict[str, Any] = state.get("web_checker_results", {})
    anomaly: Dict[str, Any] = state.get("anomaly_results", {})
    vision: Dict[str, Any] = state.get("vision_results", {})
    consistency: Dict[str, Any] = state.get("consistency_results", {})
    email: Dict[str, Any] = state.get("email_results", {})
    govt: Dict[str, Any] = state.get("govt_results", {})
    linguistic: Dict[str, Any] = state.get("linguistic_results", {})
    statistical: Dict[str, Any] = state.get("statistical_results", {})

    # ── Start at 100, deduct penalties ───────────────────────────────────────
    score = 100.0
    layer_deductions: Dict[str, float] = {}

    # LAYER 1 — Technical (OCR + anomaly)
    ocr_conf = float(ocr.get("avg_confidence", 100))
    if ocr_conf < 70:
        d = 15.0
    elif ocr_conf < 85:
        d = 8.0
    else:
        d = 0.0
    score -= d
    layer_deductions["ocr_confidence"] = d

    raw_anomaly = float(anomaly.get("overall_anomaly_score", 0))
    anomaly_pen = raw_anomaly * 0.30  # scale 0-100 → 0-30
    score -= anomaly_pen
    layer_deductions["anomaly"] = anomaly_pen

    # LAYER 2 — Semantic (hard to game)
    con_pen = float(consistency.get("consistency_penalty", 0))
    email_pen = float(email.get("email_penalty", 0))
    ling_pen = float(linguistic.get("linguistic_penalty", 0))
    stat_pen = float(statistical.get("stat_penalty", 0))
    score -= con_pen + email_pen + ling_pen + stat_pen
    layer_deductions["semantic"] = con_pen + email_pen + ling_pen + stat_pen

    # LAYER 3 — Ground truth (impossible to fake)
    govt_pen = float(govt.get("govt_penalty", 0))
    checked = web.get("checked_count", 0)
    if checked > 0:
        verified = len(web.get("verified", []))
        ratio = verified / checked
        if ratio == 0:
            web_pen = 25.0
        elif ratio < 0.5:
            web_pen = 15.0
        else:
            web_pen = 0.0
    else:
        web_pen = 0.0
    score -= govt_pen + web_pen
    layer_deductions["ground_truth"] = govt_pen + web_pen

    # LAYER 4 — AI Vision
    vision_pen = float(vision.get("visual_penalty", 0))
    score -= vision_pen
    layer_deductions["vision"] = vision_pen

    trust_score = round(max(0.0, min(100.0, score)), 2)
    total_deducted = round(100.0 - trust_score, 2)

    # ── Verdict ───────────────────────────────────────────────────────────────
    if trust_score >= 80:
        verdict = "AUTHENTIC"
    elif trust_score >= 60:
        verdict = "SUSPICIOUS"
    elif trust_score >= 40:
        verdict = "HIGH RISK"
    else:
        verdict = "FRAUDULENT"

    # ── Red flags (original + new layers) ────────────────────────────────────
    red_flags = _build_red_flags(ocr, ner, web, anomaly, vision)

    # Add new-layer flags as RedFlag objects
    for f in consistency.get("consistency_flags", []):
        red_flags.append(RedFlag(
            severity=f.get("severity", "medium").lower(),
            category="Consistency",
            description=f.get("issue", ""),
        ))
    for f in email.get("flags", []):
        red_flags.append(RedFlag(
            severity=f.get("severity", "medium").lower(),
            category="Email Verification",
            description=f.get("issue", ""),
        ))
    for f in govt.get("govt_flags", []):
        red_flags.append(RedFlag(
            severity=f.get("severity", "high").lower(),
            category="Govt Registration",
            description=f.get("issue", ""),
        ))
    for f in linguistic.get("linguistic_flags", []):
        red_flags.append(RedFlag(
            severity=f.get("severity", "medium").lower(),
            category="Linguistic",
            description=f.get("issue", ""),
        ))
    for f in statistical.get("stat_flags", []):
        red_flags.append(RedFlag(
            severity=f.get("severity", "low").lower(),
            category="Statistical",
            description=f.get("issue", ""),
        ))

    # ── Summary ───────────────────────────────────────────────────────────────
    summary = (
        f"Trust score: {trust_score:.1f}/100 ({verdict}). "
        f"{len(red_flags)} issue(s) detected. "
        f"Total deducted: {total_deducted} pts across 4 layers."
    )

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
            "consistency": consistency,
            "email": email,
            "govt": govt,
            "linguistic": linguistic,
            "statistical": statistical,
            "score_breakdown": {**layer_deductions, "total_deducted": total_deducted},
        },
        summary=summary,
    )

    state["final_result"] = result.model_dump(mode="json")
    _emit(
        state,
        "aggregator",
        "done",
        f"Trust score: {trust_score:.1f} – {verdict} ({len(red_flags)} flags)",
    )
    logger.info("Aggregation complete – score=%.1f  verdict=%s", trust_score, verdict)
    return state


# ── Build graph ───────────────────────────────────────────────────────────────

def build_graph() -> Any:
    """
    Construct and compile the LangGraph StateGraph.

    Pipeline (sequential):
      ocr → ner → consistency → email_verify → govt_verify
          → parallel_analysis (web + anomaly)
          → vision → linguistic → statistical → aggregate
    """
    graph = StateGraph(dict)

    graph.add_node("ocr", ocr_node)
    graph.add_node("ner", ner_node)
    # ── New semantic/ground-truth nodes ─────────────────────────────────────
    graph.add_node("consistency", consistency_node)
    graph.add_node("email_verify", email_verify_node)
    graph.add_node("govt_verify", govt_verify_node)
    # ── Existing nodes ───────────────────────────────────────────────────────
    graph.add_node("parallel_analysis", parallel_analysis_node)
    graph.add_node("vision", vision_node)
    # ── New AI analysis nodes ────────────────────────────────────────────────
    graph.add_node("linguistic", linguistic_node)
    graph.add_node("statistical", statistical_node)
    graph.add_node("aggregate", aggregate_node)

    graph.set_entry_point("ocr")
    graph.add_edge("ocr", "ner")
    graph.add_edge("ner", "consistency")
    graph.add_edge("consistency", "email_verify")
    graph.add_edge("email_verify", "govt_verify")
    graph.add_edge("govt_verify", "parallel_analysis")
    graph.add_edge("parallel_analysis", "vision")
    graph.add_edge("vision", "linguistic")
    graph.add_edge("linguistic", "statistical")
    graph.add_edge("statistical", "aggregate")
    graph.add_edge("aggregate", END)

    return graph.compile()


# Module-level compiled graph (singleton)
compiled_graph = build_graph()


async def run_pipeline(initial_state: Dict[str, Any]) -> Dict[str, Any]:
    """Run the full LangGraph pipeline and return the final state."""
    initial_state.setdefault("agent_updates", [])
    final_state = await compiled_graph.ainvoke(initial_state)
    return final_state
