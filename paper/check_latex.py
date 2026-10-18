r"""Static LaTeX checks that need no TeX installation. This does NOT compile anything and a clean report does not mean the paper compiles.

Checks: \input targets (resolved from manuscript/, where TeX runs), figure files, label/ref/cite consistency, unverified references that are cited,
begin/end and brace balance, unescaped underscores in text, odd numbers of dollar signs per paragraph, tabular column counts, number macros and leftover
PENDING/TODO markers. Writes paper/static_check_report.md and exits non-zero if there are warnings.
"""

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
MAN = HERE / "manuscript"
GEN = HERE / "generated"
UNVERIFIED = {"wilcoxon1945individual", "lawrence2021shallow", "tobin2017domain"}
warnings = []


def warn(f, msg):
    warnings.append(f"{pathlib.Path(f).relative_to(HERE)}: {msg}")


def strip_comments(s):
    return re.sub(r"(?<!\\)%.*", "", s)


def files():
    return [MAN / "main.tex"] + sorted((MAN / "sections").glob("*.tex")) + sorted(GEN.glob("tab_*.tex"))


raw = {f: f.read_text(encoding="utf-8") for f in files()}
texts = {f: strip_comments(t) for f, t in raw.items()}
all_text = "\n".join(texts.values())

# 1. inputs and figures
for f, t in texts.items():
    for m in re.finditer(r"\\(input|InputIfFileExists)\{([^}]+)\}", t):
        p = MAN / m.group(2)                                   # TeX resolves \input from the directory it runs in (manuscript/)
        if not (p.exists() or p.with_suffix(".tex").exists()) and m.group(1) == "input":
            warn(f, f"\\input target not found: {m.group(2)}")
    for m in re.finditer(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", t):
        if not (GEN / m.group(1)).exists():
            warn(f, f"figure not found in generated/: {m.group(1)}")

# 2. labels, refs, cites
labels = re.findall(r"\\label\{([^}]+)\}", all_text)
for dup in sorted({x for x in labels if labels.count(x) > 1}):
    warn(MAN / "main.tex", f"duplicate label {dup}")
refs = set()
for m in re.finditer(r"\\(?:ref|eqref|autoref|cref|Cref)\{([^}]+)\}", all_text):
    refs |= set(m.group(1).split(","))
for r in sorted(refs - set(labels)):
    warn(MAN / "main.tex", f"\\ref to undefined label {r}")
for lab in sorted(set(labels) - refs):
    warn(MAN / "main.tex", f"label never referenced (harmless): {lab}")
bib = (HERE / "refs.bib").read_text(encoding="utf-8")
keys = set(re.findall(r"@\w+\{([^,]+),", bib))
cited = set()
for m in re.finditer(r"\\cite\{([^}]+)\}", all_text):
    cited |= {k.strip() for k in m.group(1).split(",")}
for k in sorted(cited - keys):
    warn(HERE / "refs.bib", f"cited key not in refs.bib: {k}")
for k in sorted(keys - cited):
    warn(HERE / "refs.bib", f"bib entry never cited: {k}")
for k in sorted(cited & UNVERIFIED):
    warn(HERE / "unverified_refs.md", f"cited reference is UNVERIFIED (verify by hand before submission): {k}")

# 3. balance checks
for f, t in texts.items():
    for env in sorted(set(re.findall(r"\\begin\{([^}]+)\}", t)) | set(re.findall(r"\\end\{([^}]+)\}", t))):
        b = len(re.findall(r"\\begin\{" + re.escape(env) + r"\}", t))
        e = len(re.findall(r"\\end\{" + re.escape(env) + r"\}", t))
        if b != e:
            warn(f, f"environment {env}: {b} begin vs {e} end")
    depth = 0
    for ch in re.sub(r"\\[{}]", "", t):
        depth += (ch == "{") - (ch == "}")
        if depth < 0:
            break
    if depth != 0:
        warn(f, f"unbalanced braces (depth {depth})")

# 4. text-level heuristics (sections only)
MATH_ENV = re.compile(r"\\begin\{(align\*?|equation\*?)\}.*?\\end\{\1\}", re.S)
for f in sorted((MAN / "sections").glob("*.tex")):
    t = MATH_ENV.sub(" ", texts[f])
    for para in re.split(r"\n\s*\n", t):
        if len(re.findall(r"(?<!\\)\$", para)) % 2:
            warn(f, f"odd number of $ in paragraph starting: {para.strip()[:50]!r}")
    plain = re.sub(r"\$[^$]*\$", " ", t)
    plain = re.sub(r"\\(?:texttt|label|ref|cite|input|includegraphics|SI|num|SIrange)(?:\[[^\]]*\])?\{[^}]*\}(?:\{[^}]*\})?", " ", plain)
    for m in re.finditer(r"(?<!\\)_", plain):
        line = plain[:m.start()].count("\n") + 1
        warn(f, f"unescaped underscore in text near line {line}: {plain[max(0, m.start() - 20):m.start() + 20].strip()!r}")
        break


# 5. tabular column counts
def balanced(text, start):
    depth = 0
    for i in range(start, len(text)):
        depth += text[i] == "{"
        depth -= text[i] == "}"
        if depth == 0:
            return text[start + 1:i], i + 1
    return text[start + 1:], len(text)


for f, t in texts.items():
    for m in re.finditer(r"\\begin\{tabular\}", t):
        spec, end = balanced(t, m.end())
        body = t[end:t.index(r"\end{tabular}", end)]
        ncol = len(re.findall(r"[lcrp]", re.sub(r"p\{[^}]*\}", "p", spec)))
        for row in body.split(r"\\"):
            r = re.sub(r"\\(toprule|midrule|bottomrule)", "", row).strip()
            if r and "&" in r:
                n = len(re.findall(r"(?<!\\)&", r)) + 1
                if n != ncol:
                    warn(f, f"tabular with {ncol} columns has a row with {n} cells: {r[:50]!r}")
                    break

# 6. number macros
defs = set()
for name in ("numbers.tex", "numbers_sens.tex", "numbers_kd.tex"):
    if (GEN / name).exists():
        defs |= set(re.findall(r"\\newcommand\{\\(\w+)\}", (GEN / name).read_text(encoding="utf-8")))
used = set(re.findall(r"\\((?:ConfThree|ExplThree|VTwo|VFourPpo|VFourSac|VFourTd|Ver|PaperCommit|SensVThree|SensVFour|KdBound)\w*)", all_text))
for k in sorted(used - defs):
    warn(MAN / "main.tex", f"number macro used but not defined: {k}")

# 6b. non-ASCII characters (pdflatex without a UTF-8 setup would choke on some of them)
for f, t in raw.items():
    bad = sorted({c for c in t if ord(c) > 127})
    if bad:
        warn(f, f"non-ASCII characters: {bad[:6]}")

# 7. leftover markers
for f, t in raw.items():
    for mk in ("PENDING", "TODO", "TBD", "PLACEHOLDER"):
        if mk in t:
            warn(f, f"contains marker {mk}")

report = ["# Static LaTeX check (no TeX toolchain; NOT a compile)", "",
          "Produced by `paper/check_latex.py`. A clean list would not mean the manuscript compiles; the compile and its warnings (overfull boxes, missing fonts or packages, "
          "bibliography style, float placement) must be checked on a machine with TeX.", "", f"{len(warnings)} warning(s):", ""]
report += [f"- {w}" for w in warnings] or ["- none"]
(HERE / "static_check_report.md").write_text("\n".join(report) + "\n", encoding="utf-8", newline="\n")
print("\n".join(report))
sys.exit(1 if warnings else 0)
