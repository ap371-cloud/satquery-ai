from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parents[1]
if os.getenv('SATQUERY_DATA_DIR'):
    DATA = Path(os.getenv('SATQUERY_DATA_DIR'))
elif os.getenv('VERCEL'):
    DATA = Path('/tmp/satquery')
else:
    DATA = BASE / 'data'
UPLOADS = DATA / 'uploads'
PREVIEWS = DATA / 'previews'
RESULTS = DATA / 'results'
DB = DATA / 'satquery.db'
for d in [UPLOADS, PREVIEWS, RESULTS]:
    d.mkdir(parents=True, exist_ok=True)

SUPABASE_URL = (os.getenv('SUPABASE_URL') or '').rstrip('/')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_SERVICE_KEY') or ''
SUPABASE_BUCKET = os.getenv('SUPABASE_BUCKET') or 'satquery'
DATABASE_URL = os.getenv('SATQUERY_DATABASE_URL') or os.getenv('DATABASE_URL') or ''


def remote_enabled():
    return bool(SUPABASE_URL and SUPABASE_KEY)


def db():
    if DATABASE_URL:
        return _PgConn()
    con = sqlite3.connect(str(DB), timeout=15)
    con.row_factory = sqlite3.Row
    try:
        con.execute('PRAGMA journal_mode=WAL')
        con.execute('PRAGMA busy_timeout=10000')
    except Exception:
        pass
    return con


class _Row(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return dict.__getitem__(self, list(dict.keys(self))[key])
        return dict.__getitem__(self, key)


class _PgCursor:
    def __init__(self, cur):
        self._cur = cur
        self._names = [c.name for c in (self._cur.description or [])]

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        return _Row(dict(zip(self._names, tuple(row))))

    def fetchall(self):
        out = []
        for row in self._cur.fetchall():
            out.append(_Row(dict(zip(self._names, tuple(row)))))
        return out


class _PgConn:
    def __init__(self):
        import psycopg
        self._pg = psycopg.connect(DATABASE_URL, connect_timeout=10)

    def execute(self, sql, params=None):
        cur = self._pg.execute(sql.replace('?', '%s'), tuple(params) if params is not None else ())
        return _PgCursor(cur)

    def executescript(self, script):
        for stmt in script.split(';'):
            s = stmt.strip()
            if s:
                self._pg.execute(s.replace('?', '%s'))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type:
                self._pg.rollback()
            else:
                self._pg.commit()
        finally:
            self._pg.close()


_bucket_checked = False


def _headers():
    return {'Authorization': f'Bearer {SUPABASE_KEY}'}


def ensure_bucket():
    global _bucket_checked
    if _bucket_checked:
        return
    try:
        r = requests.post(
            f'{SUPABASE_URL}/storage/v1/bucket',
            json={'id': SUPABASE_BUCKET, 'name': SUPABASE_BUCKET, 'public': True},
            headers=_headers(), timeout=30,
        )
        if r.status_code not in (200, 201, 409):
            existing = requests.get(f'{SUPABASE_URL}/storage/v1/bucket', headers=_headers(), timeout=30)
            if not any(b.get('name') == SUPABASE_BUCKET for b in existing.json()):
                raise RuntimeError(f'Could not create storage bucket: {r.status_code} {r.text[:200]}')
    except RuntimeError:
        raise
    _bucket_checked = True


def put_file(key, local: Path):
    if not remote_enabled():
        return
    if not Path(local).exists():
        return
    ensure_bucket()
    url = f'{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{key}'
    with open(local, 'rb') as f:
        r = requests.put(
            url, data=f,
            headers={**_headers(), 'x-upsert': 'true', 'Content-Type': 'application/octet-stream'},
            timeout=600,
        )
    if r.status_code >= 300:
        raise RuntimeError(f'Storage put failed {key}: {r.status_code} {r.text[:200]}')


def fetch_file(key) -> Path:
    local = DATA / key
    if local.exists():
        return local
    if remote_enabled():
        ensure_bucket()
        url = f'{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{key}'
        r = requests.get(url, headers=_headers(), timeout=600)
        if r.status_code == 200:
            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_bytes(r.content)
            return local
        raise FileNotFoundError(key)
    raise FileNotFoundError(key)


def delete_file(key):
    local = DATA / key
    try:
        local.unlink(missing_ok=True)
    except Exception:
        pass
    if remote_enabled():
        try:
            requests.delete(f'{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{key}', headers=_headers(), timeout=60)
        except Exception:
            pass