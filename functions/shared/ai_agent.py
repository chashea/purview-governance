"""
AI Executive Agent — runs within Azure Commercial boundary.

Uses Azure OpenAI (*.openai.azure.com) with Managed Identity to generate
executive summaries from aggregated Table Storage metrics.

Reads only metadata (counts, percentages, scores) — never PII or content.
"""

import json
import logging

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

from shared.config import get_settings
from shared.table_client import read_assessment_summaries, read_latest_snapshots_all_agencies

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an AI governance advisor for a state government CISO overseeing Microsoft
Purview and Compliance Manager across multiple agencies in M365 GCC.

You analyze aggregated metadata (never PII or content) to:
1. Identify agencies with the lowest compliance scores and explain why they need attention
2. Highlight trends in label coverage, DLP incidents, and compliance scores
3. Recommend specific, actionable next steps prioritized by impact
4. Generate executive summaries suitable for legislative/cabinet briefings

Data available (injected as context):
- Agency posture snapshots (compliance scores, label coverage, DLP, sharing, retention)
- Compliance Manager assessment summaries (per regulation per agency)

Guidelines:
- Lead with the statewide compliance posture (average score and range)
- Call out any agency with compliance score below 50% as requiring immediate attention
- Reference specific numbers from the data — never fabricate metrics
- Keep executive summaries under 400 words
- Use bullet points for clarity
- Classify recommendations as Quick Win (< 1 week), Short-Term (1-4 weeks), Strategic (1-3 months)
- All scores referenced are native from Microsoft Purview and Compliance Manager
"""


def _get_openai_client() -> AzureOpenAI:
    settings = get_settings()
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://cognitiveservices.azure.com/.default",
    )
    return AzureOpenAI(
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        azure_ad_token_provider=token_provider,
        api_version=settings.AZURE_OPENAI_API_VERSION,
    )


def _build_context(agency_filter: str | None = None) -> str:
    """Build the data context string from Table Storage."""
    parts = []

    # Agency snapshots
    snapshots = read_latest_snapshots_all_agencies()
    if agency_filter:
        snapshots = [s for s in snapshots if s.get("PartitionKey") == agency_filter]

    # Sort by compliance score ascending (lowest first = most attention needed)
    snapshots.sort(key=lambda s: s.get("ComplianceScorePct", 0))

    # Summarize statewide
    if snapshots:
        scores = [s.get("ComplianceScorePct", 0) for s in snapshots]
        parts.append(
            f"## Statewide Summary\n"
            f"- Total agencies reporting: {len(snapshots)}\n"
            f"- Average compliance score: {sum(scores) / len(scores):.1f}%\n"
            f"- Range: {min(scores):.1f}% to {max(scores):.1f}%\n"
            f"- Total DLP incidents (30d): {sum(s.get('DlpIncidents30d', 0) for s in snapshots)}\n"
            f"- Average label coverage: {sum(s.get('LabelCoveragePct', 0) for s in snapshots) / len(snapshots):.1f}%"
        )

    # Agency details (top 20)
    parts.append(f"## Agency Snapshots (sorted by compliance score, lowest first)\n{json.dumps(snapshots[:20], indent=2, default=str)}")

    # Assessment summaries
    assessments = read_assessment_summaries(agency_filter)
    if assessments:
        parts.append(f"## Compliance Assessments\n{json.dumps(assessments[:30], indent=2, default=str)}")

    return "\n\n".join(parts)


def ask_executive_agent(question: str, agency_filter: str | None = None) -> dict:
    """Query the AI executive agent.

    Args:
        question: The user's question or request.
        agency_filter: Optional agency_id to scope the context.

    Returns:
        {"answer": str, "model": str, "usage": {"prompt_tokens": int, "completion_tokens": int}}
    """
    client = _get_openai_client()
    settings = get_settings()
    context = _build_context(agency_filter)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"DATA CONTEXT:\n{context}\n\nQUESTION: {question}"},
    ]

    response = client.chat.completions.create(
        model=settings.AZURE_OPENAI_DEPLOYMENT,
        messages=messages,
        temperature=0.2,
        max_tokens=2048,
    )

    return {
        "answer": response.choices[0].message.content,
        "model": response.model,
        "usage": {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
        },
    }
