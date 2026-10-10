"""TS-U-10 — banned-word regex on actions.json and every generated string (§6.4)."""

import json

import pytest
from conftest import ARTIFACTS, SAMPLE_DIR

from app.analytics.wording import assert_clean, find_banned
from app.ingest.bundle import load_bundle
from app.nilm.registry import load_registry
from app.pipeline import apply_bill, run_pipeline


def strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from strings(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from strings(value)


@pytest.mark.parametrize("word", ["fault", "faulty", "broken", "wasted", "wastage", "cause", "caused"])
def test_regex_catches_banned_words(word):
    assert find_banned(f"The AC is {word} today")
    with pytest.raises(ValueError):
        assert_clean(word.upper())


def test_regex_allows_neutral_words():
    assert not find_banned("The estimated increase is associated with longer operating time.")


def test_actions_file_is_clean():
    actions = json.loads((ARTIFACTS / "config" / "actions.json").read_text(encoding="utf-8"))
    for text in strings(actions):
        assert not find_banned(text), text


def test_generated_response_and_manifest_are_clean():
    actions = json.loads((ARTIFACTS / "config" / "actions.json").read_text(encoding="utf-8"))
    bundle = load_bundle(SAMPLE_DIR)
    result = run_pipeline(bundle, load_registry(ARTIFACTS / "registry.json"), "none")
    response = apply_bill(result, 4200, 500, actions).model_dump(mode="json")
    for text in [*strings(response["issues"]), *strings(response["source"]), *strings(bundle.manifest)]:
        assert not find_banned(text), text
