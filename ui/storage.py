"""Where uploaded creatures live: local disk in dev, Vercel Blob in production.

The bundled 13 creatures stay local, committed, read-only files (PREBUILT/RIGS in
serve.py) — this module has nothing to do with them. It exists only for content that
a request creates: an uploaded drawing and everything the swarm builds from it.

Vercel Functions have a read-only filesystem outside of /tmp (which is writable but
ephemeral, not shared across invocations), so "write it to a local directory" stops
working the moment this is actually deployed there. Two backends, one small interface,
selected once at import time by whether BLOB_READ_WRITE_TOKEN is set.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol


class Storage(Protocol):
    def write_bytes(self, key: str, data: bytes) -> None: ...
    def read_bytes(self, key: str) -> bytes | None: ...
    def exists(self, key: str) -> bool: ...
    def list_keys(self, prefix: str = "") -> list[str]: ...


class LocalStorage:
    """Dev backend: a plain directory, created lazily on first write.

    Never creates the directory at import/construction time. serve.py used to call
    UPLOADS.mkdir() unconditionally at module load, which is exactly the crash this
    avoids: on Vercel that directory doesn't exist in the deploy bundle (it's
    gitignored) and the filesystem is read-only, so an eager mkdir() there would
    throw on every cold start, before any route ran. LocalStorage is never
    instantiated on Vercel at all, but the discipline of "no writes before someone
    asks for one" is worth keeping regardless.
    """

    def __init__(self, root: Path):
        self.root = root

    def write_bytes(self, key: str, data: bytes) -> None:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def read_bytes(self, key: str) -> bytes | None:
        path = self.root / key
        return path.read_bytes() if path.is_file() else None

    def exists(self, key: str) -> bool:
        return (self.root / key).is_file()

    def list_keys(self, prefix: str = "") -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(
            rel
            for p in self.root.rglob("*")
            if p.is_file() and (rel := str(p.relative_to(self.root))).startswith(prefix)
        )


class BlobStorage:
    """Production backend: Vercel Blob over its REST API directly.

    There is no official Python SDK for Vercel Blob (only the JS/TS `@vercel/blob`
    package) — checked before writing this, so this ~60-line wrapper is a deliberate
    choice, not a reimplementation of something that already exists.

    Every key is written with addRandomSuffix disabled and allowOverwrite enabled, so
    a key is a stable, idempotent address: re-uploading the same key overwrites rather
    than errors, and a read never needs a list-then-fetch round trip to find the right
    URL — it's always `https://{store_id}.public.blob.vercel-storage.com/{key}`.

    NOT covered by the automated test suite: correctness here depends on a real Blob
    store and a real token, neither of which exists until the Vercel project is set
    up. Smoke-test this against a real store (upload a small key, read it back, confirm
    the byte-for-byte content) before trusting it in production. Two things this
    smoke test specifically needs to confirm, not just assume:
      1. _API_BASE — written from the documented PUT/list/delete request *shapes*,
         not from a directly confirmed literal hostname.
      2. BLOB_STORE_ID — BLOB_READ_WRITE_TOKEN is confirmed auto-injected once a Blob
         store is linked to the Vercel project; this second env var is NOT confirmed
         to be auto-injected the same way and may need setting by hand.
    """

    _API_BASE = "https://blob.vercel-storage.com"

    def __init__(self, token: str | None = None, store_id: str | None = None):
        self.token = token or os.environ["BLOB_READ_WRITE_TOKEN"]
        self.store_id = store_id or os.environ["BLOB_STORE_ID"]

    def _headers(self, **extra: str) -> dict[str, str]:
        return {"authorization": f"Bearer {self.token}", **extra}

    def write_bytes(self, key: str, data: bytes) -> None:
        import httpx

        resp = httpx.put(
            self._API_BASE,
            params={"pathname": key},
            content=data,
            headers=self._headers(
                **{
                    "x-vercel-blob-access": "public",
                    "x-add-random-suffix": "0",
                    "x-allow-overwrite": "1",
                }
            ),
            timeout=60.0,
        )
        resp.raise_for_status()

    def _public_url(self, key: str) -> str:
        return f"https://{self.store_id}.public.blob.vercel-storage.com/{key}"

    def read_bytes(self, key: str) -> bytes | None:
        import httpx

        resp = httpx.get(self._public_url(key), timeout=30.0)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.content

    def exists(self, key: str) -> bool:
        import httpx

        resp = httpx.head(self._public_url(key), timeout=30.0)
        return resp.status_code == 200

    def list_keys(self, prefix: str = "") -> list[str]:
        import httpx

        resp = httpx.get(
            self._API_BASE,
            params={"prefix": prefix} if prefix else {},
            headers=self._headers(),
            timeout=30.0,
        )
        resp.raise_for_status()
        return [b["pathname"] for b in resp.json().get("blobs", [])]


def default_storage(root: Path) -> Storage:
    """BlobStorage if this looks like a real Vercel deployment, else LocalStorage.

    Checked by presence of the token, not the VERCEL env var: a Blob-backed run needs
    the token regardless of what set VERCEL, and a dev machine that happens to export
    VERCEL for some unrelated reason shouldn't suddenly need Blob credentials to boot.
    """
    if os.environ.get("BLOB_READ_WRITE_TOKEN"):
        return BlobStorage()
    return LocalStorage(root)
