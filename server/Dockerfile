FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# models_store must exist and be appuser-owned BEFORE the named volume mounts
# over it, or the volume root is created root-owned and checkpoints can't save
RUN mkdir -p /app/models_store && useradd -m appuser && chown -R appuser /app
USER appuser
EXPOSE 8000
# --proxy-headers: honor nginx's X-Forwarded-For so per-IP rate limits key on
# the real client behind the web container's proxy
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
