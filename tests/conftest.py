import pytest

from disposable_email.checks import reset_caches


@pytest.fixture(autouse=True)
def fresh_caches():
    reset_caches()
    yield
    reset_caches()


def flag_on():
    return True


def flag_off():
    return False


def flag_broken():
    raise RuntimeError("config table missing")
