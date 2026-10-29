import io

import pillow_heif
import pytest
from PIL import Image

from app import config, photos
from helpers import create_recipe


def _image(size=(4032, 3024)) -> Image.Image:
    image = Image.new("RGB", size, (200, 120, 40))
    image.paste((20, 20, 20), (0, 0, size[0] // 4, size[1] // 4))
    return image


def _jpeg(orientation=6) -> bytes:
    """Like a phone photo: landscape pixels, EXIF saying "rotate 90°", and a GPS position."""
    exif = Image.Exif()
    exif[0x0112] = orientation
    exif[0x8825] = {1: "N", 2: (47.0, 22.0, 0.0)}
    out = io.BytesIO()
    _image().save(out, "JPEG", exif=exif)
    return out.getvalue()


def _heic() -> bytes:
    out = io.BytesIO()
    pillow_heif.from_pillow(_image((3000, 2000))).save(out, format="HEIF")
    return out.getvalue()


def _upload(client, headers, recipe_id, data, name="x.jpg", kind="image/jpeg"):
    return client.post(f"/api/recipes/{recipe_id}/photo", files={"file": (name, data, kind)}, headers=headers)


def test_iphone_photo_upright_small_and_clean(client, admin_headers):
    r = create_recipe(client, admin_headers)
    out = _upload(client, admin_headers, r["id"], _jpeg()).json()
    response = client.get(out["photo_url"])  # no login needed
    assert response.status_code == 200
    img = Image.open(io.BytesIO(response.content))
    assert img.format == "JPEG" and max(img.size) == 1600
    assert img.size[1] > img.size[0]  # turned upright
    assert not img.getexif()
    assert "immutable" in response.headers["cache-control"]


def test_heic_accepted(client, admin_headers):
    r = create_recipe(client, admin_headers)
    out = _upload(client, admin_headers, r["id"], _heic(), "IMG_1.HEIC", "image/heic")
    assert out.status_code == 200
    assert Image.open(io.BytesIO(client.get(out.json()["photo_url"]).content)).size == (1600, 1067)


def test_garbage_refused(client, admin_headers):
    r = create_recipe(client, admin_headers)
    response = _upload(client, admin_headers, r["id"], b"not an image")
    assert response.status_code == 400 and response.json()["detail"] == "photo_unreadable"


def test_replacing_deletes_old_file(client, admin_headers):
    r = create_recipe(client, admin_headers)
    first = _upload(client, admin_headers, r["id"], _jpeg()).json()["photo_url"].rsplit("/", 1)[1]
    _upload(client, admin_headers, r["id"], _jpeg())
    assert not (config.data_dir() / "photos" / first).exists()
    assert len(list((config.data_dir() / "photos").iterdir())) == 1


def test_remove_photo(client, admin_headers):
    r = create_recipe(client, admin_headers)
    _upload(client, admin_headers, r["id"], _jpeg())
    out = client.delete(f"/api/recipes/{r['id']}/photo", headers=admin_headers).json()
    assert out["photo_url"] is None
    assert list((config.data_dir() / "photos").iterdir()) == []


def test_photo_name_must_look_generated(client):
    assert client.get("/api/photos/..%2Fmeals.db").status_code == 404
    assert client.get("/api/photos/abc.jpg").status_code == 404
    assert client.get(f"/api/photos/{'0' * 32}.jpg").status_code == 404


def test_too_large(client, admin_headers, monkeypatch):
    monkeypatch.setattr(photos, "MAX_BYTES", 10)
    r = create_recipe(client, admin_headers)
    response = _upload(client, admin_headers, r["id"], _jpeg())
    assert response.status_code == 413 and response.json()["detail"] == "photo_too_large"


def test_upload_needs_login(client, admin_headers):
    r = create_recipe(client, admin_headers)
    assert _upload(client, {}, r["id"], _jpeg()).status_code == 401


def test_decompression_bomb_refused(client, admin_headers, monkeypatch):
    from PIL import Image

    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)
    r = create_recipe(client, admin_headers)
    response = _upload(client, admin_headers, r["id"], _jpeg())
    assert response.status_code == 400 and response.json()["detail"] == "photo_unreadable"


@pytest.fixture
def web(monkeypatch):
    """Fake DNS and HTTP for photo links: (host, path) to (status, headers, body)."""
    from app import fetch

    pages: dict = {}
    opened = []
    dns = {"public.example": ["93.184.216.34"], "nas.local": ["192.168.1.10"]}
    monkeypatch.setattr(fetch, "_resolve", lambda host, port: dns.get(host, [host]))

    def _open(scheme, host, port, target, ip, timeout):
        opened.append((host, target))
        return pages.get((host, target), (404, {}, b""))

    monkeypatch.setattr(fetch, "_open", _open)
    return pages, opened


JPEG = {"content-type": "image/jpeg"}
HTML = {"content-type": "text/html; charset=utf-8"}


def _from_link(client, headers, recipe_id, url):
    return client.post(f"/api/recipes/{recipe_id}/photo-url", json={"url": url}, headers=headers)


def test_photo_from_image_link(client, admin_headers, web):
    pages, _ = web
    pages[("public.example", "/pic.jpg")] = (200, JPEG, _jpeg())
    r = create_recipe(client, admin_headers)
    out = _from_link(client, admin_headers, r["id"], "https://public.example/pic.jpg")
    assert out.status_code == 200, out.text
    img = Image.open(io.BytesIO(client.get(out.json()["photo_url"]).content))
    assert max(img.size) == 1600 and not img.getexif()


def test_photo_from_page_link_takes_the_page_picture(client, admin_headers, web):
    pages, _ = web
    page = b'<html><head><meta property="og:image" content="/img/dish.jpg"></head><body>Rezept</body></html>'
    pages[("public.example", "/rezept")] = (200, HTML, page)
    pages[("public.example", "/img/dish.jpg")] = (200, JPEG, _jpeg())
    r = create_recipe(client, admin_headers)
    out = _from_link(client, admin_headers, r["id"], "https://public.example/rezept")
    assert out.status_code == 200, out.text
    assert out.json()["photo_url"]


def test_photo_from_link_replaces_old_file(client, admin_headers, web):
    pages, _ = web
    pages[("public.example", "/pic.jpg")] = (200, JPEG, _jpeg())
    r = create_recipe(client, admin_headers)
    first = _upload(client, admin_headers, r["id"], _jpeg()).json()["photo_url"].rsplit("/", 1)[1]
    _from_link(client, admin_headers, r["id"], "https://public.example/pic.jpg")
    assert not (config.data_dir() / "photos" / first).exists()


def test_photo_link_into_home_network_refused(client, admin_headers, web):
    _, opened = web
    r = create_recipe(client, admin_headers)
    for url in ("http://192.168.1.1/x.jpg", "http://nas.local/x.jpg"):
        response = _from_link(client, admin_headers, r["id"], url)
        assert response.status_code == 400 and response.json()["detail"] == "photo_link_failed"
    assert opened == []


def test_photo_link_without_a_picture(client, admin_headers, web):
    pages, _ = web
    pages[("public.example", "/text")] = (200, HTML, b"<html><body>Nur Text</body></html>")
    r = create_recipe(client, admin_headers)
    for url in ("https://public.example/text", "https://public.example/missing.jpg"):
        response = _from_link(client, admin_headers, r["id"], url)
        assert response.status_code == 400 and response.json()["detail"] == "photo_link_failed"
    assert client.get(f"/api/recipes/{r['id']}", headers=admin_headers).json()["photo_url"] is None


def test_photo_link_must_be_a_web_link(client, admin_headers):
    r = create_recipe(client, admin_headers)
    assert _from_link(client, admin_headers, r["id"], "file:///etc/passwd").status_code == 422
