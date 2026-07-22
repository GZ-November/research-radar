"""Optional Crossref DOI integrity lookup."""

import httpx

from radar.config import get_settings


class CrossrefIntegrityAdapter:
    endpoint = "https://api.crossref.org/works"

    def __init__(
        self, timeout_seconds: float = 15.0, *, mailto: str | None = None
    ):
        self.timeout_seconds = timeout_seconds
        self.mailto = mailto or get_settings().crossref_mailto

    def _message(self, doi: str) -> dict:
        try:
            response = httpx.get(
                f"{self.endpoint}/{doi}", timeout=self.timeout_seconds,
                headers={
                    "User-Agent": f"ResearchRadar/0.1 (mailto:{self.mailto})"
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"crossref_check_failed: {exc}") from exc
        return response.json().get("message", {})

    def check(self, doi: str) -> dict:
        message = self._message(doi)
        updates = message.get("update-to", []) + message.get("updated-by", [])
        relation = message.get("relation", {})
        serialized = json_safe = {"updates": updates, "relation": relation}
        text = str(serialized).lower()
        state = (
            "retracted"
            if "retract" in text
            else "expression_of_concern"
            if "concern" in text
            else "corrected"
            if "correct" in text
            else "normal"
        )
        return {"doi": doi, "integrity_state": state, **json_safe}

    def metadata(self, doi: str) -> dict:
        """Return bibliographic fields needed for a human-auditable paper card."""

        message = self._message(doi)
        container_titles = message.get("container-title") or []
        event = message.get("event") or {}
        venue = next((item.strip() for item in container_titles if item.strip()), None)
        venue = venue or event.get("name") or message.get("publisher")
        return {
            "doi": doi,
            "venue": venue,
            "crossref_type": message.get("type"),
            "publisher_url": message.get("URL"),
        }
