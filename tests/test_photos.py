import io

import pillow_heif
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
