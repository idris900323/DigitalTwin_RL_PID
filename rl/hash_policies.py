"""Write SHA-256 hashes of every policy file of a run into each seed's meta.json (``policy_files_sha256``).

    python rl/hash_policies.py rl/policies/ppo_v2
"""

import hashlib
import json
import pathlib
import sys


def main(run_dir):
    for d in sorted(pathlib.Path(run_dir).glob("seed_*")):
        meta_path = d / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["policy_files_sha256"] = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(d.glob("*.zip"))}
        meta_path.write_text(json.dumps(meta, indent=2, default=str) + "\n", encoding="utf-8", newline="\n")
        print(d.name, meta["policy_files_sha256"])


if __name__ == "__main__":
    main(sys.argv[1])
