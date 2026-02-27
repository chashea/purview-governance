"""
Azure Function App — Purview Governance Ingestion & AI Agent

Runs in Azure Commercial (*.azurewebsites.net).
Uses the v2 Python programming model.

Functions:
- ingest_posture:      HTTP POST — receive and validate posture payloads
- compute_aggregates:  Timer     — daily statewide aggregate computation
- ai_executive:        HTTP POST — interactive AI query against posture data
- generate_report:     HTTP POST — generate PDF/PPTX executive summary
"""

import json
import logging

import azure.functions as func

from shared.ai_agent import ask_executive_agent
from shared.normalizer import compute_statewide_aggregates, normalize_labels
from shared.report_generator import generate_pdf, generate_pptx
from shared.table_client import (
    read_latest_snapshots_all_agencies,
    write_assessment_summaries,
    write_posture_snapshot,
)
from shared.validation import validate_ingestion_request

app = func.FunctionApp()
log = logging.getLogger(__name__)


# ── HTTP Trigger: Ingest posture payload ────────────────────────────


@app.function_name("ingest_posture")
@app.route(route="ingest", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def ingest_posture(req: func.HttpRequest) -> func.HttpResponse:
    """Receive JSON payload from per-tenant collector.

    Validates certificate, tenant allow-list, and JSON schema.
    Normalizes labels and writes to Table Storage.
    """
    try:
        # 1. Validate request (cert thumbprint, tenant allow-list, JSON schema)
        payload = validate_ingestion_request(req)

        # 2. Normalize labels to standard tiers
        normalized_labels = normalize_labels(payload.get("label_taxonomy", []))

        # 3. Write posture snapshot to Table Storage
        write_posture_snapshot(payload, normalized_labels)

        # 4. Write assessment summaries
        write_assessment_summaries(payload)

        log.info(
            "Ingested posture for tenant=%s agency=%s compliance=%.1f%%",
            payload["tenant_id"],
            payload["agency_id"],
            payload.get("compliance_score_current", 0),
        )
        return func.HttpResponse(
            json.dumps({
                "status": "ok",
                "agency_id": payload["agency_id"],
                "compliance_score": payload.get("compliance_score_current", 0),
            }),
            status_code=200,
            mimetype="application/json",
        )
    except ValueError as e:
        log.warning("Validation failed: %s", e)
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=400,
            mimetype="application/json",
        )
    except Exception as e:
        log.exception("Ingestion error: %s", e)
        return func.HttpResponse(
            json.dumps({"error": "Internal server error"}),
            status_code=500,
            mimetype="application/json",
        )


# ── Timer Trigger: Recompute statewide aggregates ───────────────────


@app.function_name("compute_aggregates")
@app.timer_trigger(schedule="0 0 6 * * *", arg_name="timer", run_on_startup=False)
def compute_aggregates(timer: func.TimerRequest) -> None:
    """Daily at 6:00 AM UTC: read all agency snapshots, compute statewide aggregates.

    Aggregates are simple rollups of native scores — no custom risk formulas.
    """
    try:
        snapshots = read_latest_snapshots_all_agencies()
        if not snapshots:
            log.info("No agency snapshots found, skipping aggregate computation")
            return

        aggregates = compute_statewide_aggregates(snapshots)
        log.info(
            "Statewide aggregates: %d agencies, avg compliance=%.1f%%",
            aggregates.get("TotalAgencies", 0),
            aggregates.get("AvgComplianceScore", 0),
        )
    except Exception as e:
        log.exception("Aggregate computation failed: %s", e)


# ── HTTP Trigger: AI Executive Agent query ──────────────────────────


@app.function_name("ai_executive")
@app.route(route="ai/query", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def ai_executive(req: func.HttpRequest) -> func.HttpResponse:
    """Interactive AI query against aggregated posture data.

    Request body:
        {"question": "...", "agency_id": "..." (optional)}
    """
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON body"}),
            status_code=400,
            mimetype="application/json",
        )

    question = body.get("question", "")
    if not question:
        return func.HttpResponse(
            json.dumps({"error": "Missing 'question' field"}),
            status_code=400,
            mimetype="application/json",
        )

    agency_filter = body.get("agency_id")
    try:
        result = ask_executive_agent(question, agency_filter)
        return func.HttpResponse(json.dumps(result), mimetype="application/json")
    except Exception as e:
        log.exception("AI agent error: %s", e)
        return func.HttpResponse(
            json.dumps({"error": "AI agent processing failed"}),
            status_code=500,
            mimetype="application/json",
        )


# ── HTTP Trigger: Generate executive report ─────────────────────────


@app.function_name("generate_report")
@app.route(route="report", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def generate_report(req: func.HttpRequest) -> func.HttpResponse:
    """Generate a PDF or PPTX executive summary report.

    Request body:
        {"format": "pdf" | "pptx", "agency_id": "..." (optional)}
    """
    try:
        body = req.get_json()
    except ValueError:
        body = {}

    fmt = body.get("format", "pdf")
    agency_filter = body.get("agency_id")

    try:
        if fmt == "pptx":
            content = generate_pptx(agency_filter)
            content_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            filename = "executive-summary.pptx"
        else:
            content = generate_pdf(agency_filter)
            content_type = "application/pdf"
            filename = "executive-summary.pdf"

        return func.HttpResponse(
            body=content,
            mimetype=content_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        log.exception("Report generation error: %s", e)
        return func.HttpResponse(
            json.dumps({"error": "Report generation failed"}),
            status_code=500,
            mimetype="application/json",
        )
