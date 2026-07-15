#!/usr/bin/env python3
"""Check the ZCode CDN for a new release and bump the flatpak manifest + appdata.

Triggered by .github/workflows/auto-update.yml. Exits 0 and prints
"changed=true|false" (as "changed=<bool>" for GHA output parsing) on the last
line; prints "version=<v>" when changed.

Strategy:
  * Scrape https://zcode.z.ai for every "/releases/<x.y.z>/" path embedded in
    the page and take the highest semver.
  * Compare against the version currently pinned in ai.zcode.ZCode.yaml.
  * If newer: download the x86_64 .deb, compute sha256, rewrite the manifest's
    url + sha256, and refresh the appdata <releases> section from upstream's
    per-version latest.yml.
"""
from __future__ import annotations

import hashlib
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
MANIFEST = ROOT / "ai.zcode.ZCode.yaml"
APPDATA = ROOT / "ai.zcode.ZCode.appdata.xml"
HOMEPAGE = "https://zcode.z.ai"
CDN = "https://cdn-zcode.z.ai/zcode/electron/releases"
# The marketing site (zcode.z.ai) rejects non-browser User-Agents with an empty
# body, which used to silently break version detection. The CDN itself doesn't
# care, but we use the same UA everywhere for simplicity.
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def http(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def latest_upstream_version() -> str:
    html = http(HOMEPAGE).decode("utf-8", "replace")
    versions = set(re.findall(r"/releases/(\d+\.\d+\.\d+)/", html))
    if not versions:
        raise SystemExit("No versions found on homepage")
    # semver-ish sort
    def key(v: str):
        return tuple(int(p) for p in v.split("."))
    return sorted(versions, key=key)[-1]


def current_version() -> str:
    text = MANIFEST.read_text()
    m = re.search(r"/releases/(\d+\.\d+\.\d+)/", text)
    if not m:
        raise SystemExit("Could not find current version in manifest")
    return m.group(1)


def sha256_of(url: str) -> str:
    h = hashlib.sha256()
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=300) as r:
        for chunk in iter(lambda: r.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def bump_manifest(new: str, deb_url: str, sha256: str) -> None:
    text = MANIFEST.read_text()
    # Match both the legacy layout (releases/<v>/ZCode-...) and the current one
    # (releases/<v>/linux-x64/ZCode-...).
    text = re.sub(
        r"url: https://cdn-zcode\.z\.ai/zcode/electron/releases/[\d.]+/(?:linux-x64/)?ZCode-[\d.]+-linux-x64\.deb",
        f"url: {deb_url}",
        text,
    )
    text = re.sub(r"sha256: [0-9a-f]{64}", f"sha256: {sha256}", text)
    MANIFEST.write_text(text)


def refresh_appdata(version: str) -> None:
    yml = ""
    try:
        yml = http(f"{CDN}/{version}/linux-x64/latest.yml").decode("utf-8", "replace")
    except Exception:
        pass

    date = ""
    m = re.search(r"releaseDate:\s*['\"]?([^'\"\n]+)", yml)
    if m:
        date = m.group(1).strip().split("T")[0]

    # The markdown is a YAML literal block (|-) that may contain headers and
    # blank lines before the bullets, so capture the whole indented block and
    # then keep only the "- " lines.
    notes_block = ""
    mb = re.search(
        r"en-US:\s*\n\s*title:[^\n]*\n\s*markdown:\s*\|-\n((?:[ \t]+.*\n?)+)", yml
    )
    if not mb:
        mb = re.search(r"releaseNotes:\s*\|-\n((?:[ \t]+.*\n?)+)", yml)
    if mb:
        notes_block = mb.group(1)
    notes = [ln.strip().lstrip("- ").strip() for ln in notes_block.splitlines() if ln.strip().startswith("- ")]

    def esc(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    li = "\n          ".join(f"<li>{esc(n)}</li>" for n in notes) if notes else "<li>(see upstream release notes)</li>"
    block = (
        f'    <release version="{version}" date="{date}">\n'
        f"      <description>\n"
        f"        <p>Release {version}:</p>\n"
        f"        <ul>\n"
        f"          {li}\n"
        f"        </ul>\n"
        f"      </description>\n"
        f"    </release>"
    )

    text = APPDATA.read_text()
    # drop any existing entry for this version
    text = re.sub(r"\s*<release version=\"%s\".*?</release>\n?" % re.escape(version), "", text, flags=re.S)
    # insert right after <releases>
    text = re.sub(r"(<releases>\n)", r"\1" + block + "\n", text, count=1)
    APPDATA.write_text(text)


def main() -> int:
    new = latest_upstream_version()
    cur = current_version()
    print(f"current={cur} latest={new}")
    if new == cur:
        print("changed=false")
        return 0

    deb_url = f"{CDN}/{new}/linux-x64/ZCode-{new}-linux-x64.deb"
    print(f"downloading {deb_url} ...")
    digest = sha256_of(deb_url)
    print(f"sha256={digest}")

    bump_manifest(new, deb_url, digest)
    refresh_appdata(new)
    print(f"version={new}")
    print("changed=true")
    return 0


if __name__ == "__main__":
    sys.exit(main())
