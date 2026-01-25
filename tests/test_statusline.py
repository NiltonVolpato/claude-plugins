import pytest


def test_works():
    with pytest.raises(ZeroDivisionError):
        _ = 1 / 0
