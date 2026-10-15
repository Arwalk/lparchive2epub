def pytest_addoption(parser):
    parser.addoption("--live", action="store_true",
                     help="also run the tests that build Let's Plays from lparchive.org (network, ~1 minute)")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--live"):
        return
    import pytest
    skip = pytest.mark.skip(reason="needs --live: builds Let's Plays from lparchive.org")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)
