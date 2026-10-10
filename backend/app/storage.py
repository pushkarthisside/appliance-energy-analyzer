"""Artifact sync and local cache (ARCHITECTURE.md §6.1, §6.7, §15.1).

Startup downloads the bucket into ``$AEA_DATA_DIR/staging/``, validates it, then swaps
it into ``current/`` (the previous ``current/`` is kept as ``previous/``). If S3 fails,
an existing ``current/`` is used (``failed_using_cache``); with no cache the app is
``not_ready`` (``failed_no_cache``).

Local mode (no ``AEA_S3_BUCKET``): nothing is downloaded. The artifact root is
``$AEA_DATA_DIR/current/`` or, for convenience, ``$AEA_DATA_DIR`` itself when it already
contains ``registry.json`` (e.g. ``AEA_DATA_DIR=../artifacts`` from ``backend/``). Local
mode reports ``failed_using_cache`` because no sync took place.
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from app.config import Settings
from app.nilm.registry import load_registry

log = logging.getLogger("aea.storage")

ALLOWED_TOP_LEVEL = {"registry.json", "config", "models", "samples", "evaluation"}


class ArtifactError(ValueError):
    """The artifact set is unusable."""


@dataclass(frozen=True)
class SyncResult:
    state: str  # ok | failed_using_cache | failed_no_cache
    at: str | None
    root: Path | None  # directory holding registry.json etc., or None
    detail: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_artifacts(root: Path) -> None:
    """Minimum validity required before an artifact set may be swapped into service."""
    if not (root / "registry.json").is_file():
        raise ArtifactError("registry.json is missing")
    load_registry(root / "registry.json")  # raises RegistryError (a ValueError)
    actions_path = root / "config" / "actions.json"
    try:
        actions = json.loads(actions_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactError(f"config/actions.json is unreadable: {exc}") from exc
    for key in ("savings_label", "driver_texts", "caveats", "actions"):
        if key not in actions:
            raise ArtifactError(f"config/actions.json is missing '{key}'")


def _safe_relative(key: str) -> PurePosixPath | None:
    rel = PurePosixPath(key)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts or key.endswith("/"):
        return None
    if rel.parts[0] not in ALLOWED_TOP_LEVEL:
        return None
    return rel


def download_bucket(client: Any, bucket: str, target: Path) -> int:
    """Download every allowed key of ``bucket`` into ``target``. Returns the file count."""
    count = 0
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            rel = _safe_relative(obj["Key"])
            if rel is None:
                log.warning("skipping unexpected S3 key %r", obj["Key"])
                continue
            dest = target.joinpath(*rel.parts)
            dest.parent.mkdir(parents=True, exist_ok=True)
            client.download_file(bucket, obj["Key"], str(dest))
            count += 1
    return count


def _cache_state(current: Path, detail: str) -> SyncResult:
    try:
        validate_artifacts(current)
        return SyncResult("failed_using_cache", None, current, detail)
    except (ValueError, OSError) as exc:
        return SyncResult("failed_no_cache", None, None, f"{detail}; no valid cache ({exc})")


def sync_artifacts(settings: Settings, client: Any | None = None) -> SyncResult:
    data_dir = settings.data_dir
    current = data_dir / "current"

    if not settings.s3_bucket:
        root = current if (current / "registry.json").is_file() else data_dir
        return _cache_state(root, "local mode: AEA_S3_BUCKET is not set, no sync performed")

    staging = data_dir / "staging"
    try:
        if client is None:
            import boto3  # only needed when S3 is configured

            client = boto3.client("s3", region_name=settings.aws_region)
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        files = download_bucket(client, settings.s3_bucket, staging)
        validate_artifacts(staging)
    except Exception as exc:  # any S3 or validation failure falls back to the cache
        log.error("artifact sync failed: %s", exc)
        shutil.rmtree(staging, ignore_errors=True)
        return _cache_state(current, f"S3 sync failed: {exc}")

    previous = data_dir / "previous"
    if previous.exists():
        shutil.rmtree(previous)
    if current.exists():
        current.rename(previous)
    staging.rename(current)
    log.info("synced %d artifact files from s3://%s", files, settings.s3_bucket)
    return SyncResult("ok", _now(), current)
