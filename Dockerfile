# Imagem oficial do Playwright: já traz o Chromium e as dependências do sistema
FROM mcr.microsoft.com/playwright/python:v1.56.0-noble

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY smr_monitor ./smr_monitor

ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "smr_monitor"]
