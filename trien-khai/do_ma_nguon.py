"""Đo lại cùng tập mã nguồn để theo dõi mục tiêu đã chốt, không tính dữ liệu/font."""

import argparse
import json
import subprocess
from pathlib import Path

BASELINE = "c8eb9901adc010e16e6a0103ef3bcc368521cdd1"
BASELINE_LINES = 55311
TARGET_LINES = 110622
EXTENSIONS = {".py", ".js", ".cjs", ".html", ".css", ".sh"}
ROOT = Path(__file__).resolve().parents[1]


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT)


def measure(reference=None):
    if reference:
        revision = (
            git("rev-parse", "--verify", "--end-of-options", reference + "^{commit}")
            .decode()
            .strip()
        )
        names = git("ls-tree", "-r", "--name-only", "-z", revision).decode().split("\0")
    else:
        revision = None
        names = (
            git("ls-files", "-c", "-o", "--exclude-standard", "-z").decode().split("\0")
        )
    rows = []
    for name in sorted(set(names)):
        if not name or Path(name).suffix not in EXTENSIONS:
            continue
        if revision:
            raw = git("show", revision + ":" + name)
        else:
            source = ROOT / name
            if source.is_symlink() or not source.is_file():
                continue
            raw = source.read_bytes()
        rows.append({"path": name, "lines": len(raw.decode("utf-8-sig").splitlines())})
    total = sum(row["lines"] for row in rows)
    return {
        "baseline_commit": BASELINE,
        "baseline_lines": BASELINE_LINES,
        "target_lines": TARGET_LINES,
        "reference": revision or "working-tree",
        "source_lines": total,
        "source_files": len(rows),
        "added_since_baseline": total - BASELINE_LINES,
        "remaining_lines": max(0, TARGET_LINES - total),
        "target_reached": total >= TARGET_LINES,
        "method": "physical-lines; py,js,cjs,html,css,sh; tracked-and-unignored; tests-included; data-and-docs-excluded",
        "files": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref")
    parser.add_argument("--files", action="store_true")
    args = parser.parse_args()
    result = measure(args.ref)
    if not args.files:
        result.pop("files")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
