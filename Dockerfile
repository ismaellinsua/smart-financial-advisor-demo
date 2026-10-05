# NirKanA for any container host in the EU (Render Frankfurt, a VPS…). Caddy sits in front of Streamlit to add the
# security headers Streamlit cannot set. Secrets come from environment variables (DATABASE_URL, APP_PASSWORD, SMTP_*…).
FROM caddy:2 AS caddy

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PORT=8080
COPY --from=caddy /usr/bin/caddy /usr/local/bin/caddy
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt && useradd --create-home --uid 10001 nirkana
COPY --chown=nirkana .streamlit .streamlit
COPY --chown=nirkana sales_manager sales_manager
COPY --chown=nirkana ops/deploy ops/deploy
USER nirkana
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/_stcore/health', timeout=4)"
CMD ["bash", "ops/deploy/start.sh"]
