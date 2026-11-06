"""The Bring! client against a stubbed network (spec 2026-11-06)."""

import http.client
import io
import json
import urllib.error
import urllib.parse

import pytest

from app import bring


class Reply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


@pytest.fixture
def network(monkeypatch):
    """Records each request and answers from a queue (bytes, or an exception to raise)."""
    calls: list = []
    answers: list = []

    def urlopen(request, timeout=None):
        calls.append(request)
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return Reply(answer)

    monkeypatch.setattr(bring.urllib.request, "urlopen", urlopen)
    return calls, answers


AUTH = json.dumps({"uuid": "u-1", "publicUuid": "p-1", "access_token": "tok", "token_type": "Bearer"}).encode()


def _http_error(code):
    return urllib.error.HTTPError("https://api.getbring.com", code, "x", {}, io.BytesIO(b"{}"))


def test_login_sends_form_and_reads_uuid(network):
    calls, answers = network
    answers.append(AUTH)
    session = bring.HttpBring().login("a@b.ch", "geheim")
    assert session.uuid == "u-1" and session.token == "Bearer tok"
    request = calls[0]
    assert request.full_url == "https://api.getbring.com/rest/v2/bringauth"
    assert request.get_method() == "POST"
    assert urllib.parse.parse_qs(request.data.decode()) == {"email": ["a@b.ch"], "password": ["geheim"]}
    assert request.get_header("X-bring-api-key") == bring.API_KEY


@pytest.mark.parametrize("code", [400, 401])
def test_login_refused_is_login_failed(network, code):
    network[1].append(_http_error(code))
    with pytest.raises(bring.BringFailed) as failed:
        bring.HttpBring().login("a@b.ch", "falsch")
    assert failed.value.code == "bring_login_failed"


def test_lists(network):
    calls, answers = network
    answers += [AUTH, json.dumps({"lists": [{"listUuid": "l-1", "name": "Zuhause", "theme": "x"}]}).encode()]
    client = bring.HttpBring()
    assert client.lists(client.login("a@b.ch", "geheim")) == [("l-1", "Zuhause")]
    assert calls[1].full_url == "https://api.getbring.com/rest/bringusers/u-1/lists"
    assert calls[1].get_header("Authorization") == "Bearer tok"
    assert calls[1].get_header("X-bring-user-uuid") == "u-1"


def test_add_sends_changes(network):
    calls, answers = network
    answers += [AUTH, b""]
    client = bring.HttpBring()
    client.add(client.login("a@b.ch", "geheim"), "l-1", [("Hörnli", "500 g"), ("WC-Papier", "")])
    request = calls[1]
    assert request.full_url == "https://api.getbring.com/rest/v2/bringlists/l-1/items"
    assert request.get_method() == "PUT"
    body = json.loads(request.data)
    assert body["sender"] == ""
    assert [(c["itemId"], c["spec"], c["operation"]) for c in body["changes"]] == [
        ("Hörnli", "500 g", "TO_PURCHASE"),
        ("WC-Papier", "", "TO_PURCHASE"),
    ]
    # No item uuid: Bring! then updates the item of that name instead of adding a second one (bring-api update_item)
    assert all("uuid" not in c for c in body["changes"])


@pytest.mark.parametrize(
    "answer", [urllib.error.URLError("down"), TimeoutError(), b"kein json"], ids=["unreachable", "timeout", "garbage"]
)
def test_failures_are_bring_failed(network, answer):
    network[1].append(answer)
    with pytest.raises(bring.BringFailed) as failed:
        bring.HttpBring().login("a@b.ch", "geheim")
    assert failed.value.code == "bring_failed"


def test_server_error_after_login_is_bring_failed(network):
    network[1].extend([AUTH, _http_error(500)])
    client = bring.HttpBring()
    with pytest.raises(bring.BringFailed) as failed:
        client.add(client.login("a@b.ch", "geheim"), "l-1", [("Milch", "")])
    assert failed.value.code == "bring_failed"


def test_fake_used_when_asked(monkeypatch):
    monkeypatch.setenv("BRING_FAKE", "1")
    assert isinstance(bring.client(), bring.FakeBring)
    monkeypatch.delenv("BRING_FAKE")
    assert isinstance(bring.client(), bring.HttpBring)


def test_cut_off_answer_is_bring_failed(network):
    network[1].append(http.client.IncompleteRead(b"{"))
    with pytest.raises(bring.BringFailed) as failed:
        bring.HttpBring().login("a@b.ch", "geheim")
    assert failed.value.code == "bring_failed"


def test_list_gone_is_its_own_failure(network):
    network[1].extend([AUTH, _http_error(404)])
    client = bring.HttpBring()
    with pytest.raises(bring.BringFailed) as failed:
        client.add(client.login("a@b.ch", "geheim"), "l-weg", [("Milch", "")])
    assert failed.value.code == "bring_list_gone"
