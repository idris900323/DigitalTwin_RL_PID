"""Regenerate JGB37-520_converted.glb from the source STEP file.

The committed .glb was produced with exactly this call. Re-run it if the
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
SRC = HERE / "jgb37-520-1.snapshot.4_REFERENCE_NOT_VERIFIED_MATCH" / "JGB37-520.STEP"
DST = HERE / "JGB37-520_converted.glb"

if __name__ == "__main__":
    cascadio.step_to_glb(str(SRC), str(DST))
    print(f"Converted {SRC.name} -> {DST}")
