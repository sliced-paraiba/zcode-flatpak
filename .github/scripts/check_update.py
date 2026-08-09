#!/usr/bin/env python3
"""Check the ZCode CDN for a new release and bump the flatpak manifest + appdata.

Triggered by .github/workflows/auto-update.yml. Exits 0 and prints
"changed=true|false" (as "changed=<bool>" for GHA output parsing) on the last
line; prints "version=<v>" when changed.

Strategy:
  * The CDN (an OSS bucket) has no directory listing and no global latest.yml
    pointer, and the marketing site hardcodes its download table (it listed
    only 3.6.5 while 3.7.x was already out), so walk the version space upward
    from the version currently pinned in ai.zcode.ZCode.yaml, probing each
    candidate's per-version linux-x64/latest.yml (~2KB authoritative metadata
    published by electron-builder for every release) and take the highest hit.
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
CDN = "https://cdn-zcode.z.ai/zcode/electron/releases"
# The marketing site (zcode.z.ai) rejects non-browser User-Agents with an empty
# body, which used to silently break version detection. The CDN itself doesn't
# care, but we use the same UA everywhere for simplicity.
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Probing limits for latest_upstream_version(): skip to the next minor after
# this many consecutive missing patches, and give up after this many entirely
# empty minors (with one extra probe for a possible major bump, e.g. 4.0.0).
PATCH_MISS_LIMIT = 8
EMPTY_MINOR_LIMIT = 2


def http(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def _published(version: str) -> bool:
    """True if upstream published a linux-x64 release for this version.

    The per-version latest.yml is the authoritative metadata (version,
    releaseDate, sha512) that electron-builder writes for every release;
    probing it is far cheaper than HEAD-ing or downloading the .deb.
    """
    try:
        http(f"{CDN}/{version}/linux-x64/latest.yml")
        return True
    except Exception:
        return False


def latest_upstream_version() -> str:
    """Probe the CDN for the newest published version (see module docstring)."""
    mj, mn, pt = (int(p) for p in current_version().split("."))
    best = (mj, mn, pt)
    misses = 0        # consecutive misses within the current minor
    empty_minors = 0  # consecutive minors that yielded no hits
    while True:
        version = f"{mj}.{mn}.{pt}"
        if _published(version):
            best = (mj, mn, pt)
            misses = 0
            empty_minors = 0
        else:
            misses += 1
            if misses >= PATCH_MISS_LIMIT:
                empty_minors += 1
                misses = 0
                pt = 0
                mn += 1
                if mn > 99:
                    mn = 0
                    mj += 1
                if empty_minors >= EMPTY_MINOR_LIMIT:
                    # Only give up after checking whether the major bumped
                    # (a major release has no preceding minor to probe).
                    if not _published(f"{mj}.0.0"):
                        break
                    empty_minors = 0
                continue
        pt += 1
        if pt > 99:
            pt = 0
            mn += 1
            if mn > 99:
                mn = 0
                mj += 1
    return f"{best[0]}.{best[1]}.{best[2]}"


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
