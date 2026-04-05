# Regulated Environment Considerations (Lean V1)

This repo demonstrates foundational controls often expected in regulated environments:
- Data boundary: local-only execution
- RBAC: role-based endpoint access
- Audit trail: structured event logs

Not included in Lean V1:
- OIDC/SSO integration (e.g., Okta/Entra/Keycloak)
- Encryption at rest for vector DB
- SIEM integrations
- DLP/PII redaction
- Formal model approval workflows

These can be added in V2+ based on demand.
