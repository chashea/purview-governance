# Sample Executive Summary

*This is an example of the AI-generated executive summary that the solution produces. In production, this is generated dynamically from live aggregated metrics via Azure OpenAI.*

---

## Statewide Compliance Posture — Executive Summary

**Generated:** February 26, 2026 14:30 UTC
**Agencies Reporting:** 12
**Report Type:** Metadata Only — No PII or Document Content

---

### Statewide Overview

The average Compliance Manager score across all 12 reporting agencies is **64.3%**, ranging from a low of **38.2%** (Department of Corrections) to a high of **89.1%** (Office of the Governor). Five agencies fall below the 60% threshold, indicating significant compliance gaps that require attention.

Average label coverage stands at **61.8%**, with three agencies below 50%. The state recorded **87 DLP incidents** in the last 30 days, concentrated primarily in two agencies.

### Agencies Requiring Immediate Attention

- **Department of Corrections (38.2%)** — Lowest compliance score. Only 34% label coverage. 22 DLP incidents in 30 days. NIST 800-53 assessment shows 43% pass rate. Critical gaps in access control and audit logging controls.

- **Department of Transportation (45.6%)** — Second lowest score. 387 externally shared items with only 41% label coverage. ISO 27001 assessment at 39% pass rate. Retention policy coverage at 30%.

- **Department of Revenue (51.3%)** — Below threshold. 18 DLP incidents in 30 days. 5 high-severity insider risk alerts. HIPAA assessment at 54% — concerning given the department handles taxpayer PII.

### Key Findings

- **Label Coverage Gap:** 4 of 12 agencies have less than 50% label coverage, meaning a majority of their content is unclassified and potentially unprotected
- **DLP Concentration:** 62% of all DLP incidents (54 of 87) originated from just two agencies (Corrections and Revenue)
- **Insider Risk:** 8 high-severity insider risk alerts across all agencies in the last 90 days, with Revenue and Health accounting for 6
- **Retention Gaps:** Average retention policy coverage is 58%, with 3 agencies below 40%

### Recommendations

**Quick Wins (< 1 week):**
- Enable default sensitivity labels for all agencies below 50% label coverage
- Review and re-enable DLP policies that may have been disabled at Corrections and Revenue
- Verify insider risk alert thresholds at Revenue and Health

**Short-Term (1-4 weeks):**
- Deploy auto-labeling policies for common sensitive content types (SSN, financial data) at the 5 lowest-scoring agencies
- Expand retention policies to cover SharePoint and OneDrive at the 3 agencies with < 40% retention coverage
- Schedule Compliance Manager improvement action reviews with agency IT leads

**Strategic (1-3 months):**
- Establish a quarterly compliance review cadence using this dashboard
- Implement mandatory sensitivity label training for agencies below 60% coverage
- Deploy conditional access policies requiring compliant devices for agencies handling CJIS/FERPA data
- Target 75% average compliance score statewide by Q3 2026

---

*All scores referenced are native from Microsoft Purview and Compliance Manager. This report contains metadata only — no document content, PII, or user identities.*
