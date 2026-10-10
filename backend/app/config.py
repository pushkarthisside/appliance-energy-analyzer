"""Application settings from ``AEA_*`` environment variables (ARCHITECTURE.md §17.2).

No secrets live here: AWS access comes from the EC2 instance role (or the developer's
own AWS profile when running locally).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _bool(value: str | None, default: bool) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _int(value: str | None, default: int) -> int:
    try:
        return int(value) if value not in (None, "") else default
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    s3_bucket: str | None
    aws_region: str
    data_dir: Path
    frontend_dir: Path
    alerts_enabled: bool
    sns_topic_arn: str | None
    alert_cooldown_seconds: int
    enable_upload: bool
    max_upload_mb: int
    log_level: str

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Settings":
        env = dict(os.environ if env is None else env)
        default_frontend = Path(__file__).resolve().parents[2] / "frontend" / "dist"
        return cls(
            s3_bucket=env.get("AEA_S3_BUCKET") or None,
            aws_region=env.get("AEA_AWS_REGION") or "ap-south-1",
            data_dir=Path(env.get("AEA_DATA_DIR") or "/opt/aea/data"),
            frontend_dir=Path(env.get("AEA_FRONTEND_DIR") or default_frontend),
            alerts_enabled=_bool(env.get("AEA_ALERTS_ENABLED"), False),
            sns_topic_arn=env.get("AEA_SNS_TOPIC_ARN") or None,
            alert_cooldown_seconds=_int(env.get("AEA_ALERT_COOLDOWN_SECONDS"), 600),
            enable_upload=_bool(env.get("AEA_ENABLE_UPLOAD"), False),
            max_upload_mb=_int(env.get("AEA_MAX_UPLOAD_MB"), 20),
            log_level=(env.get("AEA_LOG_LEVEL") or "INFO").upper(),
        )

    @property
    def alerts_active(self) -> bool:
        """Alerts run only when explicitly enabled AND a topic is configured (§16)."""
        return self.alerts_enabled and bool(self.sns_topic_arn)
