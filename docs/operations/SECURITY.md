# Security Checklist

## Before Production

- Set a strong `SECRET_KEY` in `.env`.
- Set `SESSION_HTTPS_ONLY=true` when serving over HTTPS.
- Keep `ALLOW_PUBLIC_SIGNUP=false` after the first doctor account is created.
- Prefer PostgreSQL over SQLite for multi-user production use.
- Restrict network exposure with a firewall or reverse proxy.
- Run the app behind HTTPS only.
- Keep Ollama and the OS patched.

## Runbook

- Start the app with `.\start_local.ps1` for the clean tested runtime.
- Check `http://127.0.0.1:8000/healthz` after startup.
- Review audit events in `logs/security_audit.jsonl`.
- Rebuild the knowledge base only from trusted PDF sources.

## Remaining Risks

- This app is hardened, not invulnerable.
- Local session auth is suitable for an internal clinic app, not high-risk internet exposure without a proxy, TLS, and monitoring.
- AI output should still be reviewed by a clinician before treatment decisions.
