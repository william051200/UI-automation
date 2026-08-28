"""Locate the Visual Studio ``devenv.exe`` for the installed VS, edition/version/channel agnostic.

Primary detection uses ``vswhere`` (shipped with every VS installer at a fixed,
documented path). Insiders/Preview channels are not always reported by vswhere,
so several fallbacks run in order until a real ``devenv.exe`` is found:
  1. explicit override (``--path`` arg or ``VSDEVENV`` env var)
  2. when ``--prerelease`` is set, filesystem scan for Insiders/Preview
  3. vswhere ``-latest``
  4. vswhere ``-prerelease -latest`` (Preview/Insiders that register normally)
  5. registry ``HKLM\\...\\VisualStudio\\SxS\\VS7`` install paths
  6. filesystem scan of ``Microsoft Visual Studio\\*\\*\\Common7\\IDE\\devenv.exe``
     under both Program Files roots (catches Insiders dirs)
Prints the full path to ``devenv.exe`` as the first stdout column so a test can
capture it via ``$.cols[0]`` and use ``{vars.devenv}`` as a launch executable.
Exit codes:  0 OK   2 no VS install found
"""
import argparse, glob, os, subprocess, sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _program_files_roots():
    roots = []
    for var in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        v = os.environ.get(var)
        if v and v not in roots:
            roots.append(v)
    for fb in (r"C:\Program Files", r"C:\Program Files (x86)"):
        if fb not in roots:
            roots.append(fb)
    return roots


def _vswhere_path():
    base = os.environ.get("ProgramFiles(x86)") or r"C:\Program Files (x86)"
    return os.path.join(base, "Microsoft Visual Studio", "Installer", "vswhere.exe")


def _from_vswhere(prerelease):
    vswhere = _vswhere_path()
    if not os.path.isfile(vswhere):
        return ""
    cmd = [vswhere, "-latest", "-products", "*",
           "-requires", "Microsoft.VisualStudio.Component.CoreEditor",
           "-property", "productPath"]
    if prerelease:
        cmd.insert(1, "-prerelease")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    except Exception:
        return ""
    lines = (r.stdout or "").strip().splitlines()
    return lines[0].strip() if lines else ""


def _from_registry():
    try:
        import winreg
    except Exception:
        return ""
    for hive, key in ((winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\VisualStudio\SxS\VS7"),
                      (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\VisualStudio\SxS\VS7")):
        try:
            with winreg.OpenKey(hive, key) as k:
                vals = []
                for i in range(winreg.QueryInfoKey(k)[1]):
                    name, val, _ = winreg.EnumValue(k, i)
                    vals.append((name, val))
                for _, base in sorted(vals, reverse=True):
                    exe = os.path.join(base, "Common7", "IDE", "devenv.exe")
                    if os.path.isfile(exe):
                        return exe
        except OSError:
            continue
    return ""


def _from_filesystem():
    candidates = []
    for root in _program_files_roots():
        pat = os.path.join(root, "Microsoft Visual Studio", "*", "*",
                           "Common7", "IDE", "devenv.exe")
        candidates.extend(glob.glob(pat))
    candidates = [c for c in candidates if os.path.isfile(c)]
    return sorted(candidates, reverse=True)[0] if candidates else ""


def _from_prerelease_filesystem():
    candidates = []
    for root in _program_files_roots():
        for edition in ("Insiders", "Preview"):
            pat = os.path.join(root, "Microsoft Visual Studio", "*", edition,
                               "Common7", "IDE", "devenv.exe")
            candidates.extend(glob.glob(pat))
    candidates = [c for c in candidates if os.path.isfile(c)]
    return sorted(candidates, reverse=True)[0] if candidates else ""


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--prerelease", action="store_true",
                   help="prefer prerelease (preview/Insiders) over stable")
    p.add_argument("--path", default=os.environ.get("VSDEVENV"),
                   help="explicit devenv.exe path override (or set VSDEVENV)")
    a = p.parse_args()

    sources = [
        lambda: a.path,
        lambda: _from_prerelease_filesystem() if a.prerelease else "",
        lambda: _from_vswhere(a.prerelease),
        lambda: _from_vswhere(True),
        _from_registry,
        _from_filesystem,
    ]
    for fn in sources:
        path = (fn() or "").strip()
        if path and os.path.isfile(path):
            print(path)
            return

    print("ERROR: no Visual Studio devenv.exe found (vswhere, registry, and "
          "filesystem scan all failed)", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)
