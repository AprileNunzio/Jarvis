FROM nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip ffmpeg libsndfile1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /inference
RUN pip3 install faster-whisper==1.0.3 fastapi==0.110.0 "uvicorn[standard]==0.29.0" python-multipart==0.0.9

COPY server/features/voice_biometrics/inference_service.py /inference/inference_service.py

EXPOSE 8444
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD curl -fsS http://127.0.0.1:8444/health || exit 1
CMD ["uvicorn", "inference_service:app", "--host", "0.0.0.0", "--port", "8444"]
