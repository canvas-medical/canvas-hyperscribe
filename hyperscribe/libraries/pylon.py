from requests import Response, post as requests_post

from hyperscribe.libraries.constants import Constants
from logger import log


class Pylon:
    def __init__(self, api_key: str):
        self.base_url = Constants.VENDOR_PYLON_API_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def search_account(self, instance_name: str) -> str | None:
        resp = requests_post(
            f"{self.base_url}/accounts/search",
            headers=self.headers,
            json={"query": instance_name},
        )
        if resp.status_code == 200:
            accounts = resp.json().get("data", [])
            for account in accounts:
                if instance_name.lower() in account.get("name", "").lower():
                    return str(account["id"])
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
        payload: dict = {"title": title, "body_html": body_html}
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
        )
