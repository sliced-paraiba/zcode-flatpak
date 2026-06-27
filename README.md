# zcode-flatpak

Unofficial [Flatpak](https://flatpak.org) packaging of **[ZCode](https://zcode.z.ai)** —
the GLM-5.2 coding harness from Z.ai — published as a self-hosted Flatpak
repository via GitHub Pages. No Flathub submission required.

The upstream ZCode binary is a prebuilt Electron app shipped as a `.deb`. This
repository does **not** build ZCode from source; it wraps the upstream binary so
it can be installed and updated through Flatpak on any Linux distribution.

## Install

```sh
flatpak remote-add --user --no-gpg-verify zcode \
    https://sliced-paraiba.github.io/zcode-flatpak/repo
flatpak install --user zcode ai.zcode.ZCode
```

Then launch **ZCode** from your application menu, or:

```sh
flatpak run ai.zcode.ZCode
```

## Update

```sh
flatpak update ai.zcode.ZCode
```

## How it works

| File | Purpose |
| --- | --- |
| `ai.zcode.ZCode.yaml` | Flatpak manifest. Downloads the upstream `.deb`, unpacks it, installs the Electron tree + icons + desktop entry under `/app`. |
| `ai.zcode.ZCode.appdata.xml` | AppStream metadata (description, screenshots, release notes). |
| `.github/workflows/auto-update.yml` | Runs **hourly**. Polls the ZCode website for a new release; when found, rewrites the manifest's URL + `sha256` and the appdata `<releases>` section, then commits — which triggers a rebuild. |
| `.github/workflows/build.yml` | Builds the flatpak with `flatpak-builder`, exports it into a GitHub-Pages-hosted OSTree repo, and publishes a single-file `.flatpak` bundle as a build artifact. |

### Runtime

Built against `org.freedesktop.Platform`/`Sdk` **25.08** (latest stable), which
provides the GTK3, NSS, cups, ALSA, ATK/at-spi and graphics stack that the
bundled Electron binary links against.

## Limitations / notes

- **No GPG signing.** The published OSTree repo is unsigned; you add it with
  `--no-gpg-verify` as shown above. This is the trade-off for avoiding the
  Flathub review process. If you want verified updates, clone and build locally.
- **Unofficial.** ZCode is © Z.ai. This packaging is a community convenience
  and is not affiliated with or endorsed by Z.ai. Upstream issues belong on the
  ZCode site / beta group, not here.
- **x86_64 only** for now (matching the upstream Linux release).

## Build locally

```sh
flatpak install --user flathub org.freedesktop.Platform//25.08 org.freedesktop.Sdk//25.08
flatpak-builder --user --install-deps-from=flathub --force-clean \
    --repo=repo build-dir ai.zcode.ZCode.yaml
flatpak remote-add --user --no-gpg-verify --if-not-exists zcode-local repo
flatpak install --user zcode-local ai.zcode.ZCode
```

---

Assisted-by: ZCode:GLM-5.2
