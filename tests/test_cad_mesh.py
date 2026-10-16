"""The one CAD mesh used by every demo (cad/JGB37-520_converted.glb, embedded in the browser page)."""

import pathlib

import pytest

trimesh = pytest.importorskip("trimesh")

GLB = pathlib.Path(__file__).resolve().parents[1] / "cad" / "JGB37-520_converted.glb"


def test_mesh_density_and_size():
    assert 1.0e6 < GLB.stat().st_size < 3.0e6                      # about 1.6 MB (the 518k-triangle version was 11 MB)
    sc = trimesh.load(GLB)
    faces = sum(g.faces.shape[0] for g in sc.geometry.values())
    assert 60_000 < faces < 120_000                                # about 83k triangles; no visible gain above this


def test_parts_and_bounds_unchanged_by_tessellation():
    sc = trimesh.load(GLB)
    names = list(sc.geometry)
    assert len(names) == 11
    assert any("MOTOR SHAFT" in n for n in names) and any("SHAFT COUPLER" in n for n in names)   # rotating parts by name
    b = sc.bounds
    assert b[0].tolist() == pytest.approx([-0.0185, -0.0185, -0.0569], abs=1e-4)
    assert b[1].tolist() == pytest.approx([0.0185, 0.0185, 0.0215], abs=1e-4)
