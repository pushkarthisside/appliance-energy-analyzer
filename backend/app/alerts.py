"""Optional SNS email alerts (ARCHITECTURE.md §16).

- Off unless ``AEA_ALERTS_ENABLED=true`` AND ``AEA_SNS_TOPIC_ARN`` is set.
- An eligible analysis (non-empty ``issues``) may publish, subject to a per-sample
  cooldown (``AEA_ALERT_COOLDOWN_SECONDS``). An email is not guaranteed per analysis.
- Publish has a 3-second timeout; any failure gives ``failed`` and never fails analysis.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

from app.analytics.wording import assert_clean
from app.config import Settings
from app.schemas import AnalysisResponse

log = logging.getLogger("aea.alerts")


def alert_text(response: AnalysisResponse) -> tuple[str, str]:
    n = len(response.issues)
    subject = f"Appliance Energy Analyzer: unusual use estimated for {n} appliance(s)"
    source = "Simulated demonstration scenario" if response.source.simulated else response.source.title
    lines = [f"Source: {source}", ""]
    for issue in response.issues:
        inr = issue.savings.inr_per_month
        tag = " (illustrative)" if issue.savings.illustrative else ""
        lines.append(
            f"- {issue.appliance_name}: estimated change {issue.change_pct:+.1f}%; "
            f"{issue.savings.label}: ₹{inr.low:,.0f}-₹{inr.high:,.0f} per month{tag}"
        )
        lines.extend(f"  {c}" for c in issue.caveats)
    body = "\n".join(lines)
    assert_clean(subject)
    assert_clean(body)
    return subject, body


class AlertService:
    def __init__(self, settings: Settings, client_factory: Callable[[], Any] | None = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.settings = settings
        self._client_factory = client_factory
        self._client = None
        self._clock = clock
        self._last_sent: dict[str, float] = {}
        self._lock = threading.Lock()

    def _sns(self):
        if self._client is None:
            if self._client_factory is not None:
                self._client = self._client_factory()
            else:
                import boto3
                from botocore.config import Config

                self._client = boto3.client(
                    "sns",
                    region_name=self.settings.aws_region,
                    config=Config(connect_timeout=3, read_timeout=3, retries={"max_attempts": 1}),
                )
        return self._client

    def publish(self, response: AnalysisResponse) -> str:
        """Returns ``sent``, ``failed``, ``disabled``, ``no_issues`` or ``cooldown``."""
        if not response.issues:
            return "no_issues"
        if not self.settings.alerts_active:
            return "disabled"
        key = f"{response.source.kind}:{response.source.sample_id}"
        with self._lock:
            last = self._last_sent.get(key)
            if last is not None and self._clock() - last < self.settings.alert_cooldown_seconds:
                return "cooldown"
            try:
                subject, body = alert_text(response)
                self._sns().publish(TopicArn=self.settings.sns_topic_arn, Subject=subject[:100], Message=body)
            except Exception as exc:
                log.error("alert publish failed: %s", exc)
                return "failed"
            self._last_sent[key] = self._clock()
            return "sent"
