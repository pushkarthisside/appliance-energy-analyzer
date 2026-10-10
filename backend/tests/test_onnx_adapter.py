"""onnx_seq2point adapter contract (§8.1) and model-load failure handling (TS-F-01).

The ONNX model here is built by hand: it returns the centre value of each normalized
window, so expected outputs are exact. This tests the adapter's windowing, NaN rules,
normalization and batching, not any model's accuracy.
"""

import json
import shutil

import numpy as np
import onnx
import pytest
from conftest import ARTIFACTS
from fastapi.testclient import TestClient
from onnx import TensorProto, helper

from app.config import Settings
from app.main import create_app
from app.nilm.adapters.onnx_seq2point import BATCH_SIZE, OnnxSeq2PointAdapter

NORM = {"mains_mean": 500.0, "mains_std": 250.0, "app_mean": 100.0, "app_std": 50.0}


def centre_model(path, window=99):
    x = helper.make_tensor_value_info("X", TensorProto.FLOAT, [None, window])
    y = helper.make_tensor_value_info("Y", TensorProto.FLOAT, [None, 1])
    idx = helper.make_tensor("idx", TensorProto.INT64, [1], [window // 2])
    node = helper.make_node("Gather", ["X", "idx"], ["Y"], axis=1)
    graph = helper.make_graph([node], "centre", [x], [y], initializer=[idx])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 8
    onnx.save(model, str(path))
    return path


@pytest.fixture
def adapter(tmp_path):
    return OnnxSeq2PointAdapter.from_file(centre_model(tmp_path / "m.onnx"), 99, NORM)


def test_normalization_round_trip_and_edges(adapter):
    mains = np.linspace(0, 1000, 500)
    out = adapter.predict(mains)
    # centre value normalized then de-normalized with the appliance stats
    expected = (mains - 500.0) / 250.0 * 50.0 + 100.0
    assert np.isnan(out[:49]).all() and np.isnan(out[-49:]).all()  # window beyond the series
    np.testing.assert_allclose(out[49:-49], expected[49:-49], rtol=1e-5)


def test_nan_anywhere_in_window_gives_nan(adapter):
    mains = np.full(300, 500.0)
    mains[150] = np.nan
    out = adapter.predict(mains)
    assert np.isnan(out[101:200]).all()  # every window covering minute 150
    assert not np.isnan(out[100]) and not np.isnan(out[200])


def test_batching_matches_single_pass(adapter):
    mains = np.random.default_rng(1).uniform(0, 3000, BATCH_SIZE * 2 + 500)
    out = adapter.predict(mains)
    assert np.isfinite(out[49:-49]).all() and out.size == mains.size


def test_short_series_and_bad_config(tmp_path, adapter):
    assert np.isnan(adapter.predict(np.ones(50))).all()
    path = centre_model(tmp_path / "x.onnx")
    with pytest.raises(ValueError):
        OnnxSeq2PointAdapter.from_file(path, 98, NORM)  # even window
    with pytest.raises(ValueError):
        OnnxSeq2PointAdapter.from_file(path, 99, {**NORM, "mains_std": None})
    with pytest.raises(FileNotFoundError):
        OnnxSeq2PointAdapter.from_file(tmp_path / "missing.onnx", 99, NORM)


def test_go_model_with_missing_file_is_load_failed_and_app_stays_ready(tmp_path):
    data = tmp_path / "artifacts"
    shutil.copytree(ARTIFACTS, data)
    registry = json.loads((data / "registry.json").read_text(encoding="utf-8"))
    for entry in registry["appliances"]:
        if entry["id"] == "fridge":
            entry.update(status="go", on_threshold_w=50.0, energy_uncertainty_pct=20.0, min_excess_kwh_week=1.0,
                         model={"version": "v1", "path": "models/fridge/v1/model.onnx", "window_minutes": 99, "norm": NORM})
    (data / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
    frontend = tmp_path / "dist"
    frontend.mkdir()
    settings = Settings.from_env({"AEA_DATA_DIR": str(data), "AEA_FRONTEND_DIR": str(frontend)})
    with TestClient(create_app(settings)) as c:
        h = c.get("/api/health").json()
    fridge = next(a for a in h["appliances"] if a["id"] == "fridge")
    assert fridge["runtime_state"] == "load_failed" and "not found" in fridge["detail"]
    assert h["ready"] is True and h["status"] == "degraded"
