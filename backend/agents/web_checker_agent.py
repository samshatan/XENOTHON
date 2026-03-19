"""
Web Checker Agent – verifies company names via Tavily search.

Classifies each company as:
    verified   : strong online presence / official registration found
    unverified : little or no results
    suspicious : results suggest fraud / mismatch

Outputs (stored in state["web_checker_results"]):
    verified      : list of company names
    unverified    : list of company names
    suspicious    : list of company names
    web_results   : dict company_name -> raw search snippet
    checked_count : total companies checked
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

_SUSPICIOUS_KEYWORDS = [
    "fraud",
    "scam",
    "fake",
    "bogus",
    "shell company",
    "money laundering",
    "blacklist",
    "banned",
    "deregistered",
    "struck off",
    "ponzi",
]
_VERIFIED_KEYWORDS = [
    "official website",
    "registered",
    "incorporated",
    "listed on",
    "founded",
    "headquarters",
    "about us",
    "annual report",
    "company registration",
    "cin:",
    "llp",
    "pvt ltd",
    "private limited",
    "limited company",
]


def _classify_results(company: str, results: List[Dict[str, Any]]) -> str:
    if not results:
        return "unverified"

    combined_text = " ".join(
        (r.get("title", "") + " " + r.get("content", "")).lower() for r in results
    )

    suspicious_hits = sum(1 for kw in _SUSPICIOUS_KEYWORDS if kw in combined_text)
    verified_hits = sum(1 for kw in _VERIFIED_KEYWORDS if kw in combined_text)

    if suspicious_hits >= 2:
        return "suspicious"
    if verified_hits >= 2 or len(results) >= 3:
        return "verified"
    return "unverified"


async def _search_company(client: Any, company: str) -> Dict[str, Any]:
    """Run a single Tavily search for a company name."""
    query = f'"{company}" official registration company'
    loop = asyncio.get_event_loop()
    try:
        response = await loop.run_in_executor(
            None,
            lambda: client.search(
                query=query,
                search_depth="basic",
                max_results=5,
                include_answer=True,
            ),
        )
        results: List[Dict[str, Any]] = response.get("results", [])
        answer: str = response.get("answer", "")
        classification = _classify_results(company, results)
        return {
            "company": company,
            "classification": classification,
            "answer": answer,
            "result_count": len(results),
            "top_urls": [r.get("url", "") for r in results[:3]],
        }
    except Exception as exc:
        logger.warning("Tavily search failed for '%s': %s", company, exc)
        return {
            "company": company,
            "classification": "unverified",
            "answer": "",
            "result_count": 0,
            "top_urls": [],
            "error": str(exc),
        }


def _mock_result(company: str) -> Dict[str, Any]:
    """Return a neutral mock result when Tavily is unavailable."""
    return {
        "company": company,
        "classification": "unverified",
        "answer": "Tavily API not configured – skipped",
        "result_count": 0,
        "top_urls": [],
        "skipped": True,
    }


async def run_web_checker_agent(state: dict) -> dict:
    ner_results: Dict[str, Any] = state.get("ner_results", {})
    organisations: List[str] = ner_results.get("organisations", [])

    # Limit to top 5 companies to avoid rate limits
    companies = organisations[:5]

    verified: List[str] = []
    unverified: List[str] = []
    suspicious: List[str] = []
    web_results: Dict[str, Any] = {}

    if not companies:
        logger.info("Web checker: no organisations to check")
        state["web_checker_results"] = {
            "verified": [],
            "unverified": [],
            "suspicious": [],
            "web_results": {},
            "checked_count": 0,
            "note": "No company names found in document",
        }
        return state

    if not _TAVILY_API_KEY:
        logger.warning("TAVILY_API_KEY not set – skipping web checks")
        for company in companies:
            mock = _mock_result(company)
            unverified.append(company)
            web_results[company] = mock
        state["web_checker_results"] = {
            "verified": verified,
            "unverified": unverified,
            "suspicious": suspicious,
            "web_results": web_results,
            "checked_count": len(companies),
            "note": "Tavily API key not configured",
        }
        return state

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=_TAVILY_API_KEY)
    except Exception as exc:
        logger.error("Failed to initialise Tavily client: %s", exc)
        for company in companies:
            unverified.append(company)
            web_results[company] = _mock_result(company)
        state["web_checker_results"] = {
            "verified": verified,
            "unverified": unverified,
            "suspicious": suspicious,
            "web_results": web_results,
            "checked_count": len(companies),
            "error": str(exc),
        }
        return state

    # Run searches concurrently
    tasks = [_search_company(client, company) for company in companies]
    search_results = await asyncio.gather(*tasks, return_exceptions=True)

    for company, res in zip(companies, search_results):
        if isinstance(res, Exception):
            exc_msg = str(res)
            res = _mock_result(company)
            res["error"] = exc_msg

        web_results[company] = res
        classification = res.get("classification", "unverified")
        if classification == "verified":
            verified.append(company)
        elif classification == "suspicious":
            suspicious.append(company)
        else:
            unverified.append(company)

    state["web_checker_results"] = {
        "verified": verified,
        "unverified": unverified,
        "suspicious": suspicious,
        "web_results": web_results,
        "checked_count": len(companies),
    }
    logger.info(
        "Web checker complete – verified=%d  unverified=%d  suspicious=%d",
        len(verified),
        len(unverified),
        len(suspicious),
    )
    return state
