import pytest

from app.core.paths import validate_id


def test_validate_id_ok():
    assert validate_id("proj_abc123") == "proj_abc123"


def test_validate_id_rejects_traversal():
    with pytest.raises(ValueError):
        validate_id("../etc")
    with pytest.raises(ValueError):
        validate_id("foo/bar")
