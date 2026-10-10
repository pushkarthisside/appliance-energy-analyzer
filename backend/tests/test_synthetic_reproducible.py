"""test_synthetic_reproducible — regeneration is byte-identical (§10.3)."""

import json

from conftest import SAMPLE_DIR

from common import SCENARIO_PATH, config_sha256, load_scenario, window_csv_bytes
from synthetic.generate import generate_trace

from app.nilm.preprocess import window_start


def test_regenerated_traces_match_committed_files_byte_for_byte():
    scenario = load_scenario()
    start = window_start(scenario["window"]["start"])
    for appliance in scenario["appliances"]:
        first = window_csv_bytes(start, generate_trace(appliance, 21))
        second = window_csv_bytes(start, generate_trace(appliance, 21))
        assert first == second
        committed = (SAMPLE_DIR / "synthetic" / f"{appliance['id']}.csv").read_bytes()
        assert first == committed, f"{appliance['id']} differs from the committed trace; rebuild artifacts"


def test_manifest_records_the_scenario_config_hash_and_seeds():
    manifest = json.loads((SAMPLE_DIR / "manifest.json").read_text(encoding="utf-8"))
    scenario = load_scenario()
    expected_hash = config_sha256(SCENARIO_PATH)
    assert manifest["synthetic_background"]["config_sha256"] == expected_hash
    assert manifest["synthetic_background"]["seed"] == scenario["background"]["seed"]
    seeds = {a["id"]: a["seed"] for a in scenario["appliances"]}
    for app in manifest["synthetic_appliances"]:
        assert app["generator"]["config_sha256"] == expected_hash
        assert app["generator"]["seed"] == seeds[app["id"]]


def test_different_seed_gives_a_different_trace():
    appliance = dict(load_scenario()["appliances"][0])
    a = generate_trace(appliance, 21)
    appliance["seed"] = appliance["seed"] + 1
    assert not (a == generate_trace(appliance, 21)).all()
