import base64

from app.connectors.control4_media import _decode_artwork_url
from app.source_icons import load_builtin_source_icon


def test_control4_broadcast_artwork_from_media_metadata():
    path = "17/17037996-4008-402e-9826-82b8fc58faca"
    encoded = base64.b64encode(path.encode()).decode()
    assert _decode_artwork_url(encoded) == f"http://director/images/broadcast/{path}.jpg"
    assert _decode_artwork_url(base64.b64encode(b"../etc/passwd").decode()) == ""


def test_internet_radio_has_local_icon():
    mime, content = load_builtin_source_icon("Internet Radio")
    assert mime == "image/png"
    assert content.startswith(b"\x89PNG\r\n\x1a\n")
