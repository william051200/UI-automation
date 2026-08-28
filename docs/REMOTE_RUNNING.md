# Remote UI Test Execution — DevBox Runner Guide

Run the CSV-driven UI tests on a Microsoft DevBox by clicking a button in
your laptop browser. No RDP needed during the run itself.

> **Deployment model.** Each tester works on **their own fork** of
> `william051200/UI-automation`. Runners are registered against your fork
> (you're auto-admin of your fork, no permission wait), and you dispatch
> workflows from your fork's Actions tab. Shared improvements go back to
> upstream via PR.

> **Legend:** **🖥️ DEVBOX** = the RDP'd Windows machine · **💻 LAPTOP** = your local browser

---

## Architecture at a glance

```
                     💻 LAPTOP browser              GitHub                    🖥️ DEVBOX
                    ┌────────────────┐         ┌─────────────┐          ┌────────────────────┐
                    │ Click          │         │ Your fork's │          │ Self-hosted runner │
                    │ "Run workflow" │ ──────► │ Actions tab │ ──job──► │  → uv sync         │
                    └────────────────┘         └─────────────┘          │  → run.ps1 <csv>   │
                                                     ▲                  │  → screenshots     │
                                                     │ artifacts        └────────────────────┘
       artifact download ────────────────────────────┘
```

**Fork-based model.** Every tester works on **their own fork** of
`william051200/UI-automation`:

- You register your DevBox as a runner on **your fork** — you're auto-admin
  of your fork, no permission wait.
- You dispatch runs from **your fork's Actions tab**.
- Improvements to shared code (workflow, docs, scripts, new test cases) are
  contributed back to upstream via pull request.

**How it stays scalable:** each DevBox registers as a distinct runner with
a unique label (e.g. `12082026-desk-1`). The workflow's `target_devbox` input
picks which label to run on. Adding a DevBox = one command on that DevBox;
the setup script also adds the label to your fork's workflow dropdown.

---

## Part A — First-time fork setup (💻 laptop)

Do this once per tester.

### Step 1 — Fork `william051200/UI-automation`

Open <https://github.com/william051200/UI-automation> and click **Fork** →
your account. You'll end up at `https://github.com/<your-handle>/UI-automation`.

### Step 2 — Enable Actions on your fork

Forks have Actions disabled by default:

> Your fork → **Settings** → **Actions** → **General** →
> "Allow all actions and reusable workflows" → **Save**.

---

## Part B — Register your DevBox as a runner (one-time, 🖥️ DevBox)

Run these once on each DevBox you own. After this, day-to-day usage is
entirely browser-driven from your laptop.

### Step 1 — 🖥️ DEVBOX: RDP in and open an admin PowerShell

`Win + X` → **Windows PowerShell (Admin)** → `Yes` to the UAC prompt.

> ⚠️ Do NOT `cd C:\Windows\System32`. Work from `$HOME`.
> ```powershell
> cd $HOME
> ```

### Step 2 — 🖥️ DEVBOX: Run the one-line setup

Paste this **single line** (replace `<your-handle>` with your GitHub handle):

```powershell
irm https://raw.githubusercontent.com/<your-handle>/UI-automation/main/scripts/setup-remote-runner.ps1 | iex
```

The script will:

1. Detect (or ask for) your GitHub handle and clone
   `https://github.com/<your-handle>/UI-automation.git` into `$HOME\UI-automation`.
2. Install `uv` and run `uv sync` (Python + deps).
3. Compose your DevBox label as `<DDMMYYYY>[-<suffix>]-<N>`:
   - today's date is auto-prepended,
   - it asks for an optional suffix (e.g. `desk`, `laptop`) — leave blank to skip,
   - `<N>` auto-increments by scanning existing labels on your fork's workflow.
4. Prompt you for a **runner registration token**. Get it from
   (open in your **laptop** browser):

   ```
   https://github.com/<your-handle>/UI-automation/settings/actions/runners/new?arch=x64&os=win
   ```

   Copy the token that appears next to `./config.cmd --token ...` and
   paste it into the PowerShell prompt. Tokens expire in ~1 hour — grab
   it right before pasting.
5. Register the runner, install a Scheduled Task so it auto-starts on
   logon, add your label to `.github/workflows/run-ui-tests.yml`, and
   push the change to your fork's `main` (no PR — it's your own fork).

When it finishes, verify at
`https://github.com/<your-handle>/UI-automation/settings/actions/runners`
that your runner shows status **Idle**.

### Step 3 — 🖥️ DEVBOX: Log in and leave unlocked

UI automation needs an interactive, unlocked desktop.

- **Do NOT** log the DevBox off — you can disconnect RDP, but leave it logged in.
- **Do NOT** lock the screen — Windows will suspend UI input.
- Ideally: RDP once, leave the session open, close the RDP client. The DevBox
  stays running with the desktop live.

> Screens are kept open at all times, so this should be a non-issue. No
> keep-alive script is needed.

**One-time setup is done.** From here on, you never need to RDP just to run
a test.

---

## Part C — Running tests (day-to-day, browser-only)

You trigger runs from **your fork's** Actions tab. Only your fork's registered
runners will pick up the job.

### Step 1 — 💻 LAPTOP: Open the workflow page on YOUR fork

```
https://github.com/<your-handle>/UI-automation/actions/workflows/run-ui-tests.yml
```

Click **Run workflow** (top-right).

### Step 2 — 💻 LAPTOP: Fill in the inputs

| Input | Meaning | Example |
|---|---|---|
| `csv_spec` | Pick one CSV, or `ALL` to run every case sequentially | `test_cases/prod-1-cs_console_app.csv` |
| `target_devbox` | Which DevBox label to run on | `12082026-1` |

Click **Run workflow**.

### Step 3 — 💻 LAPTOP: Watch and collect

- **Live logs** — click the running job to stream stdout.
- **Screenshots** — after the run, scroll to the bottom of the summary page;
  the `screenshots-<label>-<n>` artifact contains every screenshot the CSV
  captured.
- **Exit codes** — `0` = pass, `1` = assertion fail, `2` = runner error.

### Step 4 — 🖥️ DEVBOX: Restart the listener if it dies

Sometimes the `run.cmd` PowerShell window closes (accidental close, reboot,
error), and jobs then queue forever. Check status here:

```
https://github.com/<your-handle>/UI-automation/settings/actions/runners
```

If your runner shows **Offline** (grey dot), restart it — pick either:

**A) One-liner via the Scheduled Task** (the one `setup-remote-runner.ps1`
registered):

Replace `<Label>` with your DevBox label (e.g. `12082026-1`).
**B) Manual restart** in the same admin PowerShell:

```powershell
cd C:\actions-runner
.\run.cmd
```

Leave the window open — closing it stops the runner again. Wait until you
see `Listening for Jobs`, then re-check the Runners page — status should
flip back to **Idle**.

> After a DevBox reboot the Scheduled Task starts the listener
> automatically on logon, so this recovery is only needed if you closed
> the window without a reboot.

---

## Part D — Staying in sync with upstream

Whenever upstream (`william051200/UI-automation`) adds new test cases or
fixes, pull them into your fork:

```powershell
cd $HOME\UI-automation
git remote add upstream https://github.com/william051200/UI-automation.git   # first time only
git fetch upstream
git checkout main
git merge upstream/main   # or: git rebase upstream/main
git push origin main
```

Then re-run `uv sync` if `pyproject.toml` / `uv.lock` changed. Point it
at the CI-shared venv so the next workflow run stays a no-op:

```powershell
$env:UV_PROJECT_ENVIRONMENT = 'C:\uv-venvs\ui-automation'
uv sync
```

---

## What happens automatically on every run

Each workflow run performs these steps on the DevBox:

1. **`uv sync --frozen`** — reproducible dep install from `uv.lock`.
2. **`run.ps1 <spec> [-q]`** — for each spec, sequentially.
3. **Screenshot upload** — always, even on failure.

> **DevBox hygiene:** testers refresh their DevBox between runs, so the
> workflow does **not** perform pre/post cleanup today. A cleanup script
> (`scripts/finalize-run.ps1`) is checked in and the workflow has commented
> pre/post steps ready to enable if we ever move to shared or long-lived
> DevBoxes.

---

## Adding another DevBox for yourself

Same one-liner as Part B — `setup-remote-runner.ps1` auto-composes a fresh
label. `<N>` auto-increments by scanning the existing labels on your
fork's workflow, so a second DevBox provisioned on the same day + same
suffix becomes `<DDMMYYYY>[-<suffix>]-2`. Each label is unique per DevBox;
**never** reuse a label across two machines — GitHub will re-register and
the previous DevBox will silently stop receiving jobs.

---

## Common issues

| Symptom | Cause / Fix |
|---|---|
| Workflow queued forever | No runner is online on **your fork** with the chosen label. Check `Settings → Actions → Runners` on your fork — if your runner shows **Offline**, restart the listener (see Part C, Step 4). |
| Dispatched from wrong repo | You must dispatch from `https://github.com/<your-handle>/UI-automation/actions`, not upstream. Upstream has no runners of yours. |
| `Not Found` on the runner-registration URL | You're looking at upstream. The URL must contain your fork's handle. |
| `The system cannot find the file specified` at UIA step | The DevBox is locked or logged off. Unlock and re-run. |
| Screenshots artifact missing | The CSV didn't write any screenshots (some don't) — not an error. |
| `uv sync` fails with `python not found` | First run on a fresh DevBox — `uv` will fetch Python. Re-trigger the workflow. |
| Runner appears twice in Settings → Runners | You re-registered without unregistering. Run `scripts\remove-runner.ps1 -Label <old-label>` on the DevBox to decommission the stale entry, then re-run `setup-remote-runner.ps1`. |
| Two workflows fought over the same DevBox | The workflow uses a `concurrency` group per label, so this shouldn't happen. If you see interleaved logs, file a bug. |

---

## Uninstalling a runner from a DevBox

RDP into the DevBox, open an admin PowerShell. First grab a removal
token (either via CLI or browser):

```powershell
# Option A -- CLI (fastest; needs `gh auth login` once):
gh api -X POST repos/<your-handle>/UI-automation/actions/runners/remove-token

# Option B -- browser:
# Fork -> Settings -> Actions -> Runners -> click your runner ->
# Remove -> copy the token from the shown './config.cmd remove --token ...' line.
```

Then run:

```powershell
cd $HOME\UI-automation
.\scripts\remove-runner.ps1 -Label <YourLabel> -Token <RemoveToken>
```

This will:

1. Stop and unregister the `GHRunner-<Label>` Scheduled Task.
2. Kill the live listener process.
3. Run `config.cmd remove --token <Token>` to deregister on GitHub.
4. Strip the label from `target_devbox.options` in your fork's workflow
   and push the change to `origin/main`.

If the runner is already gone from Settings -> Runners (or the token
endpoint 404s), use `-LocalOnly` to skip the GitHub-side deregistration:

```powershell
.\scripts\remove-runner.ps1 -Label <YourLabel> -LocalOnly
```

---

## Actions storage hygiene

The free GitHub plan includes only **0.5 GB of Actions storage per
month** (artifacts + logs, account-wide across all your repos). Because
every workflow run here can upload a `screenshots-<label>-<runid>`
artifact, a busy fork can hit the cap in a couple of weeks and GitHub
will email you a "100% of Actions storage" warning.

### One-time setup (recommended)

1. **Set a $0 Actions spending limit** so you can never be billed by
   accident: <https://github.com/settings/billing/spending_limit> →
   Actions → set to `$0`. Runs beyond the free tier will just be
   blocked until the next cycle instead of billed.
2. **Shorten artifact retention on your fork**:
   `https://github.com/<your-handle>/UI-automation/settings/actions` →
   *Artifact and log retention* → change from 90 days to something like
   **7 days**. New artifacts inherit this; existing ones keep their
   original expiry.

### If you get the "100% storage used" email

List and delete existing artifacts across your account:

```bash
# List repos with active artifacts and their size in MB
gh repo list <your-handle> --limit 100 --json nameWithOwner -q '.[].nameWithOwner' | \
  while read r; do
    size=$(gh api "repos/$r/actions/artifacts" --paginate \
      -q '.artifacts[] | select(.expired==false) | .size_in_bytes' \
      | awk '{s+=$1} END {printf "%.1f", s/1024/1024}')
    count=$(gh api "repos/$r/actions/artifacts" -q '.total_count')
    [ "${count:-0}" != "0" ] && echo "$r  artifacts=$count  activeMB=$size"
  done

# Delete every artifact on a repo (irreversible, but fine -- they expire anyway)
gh api repos/<your-handle>/<repo>/actions/artifacts --paginate \
  -q '.artifacts[].id' | \
  xargs -I{} gh api -X DELETE repos/<your-handle>/<repo>/actions/artifacts/{}
```

Billing counters update on a delay (usually within an hour). Once you
drop back under 0.5 GB the alert clears automatically.
