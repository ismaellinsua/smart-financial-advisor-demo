# NirKanA for any container host in the EU (Render Frankfurt, a VPS…). Caddy sits in front of Streamlit to add the
# security headers Streamlit cannot set. Secrets come from environment variables (DATABASE_URL, APP_PASSWORD, SMTP_*…).
# Images pinned by digest so every build uses the same bytes; Dependabot proposes updates.
FROM caddy:2@sha256:504a44d7d74bd2bc28a66afc4774912fc21223ca8a67734af1c54ab2f999b489 AS caddy

FROM python:3.14-slim@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170
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
