import base64

from app.connectors.control4_media import _decode_artwork_url


def test_control4_broadcast_artwork_from_media_metadata():
    path = "17/17037996-4008-402e-9826-82b8fc58faca"
    encoded = base64.b64encode(path.encode()).decode()
    assert _decode_artwork_url(encoded) == f"http://director/images/broadcast/{path}.jpg"
    assert _decode_artwork_url(base64.b64encode(b"../etc/passwd").decode()) == ""
