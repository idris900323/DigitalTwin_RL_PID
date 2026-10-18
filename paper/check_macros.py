"""Static check (no LaTeX needed): every number macro used by the manuscript is defined in generated/numbers.tex."""

import glob
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
defs = set(re.findall(r"\\newcommand\{\\(\w+)\}", (HERE / "generated" / "numbers.tex").read_text(encoding="utf-8")))
used = set()
for f in glob.glob(str(HERE / "manuscript" / "sections" / "*.tex")) + [str(HERE / "manuscript" / "main.tex")]:
    used |= set(re.findall(r"\\((?:ConfThree|ExplThree|VTwo|VFourPpo|VFourSac|VFourTd|Ver|PaperCommit)\w*)", pathlib.Path(f).read_text(encoding="utf-8")))
missing = sorted(used - defs)
print(f"{len(used)} macros used, {len(defs)} defined; missing: {missing}")
raise SystemExit(1 if missing else 0)
