# SatQuery EO-VLM Service (`services/teochat_service`)

An isolated HTTP service that runs a **real remote-sensing vision-language
model**. SatQuery's GIS backend talks to it over HTTP, so the two environments
never fight over torch/transformers pins.

## What runs here

| Backend  | Real checkpoint | Where it runs |
|----------|-----------------|---------------|
| `teochat` | `jirvin16/TEOChat` (Video-LLaVA 7B) | CUDA host w/ official TEOChat env |
| `cpu-vlm` | `Qwen/Qwen2-VL-2B-Instruct` (override with `TEOCHAT_CPU_VLM`) | genuinely on CPU |
| `cpu-vlm` | any transformers VLM you set via `TEOCHAT_CPU_VLM` | genuinely on CPU |

**Honesty contract:** the model is always self-identified by its real name in
`model_name` / `model_version` (HF commit sha). A CPU-run model is **never**
labeled "TEOChat". `GET /health` reports `status: ready` **only** after the
checkpoint is loaded **and** a real smoke inference succeeded.

## Run the CPU path (any machine with RAM)

```bash
pip install -r requirements.txt
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu   # if needed
set    PORT=8021
python app.py
```

First `/vqa` or `/smoke` downloads the checkpoint (~4.5 GB, then cached). On a
typical CPU laptop: load ~5–10 min, one debug inference ~45 s (192 tokens).

```bash
# 1) wait until model is loaded (model_loaded: true)
curl http://127.0.0.1:8021/health
# 2) run a real warm-up inference (upgrades status -> ready)
curl -X POST http://127.0.0.1:8021/smoke
# 3) ask a question
curl -X POST http://127.0.0.1:8021/vqa \
  -F image=@scene.tif -F "question=What land cover is present?"
```

`/vqa` also accepts the old JSON contract `{"query","image_paths"}` for
backward compatibility with `scripts/teochat_bridge.py`.

## Run the real TEOChat checkpoint (CUDA)

TEOChat pins an old CUDA torch stack and Python 3.9, so use its own env:

```bash
conda create -n teochat python=3.9 -y && conda activate teochat
git clone https://github.com/ermongroup/TEOChat && cd TEOChat
pip install -e .            # installs its pinned torch
# place backend/app/model.py + app.py in this env, or reuse scripts/teochat_bridge.py
PORT=8021 TEOCHAT_ENGINE=teochat TEOCHAT_MODEL=jirvin16/TEOChat python app.py
```

Remote GPU options: a RunPod / Vast.ai / Colab instance, or `ssh -L 8021` to a
workstation. Set `TEOCHAT_URL=http://<gpu-host>:8021` in SatQuery — routing
auto-detects the `teochat` backend.

## SAR safety rule

SAR (e.g. VV/VH) rasters are refused *before* inference with a `declined_block`
of `code: sar` plus a clear reason. SatQuery also gates SAR inputs at the router
so an optical-semantics model is never asked to invent radar-based meaning.

## Response contract (per request)

```json
{
  "answer": "...",
  "model_name": "Qwen/Qwen2-VL-2B-Instruct",
  "model_version": "<hf-commit-sha>",
  "model_backed": true,
  "fallback_used": false,
  "latency_ms": 46231,
  "model_confidence": null,
  "images_used": 1,
  "backend": "cpu-vlm",
  "device": "cpu",
  "dtype": "bfloat16",
  "preprocessing": [{ "width": 512, "height": 384, "...": "..." }]
}
```

Soft-declines (blank / tiny / mostly-NoData / corrupt / SAR) return HTTP 200
with `"answer": null`, `"fallback_used": true` and a `declined_block` containing
`code` + `reason`, so SatQuery falls back to its local statistics baseline
truthfully.

## Health states

`GET /health` fields: `status` (`unavailable` -> `loading` -> `ready`),
`model_loaded`, `smoke_inference`, `backend`, `model_name`, `model_version`,
`device`, `dtype`, `load_count`, `inference_count`, `load_ms`,
`last_inference_ms`, `process_memory_mb`. A `ready` status is the only thing
SatQuery accepts as "model-backed Vision ready".