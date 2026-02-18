import math


POWER_STATES = {
    "off": 0,
    "on": 1
}

HEALTH_STATES = {
    "ok": 0,
    "operable": 0,
    "enabled": 0,
    "good": 0,
    "critical": 1,
    "error": 1,
    "warning": 2,
    "absent": 0
}

class Collector:
    def __init__(self, session):
        self.session = session

    def _extractHealthRawStatus(self, data):
        """Extract health status from data."""
        if "Status" not in data:
            return math.nan, {}

        status = data["Status"]
        #if isinstance(status, str):
        #    return status.lower(), {}

        status = {k.lower(): v for k, v in status.items()}
        state = status.get("state")
        if state == "Enable": # Fix for XFusion
            state = "Enabled"

        if state is None:
            return math.nan, status

        return state.lower(), status

    def extractHealthRawStatus(self, data):
        state, _ = self._extractHealthRawStatus(data)
        return state

    def extractHealthStatus(self, data, allow_absent=False):
        state, status = self._extractHealthRawStatus(data)

        if state == "absent":
            return HEALTH_STATES[state] if allow_absent else math.nan

        health = status.get("health", "")
        if not health:
            return math.nan

        return HEALTH_STATES[health.lower()]

    def extractStringData(self, data, name, fallback = ""):
        return str(data.get(name, fallback)).strip()
