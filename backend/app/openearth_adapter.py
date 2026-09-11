from __future__ import annotations
import os
from typing import Any, Dict, Optional
import requests

class OpenEarthAdapter:
    """Optional HTTP bridge to a real OpenEarthAgent runtime.

    Set OPENEARTHAGENT_URL, e.g. http://localhost:8010.
    The companion bridge in scripts/openearth_bridge.py exposes /plan.
    """
    def __init__(self):
        self.url = os.getenv('OPENEARTHAGENT_URL', '').rstrip('/')

    @property
    def enabled(self) -> bool:
        return bool(self.url)

    def health(self) -> Dict[str, Any]:
        if not self.enabled:
            return {'enabled': False, 'reachable': False}
        try:
            r = requests.get(self.url + '/health', timeout=2)
            return {'enabled': True, 'reachable': r.ok, 'detail': r.json() if r.ok else r.text}
        except Exception as exc:
            return {'enabled': True, 'reachable': False, 'error': str(exc)}

    def plan(self, query: str, image_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        try:
            r = requests.post(self.url + '/plan', json={'query': query, 'image_path': image_path}, timeout=120)
            if r.ok:
                return r.json()
        except Exception:
            pass
        return None
