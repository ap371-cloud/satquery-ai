"""Security regression tests for the SatQuery AI hardening work.

Run from the repo root: python scripts/test_security.py

Pure-function tests always run. End-to-end tests (HTTP layer + middleware)
run only when httpx is installed (pip install -r backend/requirements-dev.txt).
"""
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

from app.security import (
    GEMINI_SYSTEM_INSTRUCTION,
    check_rate_limit,
    sanitize_filename,
    sanitize_health,
    safe_error,
    validate_magic_bytes,
    _InMemoryLimiter,
    RATE_LIMITS,
)


def _ok(cond, msg):
    assert cond, msg
    print("  ok:", msg)


def test_magic_bytes():
    print("\n[magic_bytes]")
    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as f:
        f.write(b"II*\x00")
        p = Path(f.name)
    _ok(validate_magic_bytes(p, ".tif") is True, "TIFF little-endian header accepted")
    p.write_bytes(b"MM\x00*")
    _ok(validate_magic_bytes(p, ".tif") is True, "TIFF big-endian header accepted")
    p.write_bytes(b"\x89PNG\r\n\x1a\n")
    _ok(validate_magic_bytes(p, ".png") is True, "PNG header accepted")
    _ok(validate_magic_bytes(p, ".tif") is False, "PNG rejected as TIFF")
    p.write_bytes(b"\x00\x00\x00\x00")
    _ok(validate_magic_bytes(p, ".tif") is False, "garbage rejected")
    p.write_bytes(b"\xff\xd8\xff")
    _ok(validate_magic_bytes(p, ".jpg") is True, "JPEG header accepted")
    p.unlink(missing_ok=True)


def test_filename():
    print("\n[filename]")
    _ok(sanitize_filename("../../etc/passwd") == "passwd", "path traversal stripped")
    _ok(sanitize_filename("../../etc/passwd.tif") == "passwd.tif", "path traversal stripped (.tif)")
    _ok(sanitize_filename("C:\\Users\\me\\scene.png") == "scene.png", "windows path -> basename")
    _ok(sanitize_filename("photo 1.png") == "photo_1.png", "spaces -> underscores")
    _ok(sanitize_filename("upload") == "upload", "extensionless name kept")
    _ok(sanitize_filename("") == "upload", "empty name -> upload")
    _ok(len(sanitize_filename("x" * 500 + ".tif")) <= 120, "name length capped")


def test_safe_error():
    print("\n[safe_error]")
    _ok("Users" not in safe_error(ValueError("C:\\Users\\a\\b.tif: read failed")), "windows path stripped")
    _ok("/app/models" not in safe_error(ValueError("/app/models/clip is missing")), "unix path stripped")
    _ok("runtime error" in safe_error(RuntimeError("runtime error")), "plain message preserved")
    _ok(len(safe_error(ValueError("x" * 500))) <= 250, "error truncated")
    _ok(safe_error(Exception()) == "An unexpected error occurred during operation.", "empty error -> generic")


def test_health_redaction():
    print("\n[health_redaction]")
    h = {
        "agent_bridge": {"url": "http://internal:8010", "reachable": True},
        "specialists": {
            "vision": {"url": "http://x:1", "detail": "raw provider text", "enabled": True},
            "sar": {"enabled": False},
        },
    }
    out = sanitize_health(h)
    _ok(out["agent_bridge"]["url"] is None, "top-level url redacted")
    _ok(out["specialists"]["vision"]["url"] is None, "nested url redacted")
    _ok(out["specialists"]["vision"]["detail"] is None, "raw detail string redacted")
    _ok(out["agent_bridge"]["reachable"] is True, "non-secret fields kept")
    _ok(out["specialists"]["sar"]["enabled"] is False, "unrelated fields kept")


def test_in_memory_limiter():
    print("\n[in_memory_limiter]")
    lim = _InMemoryLimiter()
    _ok(lim.allow("k", 2, 5) is True, "1st request allowed")
    _ok(lim.allow("k", 2, 5) is True, "2nd request allowed")
    _ok(lim.allow("k", 2, 5) is False, "3rd request blocked")
    _ok(lim.retry_after("k", 5) >= 1, "retry-after returned")


def test_check_rate_limit_default_scope():
    print("\n[check_rate_limit]")
    _ok(check_rate_limit("parse", "unit-" + uuid.uuid4().hex) == 0, "first call allowed")


def test_system_instruction():
    print("\n[system_instruction]")
    _ok("satellite imagery" in GEMINI_SYSTEM_INSTRUCTION.lower(), "scope focuses on satellite imagery")
    _ok("do not fabricate numeric measurements" in GEMINI_SYSTEM_INSTRUCTION.lower(), "no-fabrication guard present")


def _e2e():
    """HTTP-layer tests; requires app.main import to succeed."""
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    from app import security

    client = TestClient(fastapi_app)
    print("\n[e2e]")

    # Security headers on API responses
    r = client.get("/api/v1/health")
    _ok(r.status_code == 200, "health reachable")
    _ok(r.headers.get("x-content-type-options") == "nosniff", "X-Content-Type-Options set")
    _ok(r.headers.get("x-frame-options") == "DENY", "X-Frame-Options set")
    _ok("content-security-policy" in r.headers, "CSP set on API responses")
    _ok(r.headers.get("cache-control", "").startswith("no-store"), "no-store cache control")

    # Health does not leak internal URLs or raw detail strings
    _ok(r.json().get("agent_bridge", {}).get("url") is None, "agent bridge url redacted")
    _ok(r.headers.get("retry-after") is None, "no spurious Retry-After")

    # Query length capped by pydantic Field
    r = client.post("/api/v1/query/parse", json={"query": "x" * 3000, "dataset_count": 0})
    _ok(r.status_code == 422, "oversized query rejected (422)")

    # Negative / oversized dataset_count rejected
    r = client.post("/api/v1/query/parse", json={"query": "flood assam", "dataset_count": 999})
    _ok(r.status_code == 422, "oversized dataset_count rejected (422)")

    # Unknown provider rejected before any work starts
    r = client.post("/api/v1/analyses", json={"query": "flood areas around Assam", "provider": "EVIL"})
    _ok(r.status_code == 422, "unknown provider rejected (422)")

    # Upload: magic-byte mismatch rejected
    r = client.post(
        "/api/v1/datasets",
        files={"file": ("evil.tif", b"\x00\x00\x00\x00", "image/tiff")},
        data={"modality": "auto"},
    )
    _ok(r.status_code == 400, "fake TIFF rejected (400)")

    # Upload: unknown modality rejected
    r = client.post(
        "/api/v1/datasets",
        files={"file": ("evil.png", b"not-a-real-png", "image/png")},
        data={"modality": "bogus"},
    )
    _ok(r.status_code == 422, "unknown modality rejected (422)")

    # Rate limiting kicks in and returns Retry-After
    security.RATE_LIMITS["demo_load"] = (1, 60)
    first = client.post("/api/v1/demo/load")
    _ok(first.status_code == 200, "demo/load allowed under limit")
    second = client.post("/api/v1/demo/load")
    _ok(second.status_code == 429, "demo/load rate-limited on 2nd call")
    _ok(int(second.headers.get("retry-after", "0")) >= 1, "Retry-After header present")

    # Debug endpoint hidden unless SATQUERY_DEBUG is on
    r = client.get("/api/v1/ai/free-test")
    _ok(r.status_code == 404, "ai/free-test disabled by default (404)")


def main():
    test_magic_bytes()
    test_filename()
    test_safe_error()
    test_health_redaction()
    test_in_memory_limiter()
    test_check_rate_limit_default_scope()
    test_system_instruction()
    try:
        _e2e()
    except ImportError:
        print("\nSKIP e2e: httpx not installed (pip install -r backend/requirements-dev.txt)")
    print("\nAll security tests passed.")


if __name__ == "__main__":
    main()