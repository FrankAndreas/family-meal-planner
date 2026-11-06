"""Bring! (spec 2026-11-06): the planner logs in with a family member's own account and adds items to one of its
lists. Bring! has no official API for this; the calls are the ones the Bring! apps make, as used by the bring-api
library behind Home Assistant's integration (github.com/miaucl/bring-api). If Bring! changes them, sending fails
with "bring_failed" and the list in the planner stays."""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import ClassVar, Protocol

from . import config

logger = logging.getLogger(__name__)

API_URL = "https://api.getbring.com/rest/"
# The key every Bring! client sends (bring-api's const.py); it identifies the app, not the account
API_KEY = "cof4Nc6D8saplXjE3h3HXqHH8m7VU2i1Gs0g85Sp"
TIMEOUT_SECONDS = 20


class BringFailed(Exception):
    """code: "bring_login_failed" (email or password refused) or "bring_failed" (anything else)."""

    def __init__(self, code: str, reason: str = ""):
        super().__init__(reason or code)
        self.code = code


@dataclass
class Session:
    uuid: str
    public_uuid: str
    token: str


class BringClient(Protocol):
    def login(self, email: str, password: str) -> Session: ...

    def lists(self, session: Session) -> list[tuple[str, str]]: ...

    def add(self, session: Session, list_uuid: str, items: list[tuple[str, str]]) -> None: ...


class HttpBring:
    def _call(self, method: str, path: str, session: Session | None = None, form=None, body=None) -> bytes:
        headers = {
            "X-BRING-API-KEY": API_KEY,
            "X-BRING-CLIENT": "android",
            "X-BRING-APPLICATION": "bring",
            "X-BRING-COUNTRY": "CH",
        }
        data = None
        if form is not None:
            data = urllib.parse.urlencode(form).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        elif body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        if session is not None:
            headers["Authorization"] = session.token
            headers["X-BRING-USER-UUID"] = session.uuid
            headers["X-BRING-PUBLIC-USER-UUID"] = session.public_uuid
        request = urllib.request.Request(API_URL + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if session is None and error.code in (400, 401):
                raise BringFailed("bring_login_failed", f"HTTP {error.code}") from error
            logger.warning("Bring! %s %s: HTTP %s", method, path.split("/")[0], error.code)
            raise BringFailed("bring_failed", f"HTTP {error.code}") from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            logger.warning("Bring! unreachable: %s", error)
            raise BringFailed("bring_failed", str(error)) from error

    @staticmethod
    def _json(raw: bytes) -> dict:
        try:
            data = json.loads(raw)
        except ValueError as error:
            raise BringFailed("bring_failed", "unreadable answer") from error
        if not isinstance(data, dict):
            raise BringFailed("bring_failed", "unreadable answer")
        return data

    def login(self, email: str, password: str) -> Session:
        data = self._json(self._call("POST", "v2/bringauth", form={"email": email, "password": password}))
        try:
            return Session(
                uuid=str(data["uuid"]),
                public_uuid=str(data.get("publicUuid", "")),
                token=f"{data.get('token_type', 'Bearer')} {data['access_token']}",
            )
        except KeyError as error:
            raise BringFailed("bring_failed", "unreadable login answer") from error

    def lists(self, session: Session) -> list[tuple[str, str]]:
        data = self._json(self._call("GET", f"bringusers/{session.uuid}/lists", session))
        try:
            return [(str(item["listUuid"]), str(item["name"])) for item in data["lists"]]
        except (KeyError, TypeError) as error:
            raise BringFailed("bring_failed", "unreadable lists") from error

    def add(self, session: Session, list_uuid: str, items: list[tuple[str, str]]) -> None:
        place = {"accuracy": "0.0", "altitude": "0.0", "latitude": "0.0", "longitude": "0.0"}
        # No item uuid: Bring! then updates the item of that name if the list has it (as bring-api's save_item and
        # update_item do), so sending again never adds an item twice
        changes = [{**place, "itemId": name, "spec": spec, "operation": "TO_PURCHASE"} for name, spec in items]
        self._call("PUT", f"v2/bringlists/{list_uuid}/items", session, body={"changes": changes, "sender": ""})


class FakeBring:
    """For tests and e2e (BRING_FAKE=1): the password "wrong" is refused, an item named "FAIL" fails the send."""

    sent: ClassVar[list[tuple[str, list[tuple[str, str]]]]] = []

    def login(self, email: str, password: str) -> Session:
        if password == "wrong":
            raise BringFailed("bring_login_failed")
        return Session(uuid="fake-user", public_uuid="fake-public", token="Bearer fake")

    def lists(self, session: Session) -> list[tuple[str, str]]:
        return [("fake-home", "Zuhause"), ("fake-office", "Büro")]

    def add(self, session: Session, list_uuid: str, items: list[tuple[str, str]]) -> None:
        if any(name == "FAIL" for name, _ in items):
            raise BringFailed("bring_failed")
        FakeBring.sent.append((list_uuid, list(items)))


def client() -> BringClient:
    return FakeBring() if config.env("BRING_FAKE") == "1" else HttpBring()
