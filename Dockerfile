FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MCP_TRANSPORT=streamable-http MCP_HOST=0.0.0.0 MCP_PORT=8000
WORKDIR /app
COPY requirements.txt pyproject.toml ./
COPY contribscout ./contribscout
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .
EXPOSE 8000
USER 10001
CMD ["python", "-m", "contribscout.app.main"]
