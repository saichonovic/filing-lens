from __future__ import annotations


def build_alert_payload(signal_id: str) -> dict:
    """Build alert-safe payloads from detected signals and evidence."""
    return {"signal_id": signal_id}
