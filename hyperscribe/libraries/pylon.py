from typing import Any

from requests import Response, post as requests_post

from hyperscribe.libraries.constants import Constants
from logger import log

REQUEST_TIMEOUT = 10


class Pylon:
    def __init__(self, api_key: str):
        self.base_url = Constants.VENDOR_PYLON_API_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def search_account(self, instance_name: str) -> str | None:
        # Try exact name first, then without hyphens (e.g. "new-instance" -> "NewInstance")
        # Instance slugs are always lowercase kebab-case
        candidates = [instance_name]
        dehyphenated = "".join(part.capitalize() for part in instance_name.split("-"))
        if dehyphenated != instance_name:
            candidates.append(dehyphenated)
        for candidate in candidates:
            account_id = self._find_account(candidate)
            if account_id is not None:
                return account_id
        fallback = Constants.VENDOR_PYLON_FALLBACK_ACCOUNT
        account_id = self._find_account(fallback)
        if account_id is None:
            log.warning(f"No Pylon account found for '{instance_name}' (tried {candidates} and fallback '{fallback}')")
        return account_id

    def _find_account(self, query: str) -> str | None:
        resp = requests_post(
            f"{self.base_url}/accounts/search",
            headers=self.headers,
            json={
                "filter": {
                    "field": "name",
                    "operator": "string_contains",
                    "value": query,
                },
                "limit": 10,
            },
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            accounts = resp.json().get("data", [])
            if accounts:
                return str(accounts[0]["id"])
        else:
            log.warning(f"Pylon account search failed: {resp.status_code}, {resp.text}")
        return None

    def create_issue(
        self,
        title: str,
        body_html: str,
        requester_email: str | None = None,
        account_id: str | None = None,
        tags: list[str] | None = None,
    ) -> Response:
        payload: dict[str, Any] = {"title": title, "body_html": body_html}
        if account_id:
            payload["account_id"] = account_id
        if requester_email:
            payload["requester_email"] = requester_email
        if tags:
            payload["tags"] = tags
        return requests_post(
            f"{self.base_url}/issues",
            headers=self.headers,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
