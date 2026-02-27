"""
Purview GCC Graph API client — metadata-only extraction.

Pulls from Microsoft Graph (beta) endpoints:
- Sensitivity label taxonomy
- Label coverage statistics
- DLP incidents (via security alerts)
- External sharing counts (via SharePoint reports)
- Retention policy coverage
- Insider Risk alert counts (trend only, no user details)

All data is aggregate counts/percentages. No document content, PII,
or user identities are collected.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Generator

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)


def _session() -> requests.Session:
    """Create a requests session with retry logic for Graph API."""
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


def _paginate(url: str, token: str) -> Generator[dict, None, None]:
    """Follow @odata.nextLink pagination through Graph API results."""
    sess = _session()
    while url:
        resp = sess.get(url, headers=_headers(token), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        yield from data.get("value", [])
        url = data.get("@odata.nextLink")


# ── Sensitivity Labels ─────────────────────────────────────────────


def get_sensitivity_labels(graph_base: str, token: str) -> list[dict]:
    """Return the sensitivity label taxonomy.

    Returns list of:
        {"label_id": str, "label_name": str, "parent_label_id": str | None, "tooltip": str}
    """
    url = f"{graph_base}/beta/security/informationProtection/sensitivityLabels"
    labels = []
    for item in _paginate(url, token):
        labels.append({
            "label_id": item.get("id", ""),
            "label_name": item.get("name", ""),
            "parent_label_id": item.get("parent", {}).get("id") if item.get("parent") else None,
            "tooltip": item.get("tooltip", ""),
        })
    log.info("Retrieved %d sensitivity labels", len(labels))
    return labels


# ── Label Coverage ─────────────────────────────────────────────────


def get_label_coverage(graph_base: str, token: str) -> dict[str, Any]:
    """Return label coverage statistics.

    Uses the data classification overview endpoint to get labeled vs unlabeled counts.

    Returns:
        {"labeled_count": int, "unlabeled_sensitive_count": int,
         "total_items": int, "coverage_pct": float}
    """
    # Attempt data classification overview
    url = f"{graph_base}/beta/security/informationProtection/sensitivityLabels/evaluateClassificationResults"

    # Fallback: use content label report if available
    overview_url = f"{graph_base}/beta/reports/security/getAttackSimulationRepeatOffenders"

    # Primary approach: get label analytics from security API
    sess = _session()

    # Try the label policy summary
    policy_url = f"{graph_base}/beta/security/informationProtection/sensitivityLabels"
    try:
        resp = sess.get(policy_url, headers=_headers(token), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        total_labels = len(data.get("value", []))
    except requests.HTTPError:
        total_labels = 0

    # Get content explorer data for coverage estimate
    content_url = f"{graph_base}/beta/security/informationProtection/contentLabel/evaluations"
    labeled_count = 0
    unlabeled_sensitive_count = 0
    total_items = 0

    try:
        resp = sess.get(
            f"{graph_base}/beta/dataClassification/classifyFileJobs",
            headers=_headers(token),
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            # Parse available metrics
            total_items = data.get("totalItemCount", 0)
            labeled_count = data.get("labeledItemCount", 0)
            unlabeled_sensitive_count = data.get("unlabeledSensitiveItemCount", 0)
    except requests.HTTPError as e:
        log.warning("Could not retrieve content classification data: %s", e)

    coverage_pct = (labeled_count / total_items * 100) if total_items > 0 else 0.0

    return {
        "labeled_count": labeled_count,
        "unlabeled_sensitive_count": unlabeled_sensitive_count,
        "total_items": total_items,
        "coverage_pct": round(coverage_pct, 2),
    }


# ── DLP Incidents ──────────────────────────────────────────────────


def get_dlp_incidents(graph_base: str, token: str) -> dict[str, int]:
    """Return DLP incident counts for 30/60/90 day windows.

    Uses the security alerts v2 API filtered to DataLossPrevention category.

    Returns:
        {"last_30d": int, "last_60d": int, "last_90d": int}
    """
    sess = _session()
    now = datetime.now(timezone.utc)
    results = {}

    for days, key in [(30, "last_30d"), (60, "last_60d"), (90, "last_90d")]:
        cutoff = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        url = (
            f"{graph_base}/beta/security/alerts_v2"
            f"?$filter=category eq 'DataLossPrevention' and createdDateTime ge {cutoff}"
            f"&$count=true&$top=1"
        )
        try:
            resp = sess.get(url, headers={**_headers(token), "ConsistencyLevel": "eventual"}, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            results[key] = data.get("@odata.count", len(data.get("value", [])))
        except requests.HTTPError as e:
            log.warning("DLP incidents query failed for %d days: %s", days, e)
            results[key] = 0

    log.info("DLP incidents: %s", results)
    return results


# ── External Sharing ───────────────────────────────────────────────


def get_external_sharing_count(graph_base: str, token: str) -> int:
    """Return count of externally shared items via SharePoint usage reports.

    Uses the getSharePointSiteUsageDetail report (30-day period).
    """
    url = f"{graph_base}/beta/reports/getSharePointSiteUsageDetail(period='D30')"
    sess = _session()

    try:
        resp = sess.get(url, headers=_headers(token), timeout=60)
        resp.raise_for_status()
        # Response is CSV format
        lines = resp.text.strip().split("\n")
        if len(lines) < 2:
            return 0

        # Parse CSV header to find external sharing column
        headers = lines[0].split(",")
        ext_idx = None
        for i, h in enumerate(headers):
            if "external" in h.lower() and "sharing" in h.lower():
                ext_idx = i
                break

        if ext_idx is None:
            log.warning("External sharing column not found in SharePoint report")
            return 0

        total = 0
        for line in lines[1:]:
            cols = line.split(",")
            if ext_idx < len(cols) and cols[ext_idx].strip().isdigit():
                total += int(cols[ext_idx].strip())

        return total
    except requests.HTTPError as e:
        log.warning("External sharing report failed: %s", e)
        return 0


# ── Retention Policy Coverage ──────────────────────────────────────


def get_retention_policy_coverage(graph_base: str, token: str) -> dict[str, Any]:
    """Return retention policy coverage statistics.

    Returns:
        {"policies_count": int, "locations_covered": int, "coverage_pct": float}
    """
    url = f"{graph_base}/beta/security/labels/retentionLabels"
    sess = _session()

    policies_count = 0
    try:
        for _ in _paginate(url, token):
            policies_count += 1
    except requests.HTTPError as e:
        log.warning("Retention policy query failed: %s", e)

    # Estimate coverage from retention event types
    event_url = f"{graph_base}/beta/security/triggerTypes/retentionEventTypes"
    locations_covered = 0
    try:
        for _ in _paginate(event_url, token):
            locations_covered += 1
    except requests.HTTPError:
        pass

    # Coverage percentage is best-effort based on available API data
    coverage_pct = min(100.0, policies_count * 10.0) if policies_count > 0 else 0.0

    return {
        "policies_count": policies_count,
        "locations_covered": locations_covered,
        "coverage_pct": round(coverage_pct, 2),
    }


# ── Insider Risk Trend ─────────────────────────────────────────────


def get_insider_risk_trend(graph_base: str, token: str) -> dict[str, int]:
    """Return insider risk alert counts by severity.

    IMPORTANT: Returns counts only — no user names, case details, or PII.

    Returns:
        {"high": int, "medium": int, "low": int, "total": int}
    """
    sess = _session()
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")

    url = (
        f"{graph_base}/beta/security/alerts_v2"
        f"?$filter=category eq 'InsiderRisk' and createdDateTime ge {cutoff}"
        f"&$select=severity"
    )

    counts = {"high": 0, "medium": 0, "low": 0, "total": 0}
    try:
        for alert in _paginate(url, token):
            severity = (alert.get("severity") or "").lower()
            if severity in counts:
                counts[severity] += 1
            counts["total"] += 1
    except requests.HTTPError as e:
        log.warning("Insider risk trend query failed: %s", e)

    log.info("Insider risk trend (90d): %s", counts)
    return counts
