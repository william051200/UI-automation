"""Execute a declarative UI-automation test spec (CSV).

Usage:
    python run_test.py <spec.csv>   # standard-format CSV, loaded in memory

Exit codes:
    0  all steps passed
    1  one or more assertions failed
    2  runner error (bad spec, script missing, etc.)
"""
import argparse, datetime, os, re, subprocess, sys, time

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

        # Toast-notification failure recovery (see run_steps_retrying) is ON by
        # default for every spec -- it targets whichever `vars.*hwnd` was most
        # recently captured (see `capture()`), so no `# CONFIG` row is needed.
        # A spec can opt out with `# CONFIG` row `retry,toast_dismiss,off`, or
        # override the auto-detected window with `retry,toast_dismiss_var,<vars name>`.
        retry_cfg = spec.get("retry") or {}
        self.toast_dismiss_enabled = str(
            retry_cfg.get("toast_dismiss", "on")).strip().lower() not in (
            "off", "false", "0", "no")
        self.toast_dismiss_var = retry_cfg.get("toast_dismiss_var")
        self.last_hwnd = None
        self.last_failed_step = None


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


def run_cmd(script, args, expect_exit=0):
    cmd = [PY, os.path.join(ROOT, script)] + [str(a) for a in args]
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
        if m:
            val = first_cols[int(m.group(1))]
        else:
            m = re.fullmatch(r"\$\.rows\[(\d+)\]\.cols\[(\d+)\]", sel)
            if m:
                val = rows[int(m.group(1))][int(m.group(2))]
            else:
                raise ValueError(f"bad selector: {sel}")
        if dst.startswith("vars."):
            name = dst[5:]
            ctx.vars[name] = val
            # Track the most recently captured window handle (any var named/ending
            # in "hwnd") as the default toast-dismiss target -- see dismiss_toasts.
            if name == "hwnd" or name.endswith("_hwnd"):
                ctx.last_hwnd = val
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


def dismiss_toasts(ctx):
    """Best-effort: dismiss transient toast/notification popups that can overlap a
    dialog button and swallow a click, run when a step fails and toast recovery is
    enabled. Enabled by default for every spec; a spec can opt out with `# CONFIG`
    row `retry,toast_dismiss,off`.

    Targets whichever `vars.*hwnd` was most recently captured (see `capture()`),
    or the var named by `# CONFIG` row `retry,toast_dismiss_var,<vars name>` if
    a spec wants to pin a specific window instead of the auto-detected one.

    Returns False (nothing attempted) when the feature is disabled for this
    spec, or no window handle has been captured yet (e.g. the failure happened
    before the app launched) -- callers should treat that as "recovery not
    applicable" and let the original failure stand. Returns True once an
    attempt was made, regardless of whether a toast was actually present.
    """
    if not ctx.toast_dismiss_enabled:
        return False
    hwnd = ctx.vars.get(ctx.toast_dismiss_var) if ctx.toast_dismiss_var else None
    if not hwnd:
        hwnd = ctx.last_hwnd
    if not hwnd:
        return False
    script = os.path.join(ROOT, "scripts", "window", "dismiss_toasts.py")
    if not os.path.exists(script):
        return False
    p = subprocess.run([PY, script, str(hwnd)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if not QUIET:
        for line in (p.stdout or "").rstrip().splitlines():
            print(f"    [toast-recovery] {line}")
        for line in (p.stderr or "").rstrip().splitlines():
            print(f"    [toast-recovery] ! {line}")
    return True


def run_steps_retrying(steps_list, ctx, local_subs):
    """Run a flat list of steps in order; on a step failure, attempt toast-
    notification recovery and one retry pass before giving up.

    A toast can swallow the click meant for the *previous* step's button (the
    wizard never advances, so the failure only surfaces on this step), so
    recovery re-runs the previous step -- not just this one -- before retrying
    the step that actually failed. Runs at most one retry pass; a failure
    during retry propagates normally.
    """
    i = 0
    while i < len(steps_list):
        step = steps_list[i]
        try:
            exec_step(step, ctx, local_subs)
        except AssertionError as e:
            ctx.last_failed_step = step.get("id")
            if not dismiss_toasts(ctx):
                raise
            if not QUIET:
                print(f"    step {step.get('id')} failed ({e}); "
                      f"dismissed toast notification(s), retrying")
            if i > 0:
                prev = steps_list[i - 1]
                if not QUIET:
                    print(f"    re-running previous step {prev.get('id')} "
                          f"in case its click was swallowed by the toast")
                exec_step(prev, ctx, local_subs)
            exec_step(step, ctx, local_subs)
        i += 1


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
            cp = subprocess.run([PY, os.path.join(ROOT, cscript)] + [str(a) for a in cargs],
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
            run_steps_retrying(step["body"], ctx, {**local_subs, **local})
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
            try:
                run_steps_retrying(body, ctx, {**local_subs, **local})
            except AssertionError as e:
                print(f"    FAIL: {e}")
                ctx.iter_failed[i] = True
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
            p = subprocess.run([PY, os.path.join(ROOT, script)] + args,
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
    try:
        run_steps_retrying(spec["steps"], ctx, {})
    except AssertionError as e:
        print(f"\n*** STEP FAILED: {ctx.last_failed_step}: {e}")
        failed = True
    print("\n=== RESULT:", "FAIL" if failed else "PASS", "===")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"RUNNER ERROR: {e}", file=sys.stderr)
        sys.exit(2)
