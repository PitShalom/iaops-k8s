FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 APP_DIR=/app
WORKDIR /app

# Node + Claude Code CLI: backend "cli" (assinatura) usa `claude -p` em modo headless
RUN apt-get update \
 && apt-get install -y --no-install-recommends nodejs npm ca-certificates \
 && npm install -g @anthropic-ai/claude-code \
 && npm cache clean --force \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY skills/ ./skills/
COPY rag/ ./rag/
COPY config/ ./config/

ENV PYTHONPATH=/app/src HOME=/home/agent
RUN useradd -r -m -d /home/agent -u 10001 agent && mkdir -p /data && chown agent /data
USER agent

EXPOSE 8080
CMD ["uvicorn", "aiops_agent.main:app", "--host", "0.0.0.0", "--port", "8080"]
