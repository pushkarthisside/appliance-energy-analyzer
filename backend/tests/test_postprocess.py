"""TS-U-11 — clip, proportional scaling, other >= 0, sum <= mains (§8.3)."""

import numpy as np
import pytest

from app.nilm.postprocess import postprocess


def test_no_real_models_means_everything_is_other():
    mains = np.array([100.0, np.nan, 50.0])
    estimates, other = postprocess(mains, {})
    assert estimates == {}
    np.testing.assert_array_equal(other, mains)


def test_clip_scale_and_residual():
    mains = np.array([1000.0, 1000.0, 1000.0, np.nan])
    estimates, other = postprocess(
        mains,
        {
            "a": np.array([-50.0, 600.0, 900.0, 10.0]),
            "b": np.array([100.0, 600.0, np.nan, 10.0]),
        },
    )
    # minute 0: a clipped to 0, b = 100 -> other 900
    assert estimates["a"][0] == 0 and estimates["b"][0] == 100 and other[0] == 900
    # minute 1: sum 1200 > 1000 -> scaled by 1000/1200
    assert estimates["a"][1] == pytest.approx(500.0) and estimates["b"][1] == pytest.approx(500.0)
    assert other[1] == pytest.approx(0.0)
    # minute 2: b is NaN -> counts as 0 in the sum but stays missing for b
    assert estimates["a"][2] == pytest.approx(900.0) and np.isnan(estimates["b"][2])
    assert other[2] == pytest.approx(100.0)
    # minute 3: mains missing -> missing for everything
    assert np.isnan(estimates["a"][3]) and np.isnan(estimates["b"][3]) and np.isnan(other[3])


def test_sum_never_exceeds_mains_and_other_is_non_negative():
    rng = np.random.default_rng(0)
    mains = rng.uniform(0, 3000, 500)
    estimates, other = postprocess(mains, {"a": rng.uniform(-500, 4000, 500), "b": rng.uniform(-500, 4000, 500)})
    total = estimates["a"] + estimates["b"]
    assert (total <= mains + 1e-9).all()
    assert (other >= 0).all()
    np.testing.assert_allclose(total + other, mains)
