"""G1.6: committed policy + metadata are consistent and the feature fixture is not stale."""

import hashlib
import json
import pathlib

import numpy as np
import pytest

import autotune_360.train_autotune_360 as T

DIR = pathlib.Path(__file__).resolve().parents[1] / "autotune_360"
FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "feature_vectors.json"


def test_meta_matches_policy_file():
    meta = json.loads((DIR / "autotune_policy_360.meta.json").read_text())
    assert meta["policy_sha256"] == hashlib.sha256((DIR / "autotune_policy_360.json").read_bytes()).hexdigest()
    assert meta["pre_validation_prototype"] is True
    assert meta["feature_function_version"] == T.FEATURE_VERSION
    for key in ("seed", "iterations", "contexts_per_iteration", "samples_per_context", "learning_rate", "adam",
                "gain_bounds", "payload_ranges", "config_sha256", "git_commit", "date_utc", "runtime_s",
                "numpy", "python", "held_out"):
        assert key in meta, key


def test_feature_fixture_regenerates_identically():
    fx = json.loads(FIXTURE.read_text())
    for c in fx["cases"]:
        f = T.features(*(np.array([c[k]]) for k in ("mass", "len")), np.array([float(c["gravity"])]),
                       np.array([c["vPct"]]), np.array([c["target"]]))[0]
        assert f.tolist() == pytest.approx(c["features"], abs=1e-12)


def test_child_generators_are_independent_of_call_order():
    a = T.child_rngs(0)
    first = (a["context"].random(), a["action"].random())
    b = T.child_rngs(0)
    second_order = (b["action"].random(), b["context"].random())
    assert first[0] == second_order[1] and first[1] == second_order[0]


def test_short_training_is_deterministic(tmp_path):
    """Same seed twice -> byte-identical policy file (a fast smoke version of the full check)."""
    paths = []
    for i in range(2):
        out = tmp_path / f"p{i}.json"
        T.main(["--seed", "3", "--iters", "2", "--contexts", "8", "--samples", "2", "--out", str(out)])
        paths.append(out.read_bytes())
    assert paths[0] == paths[1]
    assert (tmp_path / "p0.meta.json").exists()
