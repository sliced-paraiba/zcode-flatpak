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
    https://xiaot-evo.github.io/zcode-flatpak/repo
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

Runs on `org.freedesktop.Sdk` **25.08** (the full SDK used as the runtime,
like the Zed/VS Code flatpaks do). It is a superset of the Platform — same
GTK3, NSS, cups, ALSA, ATK/at-spi and graphics stack — and additionally ships
the developer toolchain (`git`, `git-lfs`, `python3`, `gcc`, `make`, ...),
which ZCode's built-in git integration and the agent can use inside the
sandbox. Trade-off: the SDK is a larger download (~1.5 GB vs ~1 GB) on first
install/update.

### Host toolchain access

The sandbox mounts the host's root filesystem **read-only** at `/run/host`
(`--filesystem=host-os`) and bridges common developer tools into the app, so
the integrated terminal, the agent's bash tool and third-party plugin MCP
servers can use your real host toolchain:

- **Shell**: `$SHELL` points at `/app/bin/host-shell`, a `flatpak-spawn --host`
  wrapper that starts **your host shell in the host namespace**. It uses the
  `$SHELL` value captured from the host session (falling back to the host
  `passwd` entry, e.g. when launched from a desktop menu). This keeps the
  terminal and the agent's tools running your real shell (`~/.bashrc` /
  `~/.zshrc` environment included) — and is immune to glibc mismatches, since
  the host shell never loads inside the sandbox.
- **git / python3**: provided by the `org.freedesktop.Sdk` runtime
  (`/usr/bin/git`, `/usr/bin/python3` — glibc-safe, host-independent); ZCode's
  built-in git integration is pinned to `/usr/bin/git` via
  `ZCODE_GIT_BINARY`. Node is embedded in the app itself. None of ZCode's
  direct dependencies need host forwarding.
- **Optional host tools** (MCP servers, `nix`, ...): use the general
  `/app/bin/host-run` forwarder — a `flatpak-spawn --host` wrapper that runs
  the same-named host command in the host namespace (glibc-immune). `nix` is
  pre-wrapped (`/app/bin/nix`, probing NixOS/`/nix`/`~/.nix-profile`
  locations); for anything else add a symlink in `build-commands`:
  `ln -s host-run /app/bin/<cmd>` (requires a rebuild) — or configure
  `/usr/bin/flatpak-spawn --host ...` directly in your MCP server config
  (no rebuild needed).
- **`nix`**: wrapped separately (`/app/bin/nix`) because nix lives outside
  `/usr/bin` on most setups (NixOS: `/run/current-system/sw/bin/nix`, which is
  not even visible inside the sandbox; multi-user/determinate Nix:
  `/nix/var/...`). The wrapper probes the common locations on the host side.
  Use it for MCP servers that run via `nix run ...`.
- **Everything else** resolves through `/run/host/usr/bin` via `PATH`. Note
  that this path only exists on distros with a real `/usr` (Arch, Debian, ...);
  on NixOS host commands are invisible in the sandbox and **must** go through
  a `flatpak-spawn` wrapper (`ln -s host-run /app/bin/<cmd>` + rebuild).
  The host `PATH` still reaches the wrappers: ZCode's startup login-shell
  probe (`$SHELL -ilc env -0` through `host-shell`) pulls the host environment
  into the app, and `flatpak-spawn --host` resolves commands against it.

Caveats: the host root is read-only (the app can't modify host system files);
host processes and sockets are still invisible to the sandbox; and a host
binary that requires a newer glibc than the runtime ships will fail to load if
it is reached through `/run/host` directly — wrap it with a `flatpak-spawn`
forwarder (as above) to run it glibc-safely. Note that after ZCode's startup
login-shell env probe, the sandbox `PATH` is replaced by the host's (NixOS
paths like `/run/current-system/sw/bin` don't exist inside the sandbox) — the
wrappers use absolute paths (`/usr/bin/flatpak-spawn`, ...) and `git` is
pinned to `/app/bin/git` via `ZCODE_GIT_BINARY` precisely so they keep working
under that polluted `PATH`.

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
flatpak install --user flathub org.freedesktop.Sdk//25.08
flatpak-builder --user --install-deps-from=flathub --force-clean \
    --repo=repo build-dir ai.zcode.ZCode.yaml
flatpak remote-add --user --no-gpg-verify --if-not-exists zcode-local repo
flatpak install --user zcode-local ai.zcode.ZCode
```

---

Assisted-by: ZCode:GLM-5.2
