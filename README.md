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

The sandbox runs on `org.freedesktop.Sdk` **25.08**, a superset of the
Platform that ships the full developer toolchain (`git`, `git-lfs`,
`python3`, `gcc`, `make`, ...). ZCode's direct dependencies — git, python3,
node (embedded) — all live inside the sandbox, so no host forwarding is
needed for the terminal or the agent.

**Terminal / agent**: `$SHELL` defaults to `/usr/bin/bash` (SDK's bash,
glibc-safe, immune to the PATH pollution from ZCode's startup env probe).
The integrated terminal and the agent's bash tool run this SDK bash, with
full access to all SDK tools.

**Optional: host shell override**. If you want the terminal to use your host
shell (e.g. fish on NixOS) instead of the SDK bash, set the
`ZCODE_HOST_SHELL` env var via `flatpak override`:

```sh
flatpak override --user ai.zcode.ZCode \
    --env=ZCODE_HOST_SHELL=/run/current-system/sw/bin/fish
```

The launcher detects this and uses your host shell via the `host-shell`
wrapper (which runs it in the host namespace via `flatpak-spawn --host`).
Otherwise it stays on the reliable SDK bash.

**MCP servers**: configure them with `/usr/bin/flatpak-spawn --host <cmd>`
directly in your MCP config (no rebuild needed). The bundled
`/app/bin/nix` wrapper probes NixOS-common locations (`/run/current-system/sw`,
`/nix`, `~/.nix-profile`) on the host side.

**Optional host tool wrapper**: `/app/bin/host-run` forwards any same-named
command to the host namespace via `flatpak-spawn --host`. Add more commands
with a symlink (requires rebuild):

```sh
# in build-commands:
ln -s host-run /app/bin/<cmd>
```

Caveats: the sandbox mounts the host root read-only at `/run/host`
(`--filesystem=host-os`) but you don't need it for the default case — the
SDK bash has everything ZCode needs. Host processes and sockets remain
invisible to the sandbox; a host binary with a newer glibc will still fail
if reached directly (use the wrapper for those).

---

Assisted-by: ZCode:GLM-5.2
