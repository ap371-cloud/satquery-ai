from __future__ import annotations

import calendar
import re
from typing import Any, Dict, List, Optional, Tuple

MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})
MONTHS.update({"जनवरी": 1, "फरवरी": 2, "मार्च": 3, "अप्रैल": 4, "मई": 5, "जून": 6, "जुलाई": 7, "अगस्त": 8, "सितंबर": 9, "अक्टूबर": 10, "नवंबर": 11, "दिसंबर": 12})

# Offline gazetteer for reliable demo/India flows. Unknown place phrases are
# returned as unresolved_location_text and can be resolved online at runtime.
LOCATIONS: Dict[str, Dict[str, Any]] = {
    "assam": {
        "name": "Assam, India",
        "bbox": [89.65, 24.05, 96.05, 28.35],
        "analysis_bbox": [94.42, 27.45, 95.02, 27.88],
        "coverage_note": "Interactive analysis uses a bounded flood-prone AOI in upper Assam; state-wide runs should be tiled/mosaicked.",
    },
    "dhemaji": {
        "name": "Dhemaji, Assam, India",
        "bbox": [94.15, 27.05, 95.35, 28.15],
        "analysis_bbox": [94.42, 27.45, 95.02, 27.88],
    },
    "guwahati": {
        "name": "Guwahati, Assam, India",
        "bbox": [91.55, 25.98, 91.95, 26.28],
        "analysis_bbox": [91.60, 26.02, 91.90, 26.25],
    },
    "dibrugarh": {
        "name": "Dibrugarh, Assam, India",
        "bbox": [94.55, 27.20, 95.15, 27.70],
        "analysis_bbox": [94.65, 27.28, 95.05, 27.62],
    },
    "kaziranga": {
        "name": "Kaziranga National Park, Assam, India",
        "bbox": [92.95, 26.47, 93.75, 26.78],
        "analysis_bbox": [93.05, 26.53, 93.65, 26.73],
    },
    "indore": {
        "name": "Indore, Madhya Pradesh, India",
        "bbox": [75.65, 22.55, 76.00, 22.85],
        "analysis_bbox": [75.70, 22.62, 75.94, 22.80],
    },
}

LOCATION_ALIASES = {
    "असम": "assam",
    "धेमाजी": "dhemaji",
    "गुवाहाटी": "guwahati",
    "डिब्रूगढ़": "dibrugarh",
    "काजीरंगा": "kaziranga",
    "इंदौर": "indore",
}

OBJECT_ALIASES = {
    "building": ["building", "buildings", "house", "houses", "rooftop", "rooftops", "structure", "structures", "ghar", "इमारत", "इमारतें", "मकान"],
    "road": ["road", "roads", "highway", "highways", "street", "streets", "sadak", "सड़क", "सड़कें"],
    "water": ["water", "river", "rivers", "lake", "lakes", "pond", "ponds", "paani", "जल", "नदी", "पानी"],
    "tree": ["tree", "trees", "forest", "forests", "vegetation", "green cover", "ped", "पेड़"],
    "vehicle": ["vehicle", "vehicles", "car", "cars", "truck", "trucks"],
    "ship": ["ship", "ships", "boat", "boats", "vessel", "vessels"],
    "airplane": ["airplane", "airplanes", "aircraft", "planes"],
    "airport": ["airport", "airports", "airfield", "runway", "runways"],
    "bridge": ["bridge", "bridges"],
    "farmland": ["farmland", "farm", "farms", "crop", "crops", "agriculture", "agricultural field", "fields"],
    "solar panel": ["solar panel", "solar panels", "solar farm", "solar farms"],
    "stadium": ["stadium", "stadiums", "sports field", "sports fields"],
}


def _has_any(q: str, phrases: List[str]) -> bool:
    return any(p in q for p in phrases)


def _target_object(query: str) -> Optional[str]:
    q = query.lower()
    # longest aliases first so "solar panels" wins over generic tokens
    candidates: List[Tuple[int, str]] = []
    for canonical, aliases in OBJECT_ALIASES.items():
        for alias in aliases:
            idx = q.find(alias)
            if idx >= 0:
                candidates.append((len(alias), canonical))
    return max(candidates, default=(0, None))[1]


def _unsupported_reason(query: str) -> Optional[str]:
    """Return a clear reason for requests the current EO analysis stack cannot support.

    This guard prevents arbitrary natural-language questions from silently falling
    through to an image-statistics response. It is deliberately conservative and
    only blocks capabilities that require models/data SatQuery does not ship.
    """
    q = query.lower().strip()
    future_cues = [
        "forecast", "predict next", "predict future", "future flood", "next month",
        "next week", "tomorrow", "will it flood", "will flood", "when will flood",
        "weather forecast", "rainfall forecast", "cyclone forecast", "crop yield forecast",
        "भविष्य", "अगले महीने", "कल बाढ़", "पूर्वानुमान",
    ]
    realtime_cues = [
        "live now", "real-time now", "real time now", "right now live", "send alert",
        "notify me", "continuous monitoring", "monitor continuously",
    ]
    impact_cues = [
        "how many people affected", "how many people were affected", "people were affected", "population affected", "economic loss", "financial loss",
        "damage cost", "casualties", "death toll",
    ]
    if _has_any(q, future_cues):
        return "Forecasting is not enabled. SatQuery currently analyzes observed Earth-observation imagery; it does not predict future floods, weather, or crop yield."
    if _has_any(q, realtime_cues):
        return "Continuous real-time alerting is not enabled in this build. SatQuery can analyze selected or retrieved satellite scenes on demand."
    if _has_any(q, impact_cues):
        return "Population/economic impact estimation is not enabled because this build does not include authoritative population, asset, or damage layers."
    return None


def _intent(query: str, dataset_count: int = 0) -> str:
    q = query.lower().strip()
    target = _target_object(query)

    if _unsupported_reason(query):
        return "unsupported"

    # Flood/water temporal analysis must win before generic water segmentation.
    if _has_any(q, ["flood", "flooded", "flooding", "inundat", "waterlogged", "water logging", "baadh", "badh", "बाढ़", "जलभराव"]):
        return "flood_detection"

    # Explicit vegetation temporal change.
    if _has_any(q, ["vegetation loss", "forest loss", "deforestation", "green cover loss", "ndvi change", "vegetation change", "forest change"]):
        return "vegetation_change"
    if _has_any(q, ["vegetation", "forest", "green cover", "ndvi", "वन", "पेड़"]) and _has_any(q, ["between", "change", "loss", "lost", "decrease", "increase", "compare", "vs", "versus"]):
        return "vegetation_change"

    # Explicit optical + SAR joint reasoning / fusion. Keep this before generic
    # change detection so a cross-modal request is not collapsed into abs-diff.
    multimodal_cues = [
        "optical and sar", "sar and optical", "optical + sar", "sar + optical",
        "use both optical", "use both sar", "fuse optical", "fuse sar",
        "joint optical", "joint sar", "cross-modal", "cross modal",
        "optical aur sar", "sar aur optical", "dono sensor", "both sensors"
    ]
    if _has_any(q, multimodal_cues):
        return "multimodal_fusion"

    # Temporal semantic comparison belongs to the vision assistant when the user
    # asks for an explanation rather than a pixel mask/measurement.
    if _has_any(q, ["visible differences", "visually different", "describe the differences", "what looks different", "what are the differences"]):
        return "vision_question"

    # Generic change detection.
    if _has_any(q, ["what changed", "show changes", "detect changes", "change detection", "compare", "between", "new building", "urban expansion", "construction increased", "construction increase", "where did construction", "built-up", "built up", "expansion", "difference between", "vs", "versus"]):
        # avoid turning a pure temporal visual question into a pixel-change task unless a change cue exists
        if _has_any(q, ["change", "changed", "difference", "compare", "expansion", "construction", "built-up", "built up", "new building"]):
            return "change_detection"

    # Language-guided segmentation / grounding.
    grounding_verbs = ["highlight", "locate", "mark", "segment", "outline", "show me the", "show the", "where are", "where is", "find all", "detect all", "mask"]
    count_verbs = ["count", "how many", "number of"]
    if target and (_has_any(q, grounding_verbs) or _has_any(q, count_verbs)):
        return "grounded_segmentation"

    # Remote-sensing VQA / vision assistant.
    vision_cues = [
        "what is visible", "what do you see", "describe", "explain this image", "summarize this image",
        "what is in this image", "what does this image show", "identify", "classify", "scene type",
        "is there", "are there", "which", "where", "what kind", "can you see", "image me", "image mein",
        "kya dikh", "kya hai", "batao image", "satellite image"
    ]
    if _has_any(q, vision_cues) or (target and any(x in q for x in ["visible", "present", "exist"])):
        return "vision_question"

    # Generic image-context wording is a valid summary request when imagery is attached.
    if dataset_count > 0 and _has_any(q, ["analyze", "analyse", "inspect", "check", "look at", "image", "scene", "imagery"]):
        return "image_summary"

    # Do not pretend arbitrary questions are image analysis.
    return "unsupported"


def _resolve_location(query: str) -> Optional[Dict[str, Any]]:
    q = query.lower()
    for alias, key in LOCATION_ALIASES.items():
        if alias in query:
            out = dict(LOCATIONS[key])
            out["key"] = key
            out["source"] = "offline_gazetteer_alias"
            return out
    for key in sorted(LOCATIONS, key=len, reverse=True):
        if re.search(rf"\b{re.escape(key)}\b", q):
            out = dict(LOCATIONS[key])
            out["key"] = key
            out["source"] = "offline_gazetteer"
            return out
    return None


def _candidate_location_phrase(query: str) -> Optional[str]:
    """Best-effort extraction for unknown place names.

    It intentionally avoids claiming the place is resolved. The backend may pass
    this text to an online geocoder when network access is available.
    """
    month_words = "|".join(sorted(MONTHS.keys(), key=len, reverse=True))
    stop = rf"(?=\s+(?:between|from|during|for|on|in\s+(?:{month_words})|{month_words}|20\d{{2}})|[?.!,;]|$)"
    patterns = [
        rf"\b(?:around|near|across|over|within|at)\s+([A-Za-z][A-Za-z .,'-]{{2,60}}?){stop}",
        rf"\b(?:in)\s+([A-Za-z][A-Za-z .,'-]{{2,60}}?){stop}",
    ]
    q = query.strip()
    for pat in patterns:
        m = re.search(pat, q, flags=re.I)
        if not m:
            continue
        candidate = re.sub(r"\s+", " ", m.group(1)).strip(" ,.-")
        low = candidate.lower()
        if low in MONTHS or re.fullmatch(r"20\d{2}", low):
            continue
        if any(low.startswith(mon + " ") for mon in MONTHS):
            continue
        if low in {"this image", "the image", "these images", "this satellite image", "the satellite image", "this scene", "the scene"}:
            continue
        if low.startswith(("this image ", "the image ", "these images ", "this scene ", "the scene ")):
            continue
        if ("image" in low or "images" in low or "scene" in low) and low.startswith(("the ", "this ", "these ", "two ")):
            continue
        if 2 <= len(candidate) <= 60:
            return candidate
    return None


def _month_bounds(year: int, month: int) -> Tuple[str, str]:
    last = calendar.monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last:02d}"


def _parse_month_year_mentions(query: str) -> List[Tuple[int, int, int]]:
    q = query.lower()
    month_names = sorted(MONTHS.keys(), key=len, reverse=True)
    month_re = "|".join(re.escape(m) for m in month_names)
    raw = []
    # Allows "Jul-2025", "July 2025", "July/2025" and "July and August 2025".
    for m in re.finditer(rf"\b({month_re})\b(?:\s*[-/,]?\s*(20\d{{2}}|19\d{{2}}))?", q):
        raw.append([m.start(), int(m.group(2)) if m.group(2) else None, MONTHS[m.group(1)]])
    if not raw:
        return []
    known_year = next((x[1] for x in reversed(raw) if x[1]), None)
    if known_year:
        for x in raw:
            if x[1] is None:
                x[1] = known_year
    return [(int(pos), int(year), int(month)) for pos, year, month in raw if year]


def _parse_date_range(query: str) -> Optional[Dict[str, Any]]:
    mentions = _parse_month_year_mentions(query)
    if len(mentions) >= 2:
        _, y1, m1 = mentions[0]
        _, y2, m2 = mentions[-1]
        s1, e1 = _month_bounds(y1, m1)
        s2, e2 = _month_bounds(y2, m2)
        return {
            "start_date": min(s1, s2),
            "end_date": max(e1, e2),
            "periods": [
                {"label": f"{calendar.month_name[m1]} {y1}", "start": s1, "end": e1},
                {"label": f"{calendar.month_name[m2]} {y2}", "start": s2, "end": e2},
            ],
            "temporal": True,
        }
    if len(mentions) == 1:
        _, y, m = mentions[0]
        s, e = _month_bounds(y, m)
        return {"start_date": s, "end_date": e, "periods": [{"label": f"{calendar.month_name[m]} {y}", "start": s, "end": e}], "temporal": False}

    # ISO / slash date fallback.
    raw_dates = re.findall(r"\b((?:19|20)\d{2}[-/]\d{1,2}[-/]\d{1,2})\b", query)
    if raw_dates:
        norm = []
        for d in raw_dates:
            y, m, day = re.split(r"[-/]", d)
            norm.append(f"{int(y):04d}-{int(m):02d}-{int(day):02d}")
        if len(norm) >= 2:
            a, b = sorted(norm[:2])
            return {"start_date": a, "end_date": b, "periods": [{"label": a, "start": a, "end": a}, {"label": b, "start": b, "end": b}], "temporal": True}
        a = norm[0]
        return {"start_date": a, "end_date": a, "periods": [{"label": a, "start": a, "end": a}], "temporal": False}
    return None


def parse_query(query: str, dataset_count: int = 0) -> Dict[str, Any]:
    intent = _intent(query, dataset_count)
    location = _resolve_location(query)
    unresolved_location_text = None if location else _candidate_location_phrase(query)
    date_range = _parse_date_range(query)
    q = query.lower()
    temporal = bool(date_range and date_range.get("temporal")) or (
        _has_any(q, ["between", "compare", "vs", "versus", "from", "before and after"]) and intent in {"flood_detection", "change_detection", "vegetation_change", "vision_question"}
    ) or (dataset_count >= 2 and intent in {"change_detection", "vegetation_change", "vision_question"})

    multimodal = intent == "multimodal_fusion"

    preferred_sensor = None
    if intent != "unsupported":
        if multimodal:
            preferred_sensor = "optical+sar"
        elif "sar" in q or "sentinel-1" in q or intent == "flood_detection":
            preferred_sensor = "sar"
        elif "optical" in q or "sentinel-2" in q:
            preferred_sensor = "optical"

    target = _target_object(query)
    output_request = {
        "needs_mask": intent in {"flood_detection", "change_detection", "vegetation_change", "grounded_segmentation"},
        "needs_count": _has_any(q, ["count", "how many", "number of"]),
        "needs_area": _has_any(q, ["area", "km2", "km²", "hectare", "how much", "extent"]) or intent in {"flood_detection", "change_detection", "vegetation_change"},
        "needs_explanation": True,
    }

    resolved_or_candidate = bool(location or unresolved_location_text)
    can_auto_retrieve = bool(
        resolved_or_candidate and date_range and len((date_range or {}).get("periods") or []) >= 2 and intent == "flood_detection"
    )

    unsupported_reason = _unsupported_reason(query) if intent == "unsupported" else None

    return {
        "intent": intent,
        "supported": intent != "unsupported",
        "unsupported_reason": unsupported_reason or ("This request does not match a supported Earth-observation analysis capability. Upload imagery and ask a visual/geospatial question, or use flood/change/vegetation/grounding workflows." if intent == "unsupported" else None),
        "location": location,
        "unresolved_location_text": unresolved_location_text,
        "date_range": date_range,
        "temporal": temporal,
        "multimodal": multimodal,
        "preferred_sensor": preferred_sensor,
        "target_object": target,
        "output_request": output_request,
        "can_auto_retrieve": can_auto_retrieve,
        "vision_assistant": intent in {"vision_question", "image_summary", "grounded_segmentation", "multimodal_fusion"},
    }
