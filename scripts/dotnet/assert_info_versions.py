"""Assert that `dotnet --info` version numbers are clean major.minor.patch.

Runs ``dotnet --info`` as a subprocess and parses the ``.NET SDKs installed:``
and ``.NET runtimes installed:`` sections. Every listed version must match
``^\\d+\\.\\d+\\.\\d+$`` (e.g. ``9.0.100``). Fails if any version carries a
build suffix such as ``-servicing-xxxxx.xx`` or ``-preview.x``.

The raw ``dotnet --info`` output is also captured to disk so the test case has
an artifact of what was verified:

  --save-text PATH   write the raw stdout to PATH (parent dirs created).
  --save-image PATH  render the raw stdout as a PNG at PATH (a real
                     "screenshot" of the command output; needs Pillow).

Exit codes:
  0 - both sections found and every version is clean.
  1 - a section is missing, empty, or any version is malformed.
  2 - dotnet is not on PATH or returned a non-zero exit.
"""
import argparse
import os
import re
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
SECTIONS = [".NET SDKs installed:", ".NET runtimes installed:"]


def run_dotnet_info():
    try:
        p = subprocess.run(["dotnet", "--info"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    except FileNotFoundError:
        print("ERROR: `dotnet` not found on PATH", file=sys.stderr)
        sys.exit(2)
    if p.returncode != 0:
        print(f"ERROR: `dotnet --info` exit={p.returncode}: {p.stderr}", file=sys.stderr)
        sys.exit(2)
    return p.stdout or ""


def save_text(text, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"saved text: {path}")


def save_image(text, path):
    from PIL import Image, ImageDraw, ImageFont
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    try:
        font = ImageFont.truetype("consola.ttf", 14)
    except Exception:
        font = ImageFont.load_default()
    lines = text.splitlines() or [""]
    line_h = 18
    pad = 12
    # Measure widest line for canvas width.
    tmp = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(tmp)
    widths = []
    for ln in lines:
        try:
            bbox = draw.textbbox((0, 0), ln, font=font)
            widths.append(bbox[2] - bbox[0])
        except Exception:
            widths.append(len(ln) * 8)
    width = max(widths + [400]) + pad * 2
    height = pad * 2 + line_h * len(lines)
    img = Image.new("RGB", (width, height), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)
    y = pad
    for ln in lines:
        draw.text((pad, y), ln, fill=(230, 230, 230), font=font)
        y += line_h
    img.save(path)
    print(f"saved image: {path}")


def parse_section(text, header):
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if header in line:
            body = []
            for ln in lines[i + 1:]:
                s = ln.strip()
                if not s:
                    if body:
                        break
                    continue
                if s.endswith(":") and not s[0].isdigit():
                    break
                body.append(s)
            return body
    return None


def extract_version(entry):
    for tok in entry.split():
        if re.match(r"^\d+\.\d+", tok):
            return tok.rstrip(",")
    return None


def check_section(text, header):
    entries = parse_section(text, header)
    if entries is None:
        print(f"ERROR: section not found: {header!r}", file=sys.stderr)
        return False
    if not entries:
        print(f"ERROR: no entries under {header!r}", file=sys.stderr)
        return False
    bad = []
    all_versions = []
    for e in entries:
        v = extract_version(e)
        if v is None:
            bad.append((e, "no version token"))
            continue
        all_versions.append(v)
        if not VERSION_RE.match(v):
            bad.append((e, f"version {v!r} not major.minor.patch"))
    print(f"{header} {len(entries)} entries; versions: {', '.join(all_versions)}")
    if bad:
        for e, why in bad:
            print(f"  BAD: {e!r} -- {why}", file=sys.stderr)
        return False
    return True


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--save-text", default=None,
                   help="write raw `dotnet --info` stdout to this path")
    p.add_argument("--save-image", default=None,
                   help="render raw `dotnet --info` stdout as a PNG at this path")
    a = p.parse_args()

    text = run_dotnet_info()

    if a.save_text:
        save_text(text, a.save_text)
    if a.save_image:
        save_image(text, a.save_image)

    ok = True
    for h in SECTIONS:
        if not check_section(text, h):
            ok = False
    if not ok:
        sys.exit(1)
    print("OK: SDK and runtime versions are clean major.minor.patch.")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)


