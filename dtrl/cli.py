"""Command-line interface (see ``dtrl/__init__.py``). ``main(argv)`` returns the exit code, so it can be tested directly."""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys
from typing import List, Optional

import yaml

from models import ingest
from models.derive import derive_model
from models.motor_profile import ProfileError, library_dir, list_motors, load_profile


def _parse_answers(items: Optional[List[str]]) -> dict:
    out = {}
    for it in items or []:
        if "=" not in it:
            raise SystemExit(f"--answer expects key=value, got {it!r}")
        k, v = it.split("=", 1)
        out[k] = v
    return out


def cmd_motor_list(a) -> int:
    for m in list_motors():
        p = load_profile(m)
        print(f"{m:28s} {p.name}{'  [synthetic]' if p.synthetic else ''}")
    return 0


def cmd_motor_show(a) -> int:
    p = load_profile(a.motor)
    print(yaml.safe_dump(p.data, sort_keys=False))
    return 0


def cmd_motor_derive(a) -> int:
    answers = _parse_answers(a.answer)
    model = derive_model(load_profile(a.motor), answers)
    print(model.summary())
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps(model.to_dict(), indent=2), encoding="utf-8")
        print("wrote", a.out)
    return 0


def cmd_motor_add(a, input_fn=input, print_fn=print) -> int:
    src = pathlib.Path(a.input)
    text = ingest.read_input(src)
    cands = ingest.extract_candidates(text, source=src.name)
    if not cands:
        print_fn("no values could be extracted: type a profile YAML by hand (see motors/*/profile.yaml for the format)")
        return 2
    if a.decisions:
        d = json.loads(pathlib.Path(a.decisions).read_text(encoding="utf-8"))
        review = ingest.Review({int(k): v for k, v in d.get("decisions", {}).items()}, d.get("answers", {}))
        print_fn(ingest.confirmation_table(cands))
    else:
        review = ingest.review_interactively(cands, input_fn=input_fn, print_fn=print_fn)
    try:
        prof = ingest.build_profile(a.id, cands, review, identity={"manufacturer": a.manufacturer or "", "model": a.model or a.id},
                                    gearbox_figures_at=a.figures_at)
    except ProfileError as exc:
        print_fn(f"cannot create the profile: {exc}")
        return 1
    folder = library_dir() / a.id
    if (folder / "profile.yaml").exists() and not a.force:
        print_fn(f"{folder / 'profile.yaml'} already exists; use --force to overwrite")
        return 1
    (folder / "datasheets").mkdir(parents=True, exist_ok=True)
    shutil.copy(src, folder / "datasheets" / src.name)
    data = dict(prof.data)
    data["derivation_log"] = prof.derivation_log
    (folder / "profile.yaml").write_text("# Created by `python -m dtrl motor add` after the user confirmed each value.\n"
                                         + yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    print_fn(f"wrote {folder / 'profile.yaml'}; next: python -m dtrl motor derive --motor {a.id}")
    return 0


def _recommend(a):
    from tuning.recommend import recommend
    return recommend(a.motor, a.load, seed=a.seed, popsize=a.popsize, maxiter=a.maxiter, restarts=a.restarts, answers=_parse_answers(a.answer))


def cmd_tune(a) -> int:
    from tuning.report import write_report
    rec = _recommend(a)
    print(rec.format())
    if a.out_dir:
        for p in write_report(rec, a.out_dir):
            print("wrote", p)
    return 0


def cmd_export(a) -> int:
    from tuning import export
    rec = _recommend(a)
    text = {"py": export.to_python, "c": export.to_c, "arduino": export.to_arduino}[a.format](rec)
    if a.out:
        pathlib.Path(a.out).write_text(text, encoding="utf-8", newline="\n")
        print("wrote", a.out)
    else:
        print(text)
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="dtrl", description="Motor profiles, datasheet import, PID tuning (preliminary, not validated on hardware).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("motor").add_subparsers(dest="sub", required=True)
    m.add_parser("list").set_defaults(fn=cmd_motor_list)
    s = m.add_parser("show"); s.add_argument("motor"); s.set_defaults(fn=cmd_motor_show)
    s = m.add_parser("derive"); s.add_argument("--motor", required=True); s.add_argument("--answer", action="append", help="key=value, e.g. stall_current=stall")
    s.add_argument("--out"); s.set_defaults(fn=cmd_motor_derive)
    s = m.add_parser("add"); s.add_argument("--input", required=True, help=".txt/.csv/.pdf (or image with OCR)")
    s.add_argument("--id", required=True); s.add_argument("--manufacturer"); s.add_argument("--model")
    s.add_argument("--figures-at", default="motor", choices=["motor", "output"], help="default shaft for figures without their own shaft")
    s.add_argument("--decisions", help="JSON with {decisions: {id: accept|reject|{edit: ...}}, answers: {...}} instead of the interactive wizard")
    s.add_argument("--force", action="store_true"); s.set_defaults(fn=cmd_motor_add)
    for name, fn in (("tune", cmd_tune), ("export", cmd_export)):
        s = sub.add_parser(name)
        s.add_argument("--motor", required=True); s.add_argument("--load", required=True)
        s.add_argument("--seed", type=int, default=0); s.add_argument("--popsize", type=int, default=10); s.add_argument("--maxiter", type=int, default=25)
        s.add_argument("--restarts", type=int, default=2); s.add_argument("--answer", action="append")
        if name == "tune":
            s.add_argument("--out-dir")
        else:
            s.add_argument("--format", required=True, choices=["py", "c", "arduino"]); s.add_argument("--out")
        s.set_defaults(fn=fn)
    return ap


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    try:
        return a.fn(a)
    except (ProfileError, FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
