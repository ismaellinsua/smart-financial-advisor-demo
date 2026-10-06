# NirKanA for any container host in the EU (Render Frankfurt, a VPS…). Caddy sits in front of Streamlit to add the
# security headers Streamlit cannot set. Secrets come from environment variables (DATABASE_URL, APP_PASSWORD, SMTP_*…).
# Images pinned by digest so every build uses the same bytes; Dependabot proposes updates.
FROM caddy:2@sha256:8dc9fa87b36b25303d1c67d2a09f5824b7f3bfd72cb052f246e5da2133fe29a8 AS caddy

FROM python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d
# REQUIRE_DATABASE: the container's disk is wiped on every deploy, so the app refuses to keep data on it.
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PORT=8080 REQUIRE_DATABASE=1
COPY --from=caddy /usr/bin/caddy /usr/local/bin/caddy
WORKDIR /app
COPY requirements.lock .
# --require-hashes: a package that differs from the reviewed one by a single byte is refused.
RUN pip install --require-hashes -r requirements.lock && useradd --create-home --uid 10001 nirkana
COPY --chown=nirkana .streamlit .streamlit
COPY --chown=nirkana sales_manager sales_manager
COPY --chown=nirkana ops/deploy ops/deploy
USER nirkana
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/_stcore/health', timeout=4)"
CMD ["bash", "ops/deploy/start.sh"]
