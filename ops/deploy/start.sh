#!/usr/bin/env bash
# Streamlit listens only inside the container; Caddy is the one door, on $PORT, and adds the security headers.
set -euo pipefail
streamlit run sales_manager/app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true &
caddy run --config ops/deploy/Caddyfile --adapter caddyfile &
# If either process stops, stop the container so the host restarts it.
wait -n
exit 1
