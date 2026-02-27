"""
CLI entrypoint for the per-tenant metadata collector.

Usage:
    purview-collect --tenant-id <GUID> --agency-id <NAME>
    purview-collect --tenant-id <GUID> --agency-id <NAME> --dry-run
"""

import json
import logging
import sys

import click

from collector.auth import get_graph_token
from collector.compliance_client import (
    get_assessments,
    get_compliance_score,
    get_improvement_actions_summary,
)
from collector.config import CollectorSettings
from collector.payload import PurviewPosturePayload
from collector.purview_client import (
    get_dlp_incidents,
    get_external_sharing_count,
    get_insider_risk_trend,
    get_label_coverage,
    get_retention_policy_coverage,
    get_sensitivity_labels,
)
from collector.submit import submit_payload

log = logging.getLogger("collector")


@click.command()
@click.option("--tenant-id", envvar="TENANT_ID", help="Target tenant GUID")
@click.option("--agency-id", envvar="AGENCY_ID", help="Logical agency identifier")
@click.option("--dry-run", is_flag=True, help="Collect and print payload without submitting")
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
def main(tenant_id: str, agency_id: str, dry_run: bool, verbose: bool):
    """Collect Purview & Compliance Manager metadata from a GCC tenant."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    # Load settings (reads from .env + environment variables)
    overrides = {}
    if tenant_id:
        overrides["TENANT_ID"] = tenant_id
    if agency_id:
        overrides["AGENCY_ID"] = agency_id

    try:
        settings = CollectorSettings(**overrides)
    except Exception as e:
        click.echo(f"Configuration error: {e}", err=True)
        sys.exit(1)

    click.echo(f"Collecting metadata from tenant {settings.TENANT_ID} (agency: {settings.AGENCY_ID})")

    # Authenticate
    try:
        token = get_graph_token(settings)
    except RuntimeError as e:
        click.echo(f"Authentication failed: {e}", err=True)
        sys.exit(1)

    graph_base = settings.graph_base
    click.echo(f"Authenticated. Using Graph API at {graph_base}")

    # Collect Purview metadata
    click.echo("Collecting Purview metadata...")
    labels = get_sensitivity_labels(graph_base, token)
    coverage = get_label_coverage(graph_base, token)
    dlp = get_dlp_incidents(graph_base, token)
    external_sharing = get_external_sharing_count(graph_base, token)
    retention = get_retention_policy_coverage(graph_base, token)
    insider_risk = get_insider_risk_trend(graph_base, token)

    # Collect Compliance Manager metadata
    click.echo("Collecting Compliance Manager metadata...")
    score = get_compliance_score(graph_base, token)
    assessments = get_assessments(graph_base, token)
    actions = get_improvement_actions_summary(graph_base, token)

    # Build payload
    payload = PurviewPosturePayload(
        tenant_id=settings.TENANT_ID,
        agency_id=settings.AGENCY_ID,
        timestamp=PurviewPosturePayload.now_iso(),
        label_coverage_pct=coverage["coverage_pct"],
        unlabeled_sensitive_count=coverage["unlabeled_sensitive_count"],
        dlp_incidents_30d=dlp["last_30d"],
        dlp_incidents_60d=dlp["last_60d"],
        dlp_incidents_90d=dlp["last_90d"],
        external_sharing_count=external_sharing,
        retention_policy_count=retention["policies_count"],
        retention_coverage_pct=retention["coverage_pct"],
        insider_risk_high=insider_risk["high"],
        insider_risk_medium=insider_risk["medium"],
        insider_risk_low=insider_risk["low"],
        insider_risk_total=insider_risk["total"],
        label_taxonomy=labels,
        compliance_score_current=score["current_score"],
        compliance_score_max=score["max_score"],
        assessments=assessments,
        improvement_actions_implemented=actions["implemented"],
        improvement_actions_planned=actions["planned"],
        improvement_actions_not_started=actions["not_started"],
    )

    payload_dict = payload.to_dict()

    if dry_run:
        click.echo("\n--- DRY RUN: Payload (not submitted) ---")
        click.echo(json.dumps(payload_dict, indent=2, default=str))
        return

    # Submit to Function App
    click.echo("Submitting payload to Function App...")
    try:
        result = submit_payload(payload_dict, settings)
        click.echo(f"Success: {json.dumps(result)}")
    except Exception as e:
        click.echo(f"Submission failed: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
