FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libexpat1 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt "uvicorn[standard]>=0.30"
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu "torch" "torchvision" \
    && echo "torch(cpu) install ok" || echo "torch(cpu) install skipped"
RUN pip install --no-cache-dir -q "huggingface_hub" 2>/dev/null || echo "hf_hub optional"
RUN mkdir -p /app/models/florence2 && python - <<'PY' && echo "florence bake ok" || (touch /app/models/florence2/.missing; echo "florence bake skipped")
from huggingface_hub import snapshot_download
snapshot_download(repo_id="microsoft/Florence-2-base", local_dir="/app/models/florence2")
PY
RUN python -c "import os; f='/app/models/florence2/config.json'; print('florence-model:', 'present' if os.path.exists(f) else 'MISSING')"
COPY app ./app
COPY scripts/bake_demo_data.py ./scripts/bake_demo_data.py
RUN mkdir -p /app/data && python ./scripts/bake_demo_data.py && mkdir -p /app/data/uploads /app/data/previews /app/data/results
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]