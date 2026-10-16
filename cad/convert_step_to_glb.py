"""Regenerate JGB37-520_converted.glb from the source STEP file.

The committed .glb was produced with exactly this call (tolerances below: about 83k triangles, 1.6 MB; the
default cascadio tolerances give a faceted 23k-triangle mesh, and 0.0005 gives a 518k-triangle 11 MB mesh that adds
no visible detail at the sizes the demos draw). The browser page embeds this same file (tools/generate_js_config.py). Re-run it if the
source STEP file in jgb37-520-1.snapshot.4_REFERENCE_NOT_VERIFIED_MATCH/ is
replaced (e.g. with an actual RMCS-3013/3070 CAD model, once/if one becomes
available -- see the provenance caveat in the repo README and
datasheet/parameter_table.md).

Run:
    python cad/convert_step_to_glb.py
"""

import pathlib

import cascadio

HERE = pathlib.Path(__file__).resolve().parent
TOL_LINEAR, TOL_ANGULAR = 0.003, 0.2   # cascadio tessellation tolerances (chosen: ~83k triangles)
SRC = HERE / "jgb37-520-1.snapshot.4_REFERENCE_NOT_VERIFIED_MATCH" / "JGB37-520.STEP"
DST = HERE / "JGB37-520_converted.glb"

if __name__ == "__main__":
    cascadio.step_to_glb(str(SRC), str(DST), tol_linear=TOL_LINEAR, tol_angular=TOL_ANGULAR)
    print(f"Converted {SRC.name} -> {DST}")
