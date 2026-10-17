def pytest_addoption(parser):
    parser.addoption("--offline", action="store_true",
                     help="skip the tests that build Let's Plays from lparchive.org (network, ~1 minute). "
                          "They run by default: they are the only check against the real site")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--offline"):
        return
    import pytest
    skip = pytest.mark.skip(reason="--offline: builds Let's Plays from lparchive.org")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)
