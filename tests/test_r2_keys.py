import pytest

from roadsift_adapters.adapters.storage.r2 import _safe_key
from roadsift_adapters.ports.object_store import UnsafeObjectKeyError


def test_safe_key():
    assert _safe_key("raw/project/run/frame.jpg") == "raw/project/run/frame.jpg"


@pytest.mark.parametrize("key", ["", "/etc/passwd", "../x", "a/../../x"])
def test_unsafe_key(key):
    with pytest.raises(UnsafeObjectKeyError):
        _safe_key(key)
