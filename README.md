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
| `.github/workflows/auto-update.yml` | Runs **hourly**. Probes the ZCode CDN's per-version `latest.yml` files for a new release (the CDN has no directory listing and the website's download table lags behind); when found, rewrites the manifest's URL + `sha256` and the appdata `<releases>` section, then commits — which triggers a rebuild. |
| `.github/workflows/build.yml` | Builds the flatpak with `flatpak-builder`, exports it into a GitHub-Pages-hosted OSTree repo, and publishes a single-file `.flatpak` bundle as a build artifact. |

### Runtime

Built against `org.freedesktop.Platform`/`Sdk` **25.08** (latest stable), which
provides the GTK3, NSS, cups, ALSA, ATK/at-spi and graphics stack that the
bundled Electron binary links against.

### Host toolchain access

The sandbox mounts the host's root filesystem **read-only** at `/run/host`
(`--filesystem=host-os`) and bridges common developer tools into the app, so
the integrated terminal, the agent's bash tool and third-party plugin MCP
servers can use your real host toolchain:

- **Shell**: `$SHELL` is pointed at your host shell (`/run/host/usr/bin/...`)
  when it loads inside the runtime. The terminal and agent tools then run your
  real shell and pick up your `~/.bashrc`/`~/.zshrc` environment (conda, nvm,
  custom `PATH`, ...). If the host binary can't load (the host glibc may be
  newer than the runtime's — `GLIBC_xx not found`), it falls back to the
  runtime's own bash.
- **git**: used via `ZCODE_GIT_BINARY` when the host git loads, otherwise via
  the `flatpak-spawn` wrapper.
- **`git`, `node`, `python3`**: wrapped in `/app/bin` as `flatpak-spawn --host`
  forwarders that execute the host's binary **in the host namespace** — immune
  to glibc/library mismatches by construction. Want more? Add a symlink in
  `build-commands`: `ln -s host-run /app/bin/<cmd>` (requires a rebuild).
- **Everything else** resolves through `/run/host/usr/bin` via `PATH`.

Caveats: the host root is read-only (the app can't modify host system files);
host processes and sockets are still invisible to the sandbox; and a host
binary that requires a newer glibc than the runtime ships will fail to load
unless it is reached through a `flatpak-spawn` wrapper (add one, as above).

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
