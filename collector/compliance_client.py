"""
Compliance Manager GCC Graph API client.

Pulls native Compliance Manager data:
- Compliance Score (current/max)
- Assessments per regulation
- Improvement actions summary (counts by status)

All scores are passed through as-is from the API — no custom formulas.
"""

import logging
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)


def _session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=4,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        respect_retry_after_header=True,
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _paginate(url: str, token: str):
    sess = _session()
    while url:
        resp = sess.get(url, headers=_headers(token), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        yield from data.get("value", [])
        url = data.get("@odata.nextLink")


# ── Compliance Score ───────────────────────────────────────────────


def get_compliance_score(graph_base: str, token: str) -> dict[str, float]:
    """Return the tenant-level Compliance Manager score.

    Returns:
        {"current_score": float, "max_score": float}

    Scores are native from Compliance Manager — no transformation applied.
    """
    sess = _session()

    # Try the direct compliance score endpoint
    url = f"{graph_base}/beta/compliance/complianceManagement/complianceScore"
    try:
        resp = sess.get(url, headers=_headers(token), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return {
            "current_score": float(data.get("currentScore", 0)),
            "max_score": float(data.get("maxScore", 0)),
        }
    except requests.HTTPError:
        pass

    # Fallback: derive from assessments
    log.info("Direct compliance score endpoint unavailable, deriving from assessments")
    assessments = get_assessments(graph_base, token)
    if not assessments:
        return {"current_score": 0.0, "max_score": 0.0}

    total_score = sum(a.get("compliance_score", 0) for a in assessments)
    total_max = sum(a.get("total_controls", 0) for a in assessments)
    return {
        "current_score": float(total_score),
        "max_score": float(total_max) if total_max > 0 else 100.0,
    }


# ── Assessments ────────────────────────────────────────────────────


def get_assessments(graph_base: str, token: str) -> list[dict[str, Any]]:
    """Return all Compliance Manager assessments.

    Returns list of:
        {
            "assessment_id": str,
            "regulation": str,
            "display_name": str,
            "compliance_score": float,   # Native score from Compliance Manager
            "passed_controls": int,
            "failed_controls": int,
            "total_controls": int,
        }
    """
    url = f"{graph_base}/beta/compliance/complianceManagement/assessments"

    assessments = []
    try:
        for item in _paginate(url, token):
            passed = int(item.get("passedControls", 0))
            failed = int(item.get("failedControls", 0))
            total = int(item.get("totalControls", 0))

            assessments.append({
                "assessment_id": item.get("id", ""),
                "regulation": item.get("complianceStandard", item.get("regulationName", "")),
                "display_name": item.get("displayName", ""),
                "compliance_score": float(item.get("complianceScore", 0)),
                "passed_controls": passed,
                "failed_controls": failed,
                "total_controls": total,
            })
    except requests.HTTPError as e:
        log.warning("Assessments query failed: %s", e)

    log.info("Retrieved %d assessments", len(assessments))
    return assessments


# ── Improvement Actions ────────────────────────────────────────────


def get_improvement_actions_summary(graph_base: str, token: str) -> dict[str, int]:
    """Return improvement actions counts grouped by status.

    Returns:
        {"implemented": int, "planned": int, "not_started": int, "total": int}
    """
    url = f"{graph_base}/beta/compliance/complianceManagement/improvementActions"

    counts = {"implemented": 0, "planned": 0, "not_started": 0, "total": 0}
    try:
        for item in _paginate(url, token):
            status = (item.get("implementationStatus") or "").lower().replace(" ", "_")
            counts["total"] += 1
            if status in ("implemented", "completed"):
                counts["implemented"] += 1
            elif status in ("in_progress", "planned"):
                counts["planned"] += 1
            else:
                counts["not_started"] += 1
    except requests.HTTPError as e:
        log.warning("Improvement actions query failed: %s", e)

    log.info("Improvement actions: %s", counts)
    return counts
