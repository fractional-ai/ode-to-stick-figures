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
    URL — it's always `https://{host}.public.blob.vercel-storage.com/{key}`, where host
    is derived from the store id by `_public_url` below.

    Every request shape below was verified against a real store (`stick-figures` on the
    fractional-ai team) rather than inferred from docs. Four things that verification
    settled, each of which was wrong or unconfirmed beforehand:
      1. The pathname goes in the URL *path*, not a `?pathname=` query param — the
         query-param form returns 400 `{"code":"bad_request","message":"Invalid
         pathname"}`. `x-api-version: 7` goes with it.
      2. The public read host is the store id **lowercased with the `store_` prefix
         stripped** (`h0cfy3s….public.blob.vercel-storage.com`). Passing the id
         verbatim as it appears in the dashboard 404s every read.
      3. BLOB_STORE_ID is *not* auto-injected when a store is linked — only
         BLOB_READ_WRITE_TOKEN is. The token embeds the store id
         (`vercel_blob_rw_<storeId>_<secret>`), so it's derived from there and the
         extra env var is never needed.
      4. List responses are paginated (`hasMore`/`cursor`), so list_keys loops.
    """

    _API_BASE = "https://blob.vercel-storage.com"
    _API_VERSION = "7"

    def __init__(self, token: str | None = None, store_id: str | None = None):
        self.token = token or os.environ["BLOB_READ_WRITE_TOKEN"]
        self.store_id = (
            store_id or os.environ.get("BLOB_STORE_ID") or _store_id_from_token(self.token)
        )

    def _headers(self, **extra: str) -> dict[str, str]:
        return {
            "authorization": f"Bearer {self.token}",
            "x-api-version": self._API_VERSION,
            **extra,
        }

    def write_bytes(self, key: str, data: bytes) -> None:
        import httpx

        resp = httpx.put(
            f"{self._API_BASE}/{key.lstrip('/')}",
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
        host = self.store_id.removeprefix("store_").lower()
        return f"https://{host}.public.blob.vercel-storage.com/{key}"

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
        """Every page of them. One upload writes ~10 artifacts, so a gallery of any size
        outruns a single page, and the tail would silently vanish from /api/creatures."""
        import httpx

        keys: list[str] = []
        cursor: str | None = None
        while True:
            params = {}
            if prefix:
                params["prefix"] = prefix
            if cursor:
                params["cursor"] = cursor
            resp = httpx.get(self._API_BASE, params=params, headers=self._headers(), timeout=30.0)
            resp.raise_for_status()
            page = resp.json()
            keys.extend(b["pathname"] for b in page.get("blobs", []))
            if not page.get("hasMore"):
                return keys
            cursor = page.get("cursor")
            if not cursor:  # hasMore with no cursor would otherwise spin forever
                return keys


def _store_id_from_token(token: str) -> str:
    """Pull the store id out of `vercel_blob_rw_<storeId>_<secret>`.

    Linking a Blob store injects only BLOB_READ_WRITE_TOKEN, so this is how the read
    host gets built without asking anyone to set a second env var by hand.
    """
    parts = token.split("_")
    if len(parts) < 5 or not token.startswith("vercel_blob_rw_"):
        raise ValueError(
            "BLOB_READ_WRITE_TOKEN is not in the expected "
            "vercel_blob_rw_<storeId>_<secret> form; set BLOB_STORE_ID explicitly"
        )
    return parts[3]


def default_storage(root: Path) -> Storage:
    """BlobStorage if this looks like a real Vercel deployment, else LocalStorage.

    Checked by presence of the token, not the VERCEL env var: a Blob-backed run needs
    the token regardless of what set VERCEL, and a dev machine that happens to export
    VERCEL for some unrelated reason shouldn't suddenly need Blob credentials to boot.
    """
    if os.environ.get("BLOB_READ_WRITE_TOKEN"):
        return BlobStorage()
    return LocalStorage(root)
