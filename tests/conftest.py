from importlib.resources import files
import json
import random
import pytest


def pytest_addoption(parser):
    parser.addoption("--all", action="store_true", help="gather and check all lparchive.org content")
    parser.addoption("--random", action="store_true", help="gather and check 5 random lparchive.org content")
    parser.addoption("--specific", action="store", help="gather and check a specific lparchive.org content")

def pytest_generate_tests(metafunc):
    all_b3sums_json = files("tests.resources").joinpath("all_b3sum.json")
    with open(all_b3sums_json, "r") as f:
        all_b3sums = json.load(f)

    if metafunc.config.getoption("all"):
        if "lp" in metafunc.fixturenames and "b3sum" in metafunc.fixturenames:
            metafunc.parametrize(("lp", "b3sum"), [(b3sum["lp"], b3sum["b3sum"]) for b3sum in all_b3sums])
    elif metafunc.config.getoption("specific"):
        if "lp" in metafunc.fixturenames and "b3sum" in metafunc.fixturenames:
            name = metafunc.config.getoption("--specific")
            try:
                item = next(x for x in all_b3sums if x["lp"] == name)
            except StopIteration:
                raise ValueError(f"no such lparchive.org content: {name}") from None
            metafunc.parametrize(("lp", "b3sum"), [(item["lp"], item["b3sum"])])
    elif metafunc.config.getoption("random"):
        if "lp" in metafunc.fixturenames and "b3sum" in metafunc.fixturenames:
            metafunc.parametrize(("lp", "b3sum"), [(b3sum["lp"], b3sum["b3sum"]) for b3sum in random.sample(all_b3sums, 5)])
    else:
        if "lp" in metafunc.fixturenames and "b3sum" in metafunc.fixturenames:
            metafunc.parametrize(("lp", "b3sum"), [(None, None)])
