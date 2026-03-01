import pytest

@pytest.fixture
def vcr_config():
    return {
        "filter_headers": [("authorization", "XXXXX"), ("x-goog-api-key", "XXXXX")],
        "ignore_localhost": True,
    }
