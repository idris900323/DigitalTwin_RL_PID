import pytest

from tests.helpers import load_config


@pytest.fixture(scope="session")
def cfg():
    """YAML config loaded once per session (treat as read-only)."""
    return load_config()
