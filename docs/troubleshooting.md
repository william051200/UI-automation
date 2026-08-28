# Troubleshooting & known gotchas

> Audience: human operators running scenarios on a real machine. These are runtime/environment issues (display, monitors, focus, execution policy), not authoring rules — for agent-authoring conventions see [`AGENTS.md`](../AGENTS.md).

## Display scaling
`run_test.py` sets per-monitor v2 DPI awareness so clicks land correctly at 125/150/200%. If you see clicks offset, verify Python isn't being launched through a DPI-virtualization shim.

## Multi-monitor
`pyautogui.size()` reports the primary monitor only. The target UI must open on the primary monitor for coordinate clicks to work. The Start menu always opens on the primary monitor, so the bundled scenario is fine.

## UI language
`find_control --name Close` matches the *display name*. On non-English Windows, use `--auto-id Close` (the AutomationId is locale-invariant for system controls) or use Inspect.exe to find the right selector.

## Focus stealers
A popup that grabs focus mid-run will break typing-based steps. Re-run, or add an extra `focus_window` click before each `type_text`.

## Execution policy
If `irm | iex` is blocked, run:
```powershell
powershell -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/william051200/UI-automation/main/install.ps1 | iex"
```

## Legacy pip workflow
If you prefer not to use `uv`, the toolkit still works with vanilla pip:
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe run_test.py test_cases\<test-case>.csv
```
