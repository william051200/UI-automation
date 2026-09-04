# Scripts reference

Every primitive helper invoked by `run_test.py` lives under `scripts/`, grouped into category subfolders. Each is a single-purpose CLI mapped to a step `type`, and can be run directly for debugging. This is the source of truth for what each script does.

Categories:

- [`scripts/web/`](#web--browser--cdp) — browser automation over the Chrome DevTools Protocol
- [`scripts/input/`](#input--mousekeyboard) — synthetic mouse / keyboard input (screen coordinates)
- [`scripts/window/`](#window--window-management) — find, focus, maximize, launch, close windows
- [`scripts/uia/`](#uia--ui-automation-inspection) — read / inspect UI Automation trees and text
- [`scripts/files/`](#files--files--clipboard) — screenshots, file writes/asserts, clipboard, home dir
- [`scripts/csvfmt/`](#csvfmt--csv-spec-loader) — in-memory CSV-spec loader/schema (internal, not step types)

---

## `web/` — browser / CDP

These drive a Chrome/Edge launched with only `--remote-debugging-port` (so `navigator.webdriver` stays `false`), attaching over raw CDP. Each helper reconnects to the long-running browser. All take `--port` (default `9222`) and optional `--url-contains` to pick a page target.

### `cdp_client.py` — shared CDP module (not a step)
Connection plumbing imported by the helpers: `list_targets()`, `select_page_target()`, `wait_ready()`, and a `CDPSession` wrapper. Unit-tested in `tests/test_cdp_client.py`.

### `browser_launch.py` — start Chrome/Edge with a debug port
Launches the browser (`--browser chrome|edge`) with `--remote-debugging-port` and a fixed gitignored `--user-data-dir`, polling until CDP answers. `--fresh` wipes the profile first; `--clone` seeds it from your real profile (logins/cookies carry over without touching the live profile; `--clone-from PATH` picks a source). Prints the **pid on its own first line** (`$.cols[0]`).

```
browser_launch.py [url] [--browser chrome|edge] [--fresh] [--clone] [--clone-from DIR]
                  [--port 9222] [--user-data-dir DIR] [--chrome PATH]
```

### `browser_goto.py` — navigate to a URL
`Page.navigate`, then waits for `readyState === 'complete'`. Prints final `url` and `title`.

```
browser_goto.py <url> [--port 9222] [--load-timeout-ms 15000]
```

### `dom_get_html.py` — read page/element HTML
Writes `outerHTML` (or `--text` `innerText`) of the document or `--selector` to `--out`, printing `bytes`/`path`. Exit 1 if the selector matches nothing.

```
dom_get_html.py --out PATH [--selector CSS] [--text] [--port 9222]
```

### `dom_interact.py` — click / type / press on an element
Performs `action` on a CSS `--selector` via trusted CDP `Input.dispatch*` events. Exit 1 if not found/interactable.

```
dom_interact.py <click|type|set|press|select> [--selector CSS] [--value V] [--port 9222]
```

### `dom_query.py` — validate where to interact
Reports `count`/`visible`/`text`/bounding-box for a `--selector`. Assertion flags `--expect-min`, `--visible`, `--contains` exit 1 on failure. `--attr NAME` prints an attribute (or `innerText`) of the first match as the **first** output line (`$.cols[0]`).

```
dom_query.py --selector CSS [--expect-min N] [--visible] [--contains TEXT] [--attr NAME] [--port 9222]
```

### `dom_eval.py` — evaluate a JS expression on the page
Evaluates `--expr` and prints the result as the **first** line (`$.cols[0]`), then a `type=` line. Objects print as compact JSON; `null`/`undefined` exits 1. Use when the value isn't addressable as an element.

```
dom_eval.py --expr JS [--url-contains S] [--port 9222]
```

---

## `input/` — mouse/keyboard

Synthetic input at **screen coordinates** to the focused window. (For in-page web interactions use `web/dom_interact.py`.)

### `click.py` — mouse click
Moves to `(x, y)` and clicks (single left by default).

```
click.py <x> <y> [--right] [--double]
```

### `type_text.py` — type a literal string
Types a UTF-8 string into the focused window. `--interval` is per-char delay (default 0.02 s; use `0.06` if capitals/Shift drop on slow machines).

```
type_text.py <text> [--interval 0.02]
```

### `key.py` — press a key or hotkey
Presses a named key (`enter`, `win`, `tab`, …) or `+`-separated combo (`ctrl+s`, `alt+f4`).

```
key.py <combo>
```

### `drag.py` — press, drag, release
Explicit mouseDown → moveTo → mouseUp from `(x1,y1)` to `(x2,y2)` (pyautogui `dragTo()` is unreliable on Win11).

```
drag.py <x1> <y1> <x2> <y2> [--button left|right]
```

### `scroll.py` — scroll the mouse wheel
Scrolls at `(x, y)`; positive delta = up/right, negative = down/left.

```
scroll.py <x> <y> <delta>
```

---

## `window/` — window management

### `find_window.py` — locate a top-level window
Returns desktop windows whose title matches a regex (filterable by `--class`/`--pid`), via `uia`/`win32`/`any`. Sorted by `(pid, hwnd)` for reproducible candidate lists. Prints tab-separated `pid hwnd left top right bottom title`. Exits **1** if nothing matches (used to assert a window is *gone*).

```
find_window.py <title_regex> [--class CLASS] [--pid PID] [--backend uia|win32|any]
                              [--all | --nth N]
```

### `activate_window.py` — raise + focus a window
Restores if minimised, then `set_focus()`. Prints `activated hwnd=<n> title=<...>`. Exit 1 if the hwnd is gone or Windows refuses to foreground it.

```
activate_window.py <hwnd> [--backend uia|win32] [--settle-ms 100]
```

### `maximize_window.py` — maximize a window
Maximizes by `hwnd` (restores first if minimised). If already maximized, leaves it and prints `already maximized hwnd=<n>` (still exit 0). Exit 1 if the hwnd is gone.

```
maximize_window.py <hwnd> [--backend uia|win32] [--settle-ms 100]
```

### `close_window.py` — close a window (optional force)
Sends WM_CLOSE. If still alive after `--grace-ms`, exits 2 unless `--force` (then terminates the process). Exit: 0 closed, 1 no such hwnd, 2 still alive, 3 bad usage.

```
close_window.py <hwnd> [--grace-ms 2000] [--force]
```

### `launch.py` — launch an executable, optionally wait for its window
Prints `pid`. With `--wait-window`, prints `pid hwnd left top right bottom title` once a matching window appears. Exit: 0 OK, 1 launch failed, 2 wait timed out, 3 bad usage.

```
launch.py <exe> [--args ...] [--wait-window REGEX] [--wait-timeout-ms 10000]
```

### `wait_for.py` — poll find_window / find_control until success
Retries the wrapped helper until success or `--timeout-ms`. On success, stdout is the helper's output (so `capture:` works). Exit 1 on timeout.

```
wait_for.py --mode window|control [--timeout-ms 5000] [--poll-ms 250] -- <helper args>
```

### `click_in_dialog.py` — click a button in an optional dialog
Finds a dialog by `title_regex` and clicks `--button` if present. Tolerant: a missing dialog/button is a no-op (exit 0) unless `--required` (then exit 1). Collapses a brittle find_window + find_control + click into one fast step for dialogs that appear only sometimes (e.g. NuGet 'License Acceptance'). Exit 2 on error.

```
click_in_dialog.py <title_regex> --button NAME [--auto-id A] [--match exact|contains|regex]
                   [--find-backend uia|win32] [--timeout 4.0] [--required]
```

### `find_devenv.py` — locate the Visual Studio `devenv.exe`
Finds the installed VS executable, edition/version/channel agnostic: tries `vswhere` (`-latest`, then `-prerelease`), the `VS7` registry keys, and a Program Files scan. `--path` (or `$VSDEVENV`) forces a path; `--prerelease` prefers Insiders/Preview. Prints the full `devenv.exe` path as the **first** line (`$.cols[0]`). Exit 2 if no VS install is found.

```
find_devenv.py [--path EXE] [--prerelease]
```

---

## `uia/` — UI Automation inspection

### `find_control.py` — locate a UIA control inside a window
Walks the UIA tree of a window (`hwnd`), matching by `name`/`auto_id`/`control_type`/`class` with `exact`/`contains`/`regex`. Prints a header plus rectangle and center coords for `input/click.py`. `--name-fallback` retries without `--auto-id` if it yields zero matches (resilient to AutomationId churn).

```
find_control.py <hwnd> [--name N] [--auto-id A] [--control-type T] [--class C]
                       [--match exact|contains|regex] [--backend uia|win32]
                       [--parent-hwnd HWND] [--all | --nth N] [--name-fallback]
```

### `toggle_check.py` — set a CheckBox state
Sets a UIA CheckBox to a desired state via the Toggle pattern (not a coordinate click), so it reliably ticks boxes whose square is at a wide row's edge (e.g. VS Reference Manager). Same selector model as `find_control.py`. Prints the final state; exit 1 if not found, 2 on error.

```
toggle_check.py <hwnd> [--name N] [--auto-id A] [--control-type CheckBox] [--class C]
                [--match exact|contains|regex] [--state check|uncheck|toggle]
```

### `select_combo.py` — select a ComboBox item
Selects an item by text via the SelectionItem/ExpandCollapse patterns (not a mouse click), so it works for editable WPF combos (e.g. NuGet Version) whose centre is a text box. Prints the selected item; exit 1 if no item matches.

```
select_combo.py <hwnd> [--auto-id A] [--name N] --item TEXT [--match exact|contains|regex]
```

### `submenu_verify_checked.py` — read/verify the checked item in a cascading toolbar menu
Expands a split-button or menu control (`--root-name`/`--root-type`, e.g. the VS "Debug Target" toolbar button showing "Windows Machine"), then expands a named submenu inside it (`--submenu`, e.g. "Framework") and reads which leaf `MenuItem` is checked. WPF menu items expose exclusive checked state via the legacy MSAA `STATE_SYSTEM_CHECKED` bit rather than the UIA SelectionItem pattern, and leaf items only materialize in the UIA tree while the submenu is open, so this cannot be done with `find_control.py` alone. `list` prints every leaf with its checked flag (`name\t0|1`); `verify-checked --expect TEXT` exits 1 if the checked leaf's name does not equal `TEXT`. The menu is closed (Escape) afterward unless `--keep-open` is given.

```
submenu_verify_checked.py <hwnd> --root-name N [--root-type SplitButton] --submenu N
                          [--match exact|contains|regex] [--timeout-ms N] [--keep-open]
                          (list | verify-checked --expect TEXT)
```

### `read_console.py` — dump a window's UIA text
Prints a window's text, preferring the `Document` control (the console buffer), falling back to legacy properties then all visible text nodes. Validates console output without OCR.

```
read_console.py <hwnd>
```

### `read_text.py` — read a specific element's text
Inverse of `type_text.py`. Locates a descendant via `<parent_hwnd>` plus `--name`/`--auto-id`/`--control-type` (or reads the parent itself) and prints the value verbatim. Works for UWP/WinUI/Win11 Notepad children with no Win32 hwnd.

```
read_text.py <hwnd> [--name N] [--auto-id A] [--control-type T]
```

> **`read_console.py` vs `read_text.py`:** the former targets the whole-window console buffer (`Document`); the latter reads a specific selector-addressed descendant.

### `uia_tree.py` — dump a depth-bounded UIA subtree as JSON
Walks the UIA tree breadth-first to `--max-depth`, printing a JSON array of nodes (name/auto_id/control_type/class/rect/depth/children). For discovering selectors during authoring.

```
uia_tree.py <hwnd> [--max-depth N] [--name N] [--auto-id A] [--control-type T]
```

### `ui_fingerprint.py` — short hash of the foreground UI
Prints a 16-char SHA-256 prefix from the foreground window's title/class/process, optional rect, and up to 50 direct children. Useful for detecting a stuck UI (an unchanged hash across acting steps).

```
ui_fingerprint.py [--verbose] [--no-include-rect]
```

---

## `files/` — files & clipboard

### `screenshot.py` — capture PNG
Saves a PNG of the full screen or a region, creating the output dir.

```
screenshot.py <out_path> [--region X Y W H]
```

### `write_text.py` — create / write a text file
Writes `--text` (`\n` = newline) to `--out`, creating parent dirs, and prints the **absolute path** first (`$.cols[0]`) then `bytes=<n>`. `--append` appends. Handy for pre-creating a path-bound file a GUI editor can save with Ctrl+S.

```
write_text.py --out PATH [--text STR] [--append]
```

### `assert_file_exists.py` — file existence / content assertions
Asserts a file exists (or, with `--negate`, does not), optionally checking `--contains` and `--delete`-ing after. Backs the `assert_file` step.

```
assert_file_exists.py <path> [--contains TEXT] [--negate] [--delete]
```

### `clipboard.py` — read or write the clipboard (text only)
`read` prints clipboard text; `write <text>` replaces it; `write-stdin` reads stdin verbatim (multi-line safe).

```
clipboard.py <read|write|write-stdin> [text]
```

### `print_home.py` — print the user's home directory
Resolves `~` to the real profile path on this machine (any drive) and prints it as the **first** line (`$.cols[0]`). Capture as `{vars.home}` to build absolute, machine-portable paths.

```
print_home.py
```

---

## `csvfmt/` — CSV spec loader

Internal modules (not step types) that let `run_test.py` run a `.csv` spec straight from disk. See [`csv-test-format.md`](csv-test-format.md).

### `csv_loader.py` — load a CSV test case into a spec dict
`run_test.py` calls `load()` directly for `.csv` specs; the returned dict is the runnable spec structure the runner consumes. Run as a CLI to print the parsed spec as JSON for debugging.

```
csv_loader.py <csv>
```

### `csv_schema.py` — shared CSV schema (not a step)
Defines the combined-CSV layout: marker-delimited `# CONFIG` and `# STEPS` sections, column names, and loop markers. Imported by the loader.
