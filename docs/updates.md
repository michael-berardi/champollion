<!-- update-contract: v1 -->

# Updates

Champollion tells you when a newer stable release exists and installs it with one command. Automatic installs stay off until you turn them on.

## The check

- At most once a day, while a command you typed in a terminal runs, Champollion reads the public GitHub "latest release" record of the repository named in its package metadata (`/repos/<owner>/<repo>/releases/latest`).
- It is one anonymous GET with the User-Agent `champollion-update-check`. It sends no version, id, usage, machine or project data and needs no account.
- It runs in the background and gives up after 4 seconds. A failure is stored with its cause, shown by `champollion update --check`, and not retried until the next day.
- It does not run when stdout or stderr is not a terminal, when `CI` is set, under an agent host (`CLAUDECODE`, `CODEX_SANDBOX`, `GEMINI_CLI`, `CHAMPOLLION_AGENT` and similar), for `--json` output, from a source checkout or vendored snapshot, or when you opt out.
- Only stable `x.y.z` releases strictly newer than yours count. Drafts, prereleases and unparseable tags are ignored.

When a newer release exists, two lines follow your command's output on stderr, at most once a day per version:

```text
champollion 1.11.0 available (you have 1.10.0) · run: champollion update
turn on automatic updates: champollion update --auto on · skip: champollion update --skip
```

## Commands

```sh
champollion update               # show the new version and its notes, confirm, install
champollion update --check       # report only: exit 0 current, 10 update available, 1 check failed
champollion update --skip        # no notice for this version; a newer one notifies again
champollion update --auto on     # install future updates automatically (also: off, status)
champollion update --rollback    # restore the version the last update replaced
```

In a terminal, `update` asks `Install 1.11.0 now? [Y/n]`, then once, if automatic installs are off, `Install future updates automatically? [y/N]`. The answer is remembered. Without a terminal, or with `--json`, `update` installs without questions: running it is the consent.

## Turning the check off

Set `CHAMPOLLION_NO_UPDATE_CHECK=1`, or set `"check": false` in the state file below.

## Automatic installs

When on, the check that finds a newer release starts one detached, low-priority install. The command you ran is not affected; the new version applies on the next run. Output goes to `update.log` beside the state file (one file, kept under 256 KB). A failed automatic install leaves the current version working, records its cause (`update --auto status` shows it) and brings the notice back.

## How each install kind updates

- **install.sh (macOS, Linux):** downloads the release's `SHA256SUMS` and the wheel it lists, checks the SHA-256 before anything changes, builds a new environment beside the current one, checks that it runs, then swaps it in. The replaced environment stays as `~/.champollion/venv.previous` for `update --rollback` until the new version completes a command, and for 7 days at most. Downloads go to a temporary folder that is removed whether the update succeeds or fails.
- **install.ps1 (Windows):** Windows cannot replace a running environment, so the notice names the installer instead: `irm https://github.com/<owner>/<repo>/releases/latest/download/install.ps1 | iex`.
- **pip, uv tool, pipx:** `update` runs the package manager's own command pinned to the release tag, for example `uv tool install --force "champollion-protocol @ git+https://github.com/<owner>/<repo>.git@v1.11.0"`. It never overwrites files a package manager owns.
- **Source checkout or vendored snapshot:** no notice. Update with `git pull`, or vendor a newer tag.

## Files

One state file holds the last check time and result (or failure cause), the skipped version, the last notice and your automatic-install choice. It is owner-only and replaced atomically.

| Platform | State file |
|---|---|
| macOS | `~/Library/Caches/champollion/update.json` |
| Linux | `$XDG_CACHE_HOME/champollion/update.json` (default `~/.cache/champollion/`) |
| Windows | `%LOCALAPPDATA%\Champollion\Cache\update.json` |

To remove Champollion completely, run `champollion update --auto off`, then delete `~/.champollion`, the `champollion` shim on your PATH, and the cache folder above. On Windows, deleting `%LOCALAPPDATA%\Champollion` removes the cache folder too.

For tests against a local server, `CHAMPOLLION_UPDATE_API` replaces the release-record URL and `CHAMPOLLION_RELEASE_BASE` replaces the download base, as it does for the installers.
