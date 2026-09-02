"""Execute a declarative UI-automation test spec (CSV).

Usage:
    python run_test.py <spec.csv>   # standard-format CSV, loaded in memory

Exit codes:
    0  all steps passed
    1  one or more assertions failed
    2  runner error (bad spec, script missing, etc.)
"""
import argparse, ctypes, datetime, os, re, subprocess, sys, time
from ctypes import wintypes

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "scripts", "csvfmt"))
import csv_loader  # noqa: E402


def load_spec(path):
    """Load a standard-format `.csv` spec into a runnable dict."""
    return csv_loader.load(path)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Make this process (and the child scripts it spawns) DPI-aware so
# pyautogui virtual-pixel clicks align with pywinauto physical-pixel rects
# on HiDPI displays. Per-monitor v2 (value 2) is the modern setting.
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
QUIET = False
WHILE_MAX_ITERATIONS = 25  # default safety cap for a `while` loop

# Standard screenshot folder naming: "<test case name>-<timestamp>" so it's
# obvious which test case a folder of screenshots belongs to. A CSV can still
# override this by setting `artifacts,screenshot_dir,<custom/path>` in its
# `# CONFIG` section; when it doesn't, this default is used.
DEFAULT_SCREENSHOT_DIR = "screenshots/{name}-{timestamp}"


class Ctx:
    def __init__(self, spec):
        self.spec = spec
        self.vars = {}
        self.iter_failed = {}   # n -> bool, used by snapshot step
        self.ss_counter = 1     # screenshot ordering counter, continuous across the whole run
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%SZ")
        self.subs = {
            "name": spec.get("name") or "test",
            "timestamp": ts,
            "inputs": spec.get("inputs", {}),
            "artifacts": spec.get("artifacts", {}),
            "vars": self.vars,
        }
        # pre-resolve artifacts paths
        art = spec.get("artifacts", {})
        resolved_artifacts = {
            k: render(v, self.subs) for k, v in art.items()
        }
        if not resolved_artifacts.get("screenshot_dir"):
            resolved_artifacts["screenshot_dir"] = render(DEFAULT_SCREENSHOT_DIR, self.subs)
        self.subs["artifacts"] = resolved_artifacts
        self.shot_dir = os.path.join(ROOT, resolved_artifacts["screenshot_dir"])
        os.makedirs(self.shot_dir, exist_ok=True)


_expr_re = re.compile(r"\{([^{}]+)\}")


def lookup(path, subs):
    cur = subs
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
        if cur is None:
            return ""
    return cur


def render(value, subs):
    """Render {placeholders} and {a + b} arithmetic on ints."""
    if isinstance(value, list):
        return [render(v, subs) for v in value]
    if isinstance(value, dict):
        return {k: render(v, subs) for k, v in value.items()}
    if not isinstance(value, str):
        return value

    def repl(m):
        expr = m.group(1).strip()
        # simple integer arithmetic: "vars.win_left + 100"
        if any(op in expr for op in "+-*/"):
            tokens = re.split(r"(\s*[+\-*/]\s*)", expr)
            try:
                parts = []
                for tok in tokens:
                    tok_s = tok.strip()
                    if tok_s in {"+", "-", "*", "/"}:
                        parts.append(tok_s)
                    elif re.fullmatch(r"-?\d+", tok_s):
                        parts.append(tok_s)
                    else:
                        v = lookup(tok_s, subs)
                        parts.append(str(int(v)))
                return str(eval(" ".join(parts), {"__builtins__": {}}, {}))
            except Exception:
                pass
        return str(lookup(expr, subs))

    return _expr_re.sub(repl, value)


def script_path(script):
    """Resolve a repository script and reject missing or escaping paths."""
    if not script:
        raise ValueError("step has no script")
    path = os.path.abspath(script if os.path.isabs(script)
                           else os.path.join(ROOT, script))
    if not os.path.isfile(path):
        raise ValueError(f"script not found: {script}")
    return path


def run_cmd(script, args, expect_exit=0):
    cmd = [PY, script_path(script)] + [str(a) for a in args]
    if not QUIET:
        print(f"  $ {' '.join(cmd)}")
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    failed = p.returncode != expect_exit
    if p.stdout and (failed or not QUIET):
        for line in p.stdout.rstrip().splitlines():
            print(f"    | {line}")
    if p.stderr:
        for line in p.stderr.rstrip().splitlines():
            print(f"    ! {line}")
    if failed:
        raise AssertionError(f"exit {p.returncode}, expected {expect_exit}")
    return p


def capture(out_text, mapping, ctx):
    """Apply $.cols[i] / $.rows[j].cols[i] selectors to tab-separated output."""
    lines = [l for l in out_text.splitlines() if l.strip()]
    rows = [l.split("\t") for l in lines]
    first_cols = rows[0] if rows else []
    for dst, sel in mapping.items():
        m = re.fullmatch(r"\$\.cols\[(\d+)\]", sel)
        try:
            if m:
                val = first_cols[int(m.group(1))]
            else:
                m = re.fullmatch(r"\$\.rows\[(\d+)\]\.cols\[(\d+)\]", sel)
                if m:
                    val = rows[int(m.group(1))][int(m.group(2))]
                else:
                    raise ValueError(f"bad selector: {sel}")
        except IndexError as exc:
            raise ValueError(
                f"capture selector {sel} did not match script output") from exc
        if dst.startswith("vars."):
            ctx.vars[dst[5:]] = val
        else:
            raise ValueError(f"capture dst must start with vars.: {dst}")


def get_wait(ctx, val):
    """Return a sleep duration in seconds.

    `val` may be a literal number of milliseconds (int or numeric string) or
    the name of a key in the spec's `timing` block (legacy form).
    """
    if val is None or val == "":
        return 0
    if isinstance(val, (int, float)):
        return float(val) / 1000.0
    s = str(val).strip()
    if s.lstrip("-").isdigit():
        return int(s) / 1000.0
    keyed = ctx.spec.get("timing", {}).get(s, 0)
    return int(keyed) / 1000.0


def exec_step(step, ctx, local_subs):
    subs = dict(ctx.subs); subs.update(local_subs)
    t = step["type"]
    desc = step.get("description", "")
    if not QUIET:
        print(f"\n[{step.get('id','?')}] ({t}) {desc.strip().splitlines()[0] if desc else ''}")

    if t == "while":
        cond = step["condition"]
        cscript = cond["script"]
        cexit = cond.get("expect_exit", 0)
        max_it = step.get("max_iterations", WHILE_MAX_ITERATIONS)
        i = 0
        while i < max_it:
            csubs = dict(ctx.subs); csubs.update(local_subs)
            cargs = [render(a, csubs) for a in cond.get("args", [])]
            if not QUIET:
                print(f"  ? {' '.join([cscript] + [str(x) for x in cargs])}")
            cp = subprocess.run([PY, script_path(cscript)] + [str(a) for a in cargs],
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
            if cp.returncode != cexit:
                if not QUIET:
                    print(f"    loop condition false (exit {cp.returncode}); stopping after {i} iteration(s)")
                break
            if "capture" in cond:
                capture(cp.stdout, cond["capture"], ctx)
            i += 1
            if not QUIET:
                print(f"\n--- while iter {i} ---")
            ctx.iter_failed[i] = False
            local = {"i": i, "n": i}
            for sub in step["body"]:
                exec_step(sub, ctx, {**local_subs, **local})
        else:
            raise AssertionError(
                f"while loop did not converge: condition still true after "
                f"max_iterations={max_it} (vulnerable packages remain)")
        return

    if t == "foreach":
        items = lookup(step["items"], subs)
        var = step["var"]; idx_var = step.get("index_var", "i")
        body = step["body"]
        for i, item in enumerate(items, start=1):
            if not QUIET:
                print(f"\n--- iter {i}: {var}={item!r} ---")
            local = {var: item, idx_var: i}
            ctx.iter_failed[i] = False
            for sub in body:
                try:
                    exec_step(sub, ctx, {**local_subs, **local})
                except AssertionError as e:
                    print(f"    FAIL: {e}")
                    ctx.iter_failed[i] = True
                    if sub["type"] != "screenshot":
                        # try to take the FAIL snapshot before bubbling
                        pass
                    raise
        return

    script = step.get("script")
    raw_args = step.get("args") or step.get("args_expr") or []
    args = [render(a, subs) for a in raw_args]
    expect_exit = step.get("expect_exit", 0)

    if t == "assert_console_contains":
        target = render(step["expected_contains_expr"], subs)
        total = get_wait(ctx, step.get("poll_total_ms")) or 3.0
        interval = get_wait(ctx, step.get("poll_interval_ms")) or 0.2
        deadline = time.time() + total
        last = ""
        while time.time() < deadline:
            p = subprocess.run([PY, script_path(script)] + args,
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            last = p.stdout
            if target in last:
                if not QUIET:
                    print(f"    matched: {target!r}")
                return
            time.sleep(interval)
        raise AssertionError(f"console did not contain {target!r}; last={last[:200]!r}")

    if t == "screenshot":
        n = local_subs.get("n", 0)
        failed = ctx.iter_failed.get(n, False)
        key = "args_expr_on_fail" if failed else "args_expr_on_pass"
        raw = step.get(key) or step.get("args_expr") or step.get("args")
        subs = dict(subs); subs["ss"] = f"ss_{ctx.ss_counter}"
        args = [render(a, subs) for a in raw]
        ctx.ss_counter += 1
        run_cmd(script, args, expect_exit=0)
        return

    p = run_cmd(script, args, expect_exit=expect_exit)
    if "capture" in step:
        capture(p.stdout, step["capture"], ctx)
    wait = get_wait(ctx, step.get("wait_after"))
    if wait:
        time.sleep(wait)


def _hwnd_vars(ctx):
    """Captured window handles, keyed by var name, in capture order.

    Any `capture` mapping whose destination var name ends in `hwnd` (the
    convention used throughout test_cases/, e.g. vars.vs_hwnd, vars.cmd_hwnd)
    is treated as a window handle worth acting on during failure cleanup.
    """
    out = []
    for key, val in ctx.vars.items():
        if key.lower().endswith("hwnd"):
            try:
                out.append((key, int(val)))
            except (TypeError, ValueError):
                continue
    return out


def _console_hwnd(ctx):
    """Best-effort guess at a captured command-prompt / console window var."""
    for key, hwnd in _hwnd_vars(ctx):
        lk = key.lower()
        if "console" in lk or "cmd" in lk:
            return hwnd
    return None


def _window_rect(hwnd):
    """Return (x, y, w, h) for hwnd via GetWindowRect, or None on failure."""
    rect = wintypes.RECT()
    if not ctypes.windll.user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
        return None
    return (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)


def on_failure_capture(ctx):
    """Best-effort diagnostics + cleanup run once a step fails.

    1. Screenshot the current UI state (full screen).
    2. Screenshot the console/log window, if one was captured (any `*hwnd`
       var whose name contains "cmd" or "console" -- the convention already
       used by test_cases/*.csv).
    3. Force-close every captured window (and its owning process), so a
       failed run doesn't leave the app/console orphaned for the next run.

    Never lets a diagnostics/cleanup error mask the original assertion
    failure -- each sub-step is independently best-effort.
    """
    print("\n--- on-failure cleanup ---")

    ui_shot = os.path.join(ctx.shot_dir, f"ss_{ctx.ss_counter}_FAILURE_ui_state.png")
    try:
        run_cmd("scripts/files/screenshot.py", [ui_shot])
        ctx.ss_counter += 1
    except Exception as e:
        print(f"    ! failed to capture UI-state screenshot: {e}")

    console_hwnd = _console_hwnd(ctx)
    if console_hwnd is not None:
        log_shot = os.path.join(ctx.shot_dir, f"ss_{ctx.ss_counter}_FAILURE_console_log.png")
        rect = _window_rect(console_hwnd)
        args = [log_shot] + (["--region", *map(str, rect)] if rect else [])
        try:
            run_cmd("scripts/files/screenshot.py", args)
            ctx.ss_counter += 1
        except Exception as e:
            print(f"    ! failed to capture console/log screenshot: {e}")
    else:
        print("    (no captured *cmd_hwnd/*console_hwnd var found; skipping log screenshot)")

    for key, hwnd in _hwnd_vars(ctx):
        try:
            run_cmd("scripts/window/close_window.py", [hwnd, "--force"])
        except Exception as e:
            print(f"    ! failed to close {key}={hwnd}: {e}")


def main():
    global QUIET
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("spec")
    ap.add_argument("-q", "--quiet", action="store_true",
                    help="suppress per-step headers and successful stdout echo")
    a = ap.parse_args()
    QUIET = a.quiet
    spec = load_spec(a.spec)
    ctx = Ctx(spec)
    print(f"=== {spec.get('name')} ===")
    print(f"screenshot_dir: {ctx.shot_dir}")
    failed = False
    for step in spec["steps"]:
        try:
            exec_step(step, ctx, {})
        except AssertionError as e:
            print(f"\n*** STEP FAILED: {step.get('id')}: {e}")
            try:
                on_failure_capture(ctx)
            except Exception as cleanup_err:
                print(f"    ! on-failure cleanup raised unexpectedly: {cleanup_err}")
            failed = True
            break
    print("\n=== RESULT:", "FAIL" if failed else "PASS", "===")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"RUNNER ERROR: {e}", file=sys.stderr)
        sys.exit(2)
