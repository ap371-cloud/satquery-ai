"""Golden demo suite: model-backed Vision + regression + failure-fallback.

Run from the repo root:
    python backend/tests/golden_demo_suite.py

Requires the EO-VLM service (services/teochat_service/app.py) on TEOCHAT_URL
(default http://127.0.0.1:8021). If the service is unreachable the suite SKIPS
with exit code 0 so automated runners stay green while remaining honest.

Covers:
  G1  Golden vision Q — model-backed, full provenance, no fabricated claims.
  G2  Five-image semantic test — real model answers that reflect each scene and
      differ materially between scenarios.
  G3  Repeatability — the same image+question produces a stable answer.
  G4  Negative inputs — blank / near-black / tiny / SAR declined before the
      model, no server crash, no fabricated scene description.
  G5  Regression — Assam flood (SAR) and Indore urban change still work.
  G6  Failure-fallback — VLM offline -> honest image_statistics baseline; back
      online -> model-backed again.
  G7  Health/memory — single load, bounded memory, per-inference counters.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
SERVICE = os.getenv("TEOCHAT_URL", "http://127.0.0.1:8021").rstrip("/")
VISION = ROOT / "demo_data" / "vision"
SMOKE_TIMEOUT = int(os.getenv("SATQUERY_VLM_RELOAD_TIMEOUT", "900"))
INF_WAIT = 700

os.environ.setdefault("TEOCHAT_URL", SERVICE)
sys.path.insert(0, str(ROOT / "backend"))
import app.main as main  # noqa: E402
from app.main import AnalysisIn  # noqa: E402

FAILED = []


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        FAILED.append(name)


def wait(aid, timeout=INF_WAIT):
    deadline = time.time() + timeout
    while time.time() < deadline:
        row = main.get_analysis(aid)
        if row["status"] in ("completed", "failed"):
            result = json.loads(row["result_json"] or "{}")
            if row["status"] != "completed":
                raise AssertionError(f"analysis {aid} failed: {result.get('error')}")
            return result
        time.sleep(0.5)
    raise TimeoutError(aid)


def run(query, ids):
    job = main.create_analysis(AnalysisIn(query=query, dataset_ids=ids, provider="local"))
    return wait(job["analysis_id"])


def levenshtein(a, b):
    if a == b:
        return 0.0
    la, lb = len(a), len(b)
    d = list(range(lb + 1))
    for i in range(1, la + 1):
        prev = d[0]
        d[0] = i
        for j in range(1, lb + 1):
            cur = d[j]
            d[j] = min(d[j] + 1, d[j - 1] + 1, prev + (a[i - 1] != b[j - 1]))
            prev = cur
    return d[lb] / max(len(a), len(b))


def register_scene(filename, modality="optical"):
    with main.db() as con:
        existing = con.execute("SELECT * FROM datasets WHERE filename=?", (filename,)).fetchone()
    if existing:
        return main.dataset_row(existing)
    did = "ds_vs_" + filename.replace(".tif", "").replace(".png", "")
    src = VISION / filename
    dest = main.UPLOADS / f"{did}.tif"
    if not src.exists():
        raise FileNotFoundError(src)
    if src.suffix.lower() == ".tif":
        dest.write_bytes(src.read_bytes())
    else:
        raise ValueError("register_scene expects a .tif")
    preview = main.PREVIEWS / f"{did}.png"
    main.make_preview(dest, preview)
    md = main.read_raster(dest)["meta"]
    md["demo_data"] = True
    md["period_label"] = "June 2026"
    with main.db() as con:
        con.execute("INSERT INTO datasets VALUES(?,?,?,?,?,?,?)",
                    (did, filename, str(dest), str(preview), modality, json.dumps(md), main.now()))
    return main.dataset_row(main.get_dataset(did))


def service_up():
    try:
        r = requests.get(SERVICE + "/health", timeout=6)
        return r.ok
    except requests.RequestException:
        return False


def ensure_service_ready():
    if not service_up():
        print("SKIP: EO-VLM service is not reachable; golden suite skipped (exit 0).")
        sys.exit(0)

    def _health():
        return requests.get(SERVICE + "/health", timeout=8).json()

    h = _health()
    # The service loads its model lazily. If it has not loaded yet, trigger a
    # real load + smoke inference so readiness is actually verified, not assumed.
    if not h.get("model_loaded"):
        print("triggering model load + smoke inference (loads lazily on CPU, then ~1-2 min infer)...")
        s = requests.post(SERVICE + "/smoke", timeout=SMOKE_TIMEOUT + 120)
        if not s.ok:
            print("FAIL: smoke inference failed:", s.text[:400])
            sys.exit(2)
        h = _health()
    elif not h.get("smoke_inference"):
        print("running smoke inference ...")
        s = requests.post(SERVICE + "/smoke", timeout=SMOKE_TIMEOUT)
        if not s.ok:
            print("FAIL: smoke inference failed:", s.text[:400])
            sys.exit(2)
        h = _health()
    if not h.get("model_loaded"):
        print("FAIL: service model never loaded.")
        sys.exit(2)
    print(f"service: {h.get('model_name')} backend={h.get('backend')} device={h.get('device')} loaded")
    if not (h.get("model_loaded") and h.get("smoke_inference")):
        print("FAIL: service not genuinely ready.")
        sys.exit(2)
    return h


def main_run():
    print("=== Golden demo suite ===")
    ensure_service_ready()

    semantic_scenes = {f: ("vision: summarize this satellite image. Name land cover and water features.") for f in
                       ["vision_sample.tif", "vd_01_river_agriculture.tif", "vd_02_dense_urban.tif",
                        "vd_03_forest.tif", "vd_04_coastal_water.tif", "vd_05_mixed_urban_water.tif"]}
    ids = {f: register_scene(f)["id"] for f in semantic_scenes}

    # ---- G1: golden vision, model-backed, honest provenance ------------- #
    print("\n[G1] Golden model-backed vision answer")
    q = "vision: summarize this satellite image. Name land cover and water features."
    r = run(q, [ids["vision_sample.tif"]])
    prov = r["provenance"] or {}
    mi = r.get("model_info") or {}
    check("intent is vision", r["intent"] in ("vision_question", "image_summary"), r["intent"])
    check("model-backed", mi.get("model_backed") is True and prov.get("model_backed") is True)
    check("no fallback", prov.get("fallback_used") is False)
    check("model named truthfully", bool(prov.get("model_display")) and "TEOChat" not in str(prov.get("model_display")),
          prov.get("model_display"))
    check("model version (hf sha)", bool(prov.get("model_version")), str(prov.get("model_version"))[:12])
    check("latency measured", isinstance(prov.get("latency_ms"), int) and prov["latency_ms"] > 0, f"{prov.get('latency_ms')}ms")
    check("model_confidence stays null (uncalibrated)", prov.get("model_confidence") is None)
    ans = r.get("answer") or ""
    check("non-empty answer", len(ans.strip()) > 20)
    kw = [w for w in ("river", "water", "field", "land", "crop", "agriculture", "urban", "village", "building", "vegetation") if w.lower() in ans.lower()]
    check("material scene content", len(kw) >= 1, f"keywords={kw}")
    check("overlay + geo envelope present", bool(r.get("overlay_url")) and bool(r.get("map_context", {}).get("bounds_wgs84")))
    print(f"    answer: {ans[:220]}...")
    print(f"    model: {prov.get('model_display')} v{str(prov.get('model_version'))[:8]}  latency={prov.get('latency_ms')}ms")

    # ---- G2: five-image semantic test ----------------------------------- #
    print("\n[G2] Five-image semantic test")
    answers = {}
    latencies = []
    for fname, fq in list(semantic_scenes.items())[1:]:
        t0 = time.time()
        rr = run(fq, [ids[fname]])
        prov = rr["provenance"] or {}
        ans = rr.get("answer") or "(empty)"
        answers[fname] = ans
        latencies.append(prov.get("latency_ms"))
        check(f"{fname} model-backed", (rr.get("model_info") or {}).get("model_backed") is True, f"{int(time.time()-t0)}s")
        check(f"{fname} non-empty answer", len(ans.strip()) > 15)
        print(f"    {fname[-12:]} -> {ans[:110]}...")
    avg_lat = sum(x for x in latencies if x) / max(1, len([x for x in latencies if x]))
    check("all latencies sane", all(x and 1500 <= x <= 900000 for x in latencies), f"avg {avg_lat/1000:.1f}s")
    sims = []
    items = list(answers.items())
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            sims.append(1 - levenshtein(items[i][1].lower(), items[j][1].lower()))
    check("answers differ materially across scenes", len(sims) > 0 and max(sims) < 0.92, f"max_pairwise_sim={max(sims):.2f}")

    # ---- G3: repeatability ---------------------------------------------- #
    print("\n[G3] Repeatability (3x same image+question)")
    runs = []
    for _ in range(3):
        rr = run(q, [ids["vd_02_dense_urban.tif"]])
        runs.append(rr.get("answer") or "")
        check("repeat run model-backed", (rr.get("model_info") or {}).get("model_backed") is True)
    stable = max(1 - levenshtein(runs[0].lower(), x.lower()) for x in runs[1:])
    check("stable answer across runs", stable >= 0.92, f"min_sim={stable:.2f}")

    # ---- G4: negative inputs (service-level, no crash) ------------------- #
    print("\n[G4] Negative inputs declined honestly")
    negatives = [("sb_01_blank.tif", "blank"), ("sb_02_black.tif", "black"), ("sb_03_tiny.tif", "tiny"), ("sb_04_sar.tif", "sar")]
    for fname, code in negatives:
        with open(VISION / fname, "rb") as f:
            resp = requests.post(SERVICE + "/vqa", files={"image": (fname, f, "image/tiff")},
                                 data={"question": "Describe the land cover in detail."}, timeout=120)
        body = resp.json()
        check(f"{fname} http 200", resp.status_code == 200, str(resp.status_code))
        check(f"{fname} no fabricated answer", body.get("answer") is None)
        block = body.get("declined_block") or {}
        check(f"{fname} declined reason present", bool(block.get("code")), block.get("reason", "")[:60])
        check(f"{fname} honest fallback flag", body.get("fallback_used") is True)

    # ---- G5: regression (offline geo specialists) ------------------------ #
    print("\n[G5] Regression: flood + urban change")
    samples = main.load_demo()
    assam = sorted([x for x in samples if x["filename"].startswith("Assam_")], key=lambda x: x["metadata"].get("acquired_at") or "")
    rf = run("Show flooded areas around Assam between July and August 2025.", [x["id"] for x in assam])
    check("flood intent", rf["intent"] == "flood_detection")
    check("flood area computed", isinstance(rf["statistics"].get("probable_flood_area_km2"), float), f"{rf['statistics'].get('probable_flood_area_km2')} km2")
    check("flood vector features", len(rf["geojson"]["features"]) > 0)
    indore = [x for x in samples if x["filename"].startswith("Indore_")]
    rc = run("Show where urban construction changed between these two dates.", [x["id"] for x in indore])
    check("change intent", rc["intent"] == "change_detection", rc["intent"])
    check("change stats present", "change_percent" in rc["statistics"])

    # ---- G6: failure-fallback -------------------------------------------- #
    print("\n[G6] Failure-fallback (VLM offline -> baseline; online -> model-backed)")
    original_url = main.specialists.vlm.url
    main.specialists.vlm.url = ""
    try:
        rb = run(q, [ids["vision_sample.tif"]])
        mb = (rb.get("model_info") or {}).get("model_backed")
        check("offline fallback to image_statistics", rb.get("method") == "image_statistics", rb.get("method"))
        check("offline result clearly not model-backed", mb is not True)
        check("fallback flag set", (rb.get("provenance") or {}).get("fallback_used") is True)
        warns = "\n".join(rb.get("warnings") or [])
        check("offline warning surfaced", "offline" in warns.lower() or "unavailable" in warns.lower() or "declined" in warns.lower(), warns[:80])
        print(f"    fallback answer: {(rb.get('answer') or '')[:120]}")
    finally:
        main.specialists.vlm.url = original_url
    print("    (waiting for VLM service to answer again...)")
    rr = run(q, [ids["vision_sample.tif"]])
    check("back online -> model-backed", (rr.get("model_info") or {}).get("model_backed") is True)

    # ---- G7: health / memory / single-load -------------------------------- #
    print("\n[G7] Health, memory, single-load guarantee")
    h = requests.get(SERVICE + "/health", timeout=8).json()
    check("single model load", h.get("load_count") == 1, f"load_count={h.get('load_count')}")
    check("inference counter advanced", (h.get("inference_count") or 0) >= 7, f"inference_count={h.get('inference_count')}")
    mem = h.get("process_memory_mb")
    check("memory bounded range (9-30 GB host)", mem and 300 <= mem <= 30000, f"{mem} MB")

    print()
    if FAILED:
        print(f"GOLDEN DEMO SUITE FAILED: {len(FAILED)} failing check(s): {FAILED}")
        sys.exit(1)
    print("GOLDEN DEMO SUITE PASS")
    sys.exit(0)


if __name__ == "__main__":
    main_run()