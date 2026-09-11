FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libexpat1 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt "uvicorn[standard]>=0.30"
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu "torch" "torchvision" \
    && echo "torch(cpu) install ok" || echo "torch(cpu) install skipped"
RUN pip install --no-cache-dir -q "huggingface_hub" 2>/dev/null || echo "hf_hub optional"
RUN mkdir -p /app/models/clip && python - <<'PY' && echo "clip bake ok" || (touch /app/models/clip/.missing; echo "clip bake skipped")
import time, pathlib
from huggingface_hub import snapshot_download
for i in range(3):
    try:
        snapshot_download(repo_id="openai/clip-vit-base-patch32", local_dir="/app/models/clip")
        break
    except Exception as e:
        print("download attempt", i, "failed:", e)
        time.sleep(10)
root = pathlib.Path("/app/models/clip")
for p in sorted(root.iterdir()):
    print("file", p.name, p.stat().st_size)
weights = list(root.glob("*.safetensors")) + list(root.glob("pytorch_model.bin"))
if not any(p.stat().st_size > 50_000_000 for p in weights):
    raise SystemExit("clip weights file missing or too small")
print("bake files verified")
PY
RUN python -c "import os; f='/app/models/clip/config.json'; print('clip-model:', 'present' if os.path.exists(f) else 'MISSING')"
COPY app ./app
COPY scripts/bake_demo_data.py ./scripts/bake_demo_data.py
RUN mkdir -p /app/data && python ./scripts/bake_demo_data.py && mkdir -p /app/data/uploads /app/data/previews /app/data/results
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]