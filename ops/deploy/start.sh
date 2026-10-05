#!/usr/bin/env bash
# Streamlit listens only inside the container; Caddy is the one door, on $PORT, and adds the security headers.
set -euo pipefail
streamlit run sales_manager/app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true &
caddy run --config ops/deploy/Caddyfile --adapter caddyfile &
if [[ -n "${STRIPE_WEBHOOK_SECRET:-}" ]]; then
  python ops/deploy/webhook.py &
fi
# If either process stops, stop the container so the host restarts it.
wait -n
exit 1
