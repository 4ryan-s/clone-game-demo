# Demo API and the built quiz. The Qwen worker is a separate image (Dockerfile.qwen).
FROM node:20-bookworm-slim AS quiz
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends libsndfile1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
# ONNX_GPU=1 installs the CUDA build so Spectra runs on the GPU. The voice-activity model stays on CPU.
ARG ONNX_GPU=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && if [ "$ONNX_GPU" = "1" ]; then \
         pip uninstall -y onnxruntime \
         && pip install --no-cache-dir "onnxruntime-gpu[cuda,cudnn]==1.32.0"; \
       fi
COPY . .
COPY --from=quiz /src/dist ./frontend/dist
COPY docker/api-entrypoint.sh /entrypoint.sh
EXPOSE 8000
ENTRYPOINT ["sh", "/entrypoint.sh"]
CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
