"""Collect Microsoft.AspNetCore.App major runtime versions and iterate them.

Two modes back a CSV ``# LOOP`` so a test can adapt to whatever .NET runtimes a
machine actually has (8, 9, 10, 11, ...) instead of hard-coding them:

  collect --state FILE
      Query the installed runtimes (``dotnet --list-runtimes``) and the active
      SDK version (``dotnet --version``), then write ``{"sdk", "majors", "idx"}``
      to FILE (``idx`` reset to 0) and print ``<sdk>\t<comma-joined majors>`` so
      the runner can capture the SDK version (``$.cols[0]``).

  next --state FILE
      Print the next major version (one per call) as ``<major>\tnet<major>.0``
      and advance the saved index. Exit 0 while a version remains, 1 once the
      list is exhausted -- so a ``# LOOP`` while-condition stops cleanly.

The majors are de-duplicated and sorted ascending for reproducibility.

NOTE: the CSV `# LOOP` row that drives ``next`` sets ``max_iter=15`` as a
safety cap on iteration count -- comfortably above the 8/9/10 majors in use
today. If a machine is ever set up with more than 15 installed
Microsoft.AspNetCore.App majors at once, raise that CSV's ``max_iter`` value
accordingly (this script itself has no built-in limit on how many majors it
will collect/yield).
"""
import argparse
import json
import re
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _dotnet(args):
    return subprocess.run(["dotnet"] + args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def collect(state_path):
    ver = _dotnet(["--version"])
    sdk = ""
    if ver.stdout and ver.stdout.strip():
        sdk = ver.stdout.strip().splitlines()[0].strip()

    rt = _dotnet(["--list-runtimes"])
    majors = []
    for line in (rt.stdout or "").splitlines():
        m = re.match(r"\s*Microsoft\.AspNetCore\.App\s+(\d+)\.", line)
        if m:
            maj = int(m.group(1))
            if maj not in majors:
                majors.append(maj)
    majors.sort()
    if not majors:
        print("ERROR: no Microsoft.AspNetCore.App runtimes found", file=sys.stderr)
        sys.exit(1)

    state = {"sdk": sdk, "majors": majors, "idx": 0}
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f)
    print(f"{sdk}\t{','.join(str(x) for x in majors)}")


def nxt(state_path):
    with open(state_path, "r", encoding="utf-8") as f:
        state = json.load(f)
    idx = int(state.get("idx", 0))
    majors = state.get("majors", [])
    if idx >= len(majors):
        print("done: no more versions", file=sys.stderr)
        sys.exit(1)
    maj = majors[idx]
    state["idx"] = idx + 1
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f)
    print(f"{maj}\tnet{maj}.0")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mode", choices=["collect", "next"])
    p.add_argument("--state", required=True, help="path to the JSON state file")
    a = p.parse_args()
    if a.mode == "collect":
        collect(a.state)
    else:
        nxt(a.state)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)
