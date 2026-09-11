from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.query_parser import parse_query

# (query, expected_intent, expected_location_key, temporal, preferred_sensor)
CASES = [
    # FLOOD / SAR / TEMPORAL — English + Hinglish variants
    ("Show flooded areas around Assam between July and August 2025.", "flood_detection", "assam", True, "sar"),
    ("Where did flooding increase in Assam from Jul 2025 to Aug 2025?", "flood_detection", "assam", True, "sar"),
    ("Assam flood extent July vs August 2025", "flood_detection", "assam", True, "sar"),
    ("Map inundated regions near Dhemaji during July and August 2025", "flood_detection", "dhemaji", True, "sar"),
    ("Assam me July se August 2025 ke beech baadh kaha hui?", "flood_detection", "assam", True, "sar"),
    ("Assam mein July aur August 2025 ka flood compare karo", "flood_detection", "assam", True, "sar"),
    ("Show waterlogged zones around Guwahati in August 2025", "flood_detection", "guwahati", False, "sar"),
    ("Show flooded areas near Kaziranga between 2025/07/01 and 2025/08/31", "flood_detection", "kaziranga", True, "sar"),
    ("Map flood around Dibrugarh from 2025-07-01 to 2025-08-31", "flood_detection", "dibrugarh", True, "sar"),
    ("Show inundation in Assam July-August 2025", "flood_detection", "assam", True, "sar"),
    ("Find flood affected regions in Dhemaji from 1 July 2025 to 31 August 2025", "flood_detection", "dhemaji", True, "sar"),
    ("Analyze Sentinel-1 flooding around Assam in Jul/Aug 2025", "flood_detection", "assam", True, "sar"),
    ("असम में जुलाई और अगस्त 2025 के बीच बाढ़ कहाँ बढ़ी?", "flood_detection", "assam", True, "sar"),
    ("गुवाहाटी में अगस्त 2025 के बाढ़ वाले क्षेत्र दिखाओ", "flood_detection", "guwahati", False, "sar"),

    # CHANGE DETECTION
    ("Show urban expansion between these two images", "change_detection", None, True, None),
    ("What changed between 2023 and 2026?", "change_detection", None, True, None),
    ("Compare these images and highlight new construction", "change_detection", None, True, None),
    ("Detect built-up change", "change_detection", None, False, None),
    ("Show changes between the before and after image", "change_detection", None, True, None),
    ("Where did construction increase?", "change_detection", None, False, None),
    ("Detect changes in the two satellite images", "change_detection", None, True, None),
    ("Compare the two dates for urban expansion", "change_detection", None, True, None),

    # VEGETATION
    ("Where was vegetation lost between these dates?", "vegetation_change", None, True, None),
    ("Show forest loss in the two images", "vegetation_change", None, True, None),
    ("Compare NDVI change between the images", "vegetation_change", None, True, None),
    ("Detect green cover loss", "vegetation_change", None, False, None),
    ("How much forest changed between these images?", "vegetation_change", None, True, None),
    ("Show deforestation between the two dates", "vegetation_change", None, True, None),

    # VISION ASSISTANT — semantic questions, no fabricated mask requirement
    ("What is visible in this satellite image?", "vision_question", None, False, None),
    ("Describe this image in simple language", "vision_question", None, False, None),
    ("Is there an airport visible in this image?", "vision_question", None, False, None),
    ("Kya is image me river dikh rahi hai?", "vision_question", None, False, None),
    ("Classify this satellite scene", "vision_question", None, False, None),
    ("What does this image show?", "vision_question", None, False, None),
    ("Can you see roads in this image?", "vision_question", None, False, None),
    ("What kind of land cover is visible?", "vision_question", None, False, None),
    ("What are the most important visible differences between these two satellite images?", "vision_question", None, True, None),
    ("Describe the differences between these two Earth observation images", "vision_question", None, True, None),

    # LANGUAGE-GROUNDED SEGMENTATION / COUNTING
    ("Highlight all buildings in this image", "grounded_segmentation", None, False, None),
    ("Where are the roads?", "grounded_segmentation", None, False, None),
    ("Count the buildings in this image", "grounded_segmentation", None, False, None),
    ("Find all ships in the harbor", "grounded_segmentation", None, False, None),
    ("Mark the solar panels", "grounded_segmentation", None, False, None),
    ("Locate all bridges", "grounded_segmentation", None, False, None),
    ("How many airplanes are visible?", "grounded_segmentation", None, False, None),
    ("Segment the farmland", "grounded_segmentation", None, False, None),
    ("Outline the water regions", "grounded_segmentation", None, False, None),
    ("Find all vehicles", "grounded_segmentation", None, False, None),
    ("इस image में इमारतें highlight करो", "grounded_segmentation", None, False, None),
    ("इस image में सड़कें mark करो", "grounded_segmentation", None, False, None),


    # CAPABILITY GUARDS — must not fabricate unsupported forecasting/impact answers
    ("Predict which parts of Assam will flood next month", "unsupported", "assam", False, None),
    ("Give me a rainfall forecast for tomorrow", "unsupported", None, False, None),
    ("How many people were affected by this flood?", "unsupported", None, False, None),

    # OPTICAL + SAR JOINT / MULTIMODAL ROUTING
    ("Use both optical and SAR images for joint analysis", "multimodal_fusion", None, False, "optical+sar"),
    ("Fuse optical and SAR imagery and explain the land cover", "multimodal_fusion", None, False, "optical+sar"),
    ("Compare SAR and optical evidence in these images", "multimodal_fusion", None, False, "optical+sar"),
    ("Optical aur SAR dono sensor use karke scene explain karo", "multimodal_fusion", None, False, "optical+sar"),
]

failures = []
for text, intent, loc, temporal, sensor in CASES:
    out = parse_query(text, dataset_count=2 if any(w in text.lower() for w in ["two", "these", "before and after"]) else 0)
    got_loc = (out.get("location") or {}).get("key")
    checks = {
        "intent": out["intent"] == intent,
        "location": got_loc == loc,
        "temporal": out["temporal"] == temporal,
        "sensor": out["preferred_sensor"] == sensor,
    }
    if not all(checks.values()):
        failures.append({"query": text, "expected": [intent, loc, temporal, sensor], "got": out, "checks": checks})

# False-positive guards and unknown-place extraction.
guards = [
    (parse_query('Highlight all buildings in this image.', 1)['unresolved_location_text'] is None, 'this image must not be treated as a place'),
    (parse_query('Describe the scene in this image.', 1)['unresolved_location_text'] is None, 'this image must not be geocoded'),
    (parse_query('Show flooded areas around Silchar between July and August 2025.', 0)['unresolved_location_text'] == 'Silchar', 'unknown location phrase should be extracted'),
    (parse_query('Count the buildings in this satellite image.', 1)['target_object'] == 'building', 'building target extraction'),
    (parse_query('Mark the solar panels.', 1)['target_object'] == 'solar panel', 'long object alias extraction'),
    (parse_query('Predict floods next month.', 0)['supported'] is False, 'forecast query must be explicitly unsupported'),
    (parse_query('Analyze this image.', 1)['intent'] == 'image_summary', 'generic image analysis should work when imagery is attached'),
    (parse_query('Hello, what can you do?', 0)['supported'] is False, 'arbitrary non-EO query should not become image statistics'),
]
for ok, note in guards:
    if not ok:
        failures.append({'guard': note})

print(f"Natural-language cases: {len(CASES)} + {len(guards)} guard checks")
print(f"Passed: {len(CASES)+len(guards)-len(failures)}")
print(f"Failed: {len(failures)}")
if failures:
    print(json.dumps(failures, indent=2))
    raise SystemExit(1)
print("NATURAL LANGUAGE TESTS PASS")
