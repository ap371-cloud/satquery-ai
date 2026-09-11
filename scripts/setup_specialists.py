"""Print reproducible setup guidance for optional specialist repositories.

Large model repositories are intentionally not vendored into SatQuery's ZIP:
weights are large and their dependency stacks conflict. They run as isolated
services and SatQuery discovers them through environment variables.
"""
from textwrap import dedent

print(dedent(r'''
SATQUERY SPECIALIST SETUP
========================

1) General + temporal EO vision assistant — TEOChat
   Repo: https://github.com/ermongroup/TEOChat

   git clone https://github.com/ermongroup/TEOChat.git external/TEOChat
   conda create -n teochat python=3.9 -y
   conda activate teochat
   pip install -e external/TEOChat
   pip install git+https://github.com/facebookresearch/pytorchvideo
   python scripts/teochat_bridge.py

   Main backend env:
   TEOCHAT_URL=http://127.0.0.1:8021

2) SAR semantic VQA — SARChat
   Repo: https://github.com/JimmyMa99/SARChat

   Use one of the published SARChat VLM checkpoints in an isolated environment
   and expose a tiny service contract:
       GET  /health
       POST /vqa  {"query":"...", "image_paths":["..."]}
       -> {"answer":"...", "model":"SARChat-..."}

   Main backend env:
   SARCHAT_URL=http://127.0.0.1:8023

3) Trained bi-temporal change detection — Open-CD
   Repo: https://github.com/likyoo/open-cd

   Follow the official Open-CD installation and choose a model config/checkpoint.
   Then run:
   set OPENCD_MODEL_CONFIG=<path-to-config>       # Windows
   set OPENCD_WEIGHTS=<path-to-checkpoint>
   python scripts/opencd_bridge.py

   Main backend env:
   OPENCD_URL=http://127.0.0.1:8022

4) Language-guided geospatial segmentation — segment-geospatial / SamGeo
   Repo: https://github.com/opengeos/segment-geospatial

   Start the project's REST API and point SatQuery to its root:
   SAMGEO_URL=http://127.0.0.1:<samgeo-port>

5) Large-remote-sensing-image VQA — LRS-VQA
   Repo: https://github.com/VisionXLab/LRS-VQA

   Install it in its recommended isolated GPU environment and expose:
       GET  /health
       POST /vqa {"query":"...", "image_paths":["..."]}
       -> {"answer":"...", "model":"LRS-VQA-..."}

   Main backend env:
   LRSVQA_URL=http://127.0.0.1:8024
   SATQUERY_LARGE_RSI_THRESHOLD=4096

6) Optical + SAR multimodal EO foundation model — TerraMind
   Repo: https://github.com/IBM/terramind

   TerraMind is not a chat server. Fine-tune/select a downstream TerraTorch task
   (for example a Sentinel-1 + Sentinel-2 segmentation task) and expose:
       GET  /health
       POST /fusion {
         "query":"...",
         "optical_path":"...",
         "sar_path":"..."
       }
       -> {
         "answer":"...",
         "model":"TerraMind ...",
         "confidence":0.0-1.0,
         "confidence_type":"multimodal_foundation_model"
       }

   Main backend env:
   TERRAMIND_URL=http://127.0.0.1:8025

SatQuery remains E2E-operational without these heavy services using transparent
local fallbacks. It never claims a specialist model was used when it was not
actually connected.
'''))
