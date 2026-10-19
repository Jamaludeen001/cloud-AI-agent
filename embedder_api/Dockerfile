FROM python:3.11-slim

WORKDIR /app

RUN pip install fastapi uvicorn sentence-transformers pydantic torch

COPY main.py .

ENV HF_HOME=/app/hf_cache

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]