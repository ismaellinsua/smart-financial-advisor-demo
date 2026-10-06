#!/usr/bin/env bash
# Streamlit listens only inside the container; Caddy is the one door, on $PORT, and adds the security headers.
set -euo pipefail
# Every business's tables are brought up to date first; if that fails, the container does not start.
python ops/deploy/migrate.py
streamlit run sales_manager/app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true &
caddy run --config ops/deploy/Caddyfile --adapter caddyfile &
python ops/deploy/sessions.py &
if [[ -n "${STRIPE_WEBHOOK_SECRET:-}" ]]; then
  python ops/deploy/webhook.py &
fi
# If either process stops, stop the container so the host restarts it.
wait -n
exit 1
