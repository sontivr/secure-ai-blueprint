# Lean V1 Principles (Secure On-Prem AI Blueprint)

## Data locality
- Designed to run entirely on a local machine.
- Ollama runs locally; embeddings + vector DB stored on local disk.
- No external API calls are required.

## Access control
- JWT authentication.
- RBAC roles: admin, user.
- Admin-only ingestion and audit summary endpoints.

## Auditability
- Append-only JSONL audit log stored locally.
- Records actor, role, event type, latency, and relevant metadata.

## Threat model assumptions (Lean)
- Single machine, trusted OS user.
- Secrets are stored in environment variables.
- No multi-tenancy or external-facing network exposure in V1.
