FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MCP_TRANSPORT=streamable-http MCP_HOST=0.0.0.0
WORKDIR /app
COPY requirements.txt pyproject.toml ./
COPY contribscout ./contribscout
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .
EXPOSE 8000
USER 10001
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT',os.getenv('MCP_PORT','8000'))+'/healthz',timeout=2)"
CMD ["python", "-m", "contribscout.app.main"]
