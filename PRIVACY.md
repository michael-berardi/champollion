# Privacy

Champollion is an offline toolkit. This page lists every network request it makes and every file it writes outside your project folders.

## Network

- **Update check** (automatic, at most once a day): one anonymous GET of `https://api.github.com/repos/<owner>/<repo>/releases/latest` for the repository in the package metadata, with the User-Agent `champollion-update-check`. It sends nothing about you, your machine, your version or your texts; GitHub sees the request's IP address, as for any web request. It runs only in an interactive terminal: never in CI, under agent hosts, for `--json` output, or from a source checkout or vendored snapshot. Turn it off with `CHAMPOLLION_NO_UPDATE_CHECK=1` or `"check": false` in the state file. See [docs/updates.md](docs/updates.md).
- **Updates** (only when you run `champollion update`, or after you turn automatic installs on): the same release record, then the release's `SHA256SUMS` and wheel from GitHub. pip, uv and pipx installs run that package manager, which fetches the tagged release from GitHub with git.
- **Installers** (`install.sh`, `install.ps1`): download `SHA256SUMS` and the wheel from the GitHub release.
- **`source add --url`** fetches nothing; it prints a `curl` command for you to run.
- **`export`** starts the Chrome or Chromium already on your machine to render a local page. Champollion sends the book nowhere.

There is no telemetry, analytics, crash reporting, account or licence check. Checks, reports and review read and write local files and call no model.

## Files outside your project

| What | Where | When |
|---|---|---|
| Update state: last check and its result or failure cause, skipped version, last notice, automatic-install choice | macOS `~/Library/Caches/champollion/update.json`; Linux `~/.cache/champollion/update.json` (or under `$XDG_CACHE_HOME`); Windows `%LOCALAPPDATA%\Champollion\Cache\update.json` | after the first check; owner-only |
| Automatic-install log, one file under 256 KB | `update.log` beside the state file | only after you turn automatic installs on |
| Installed program and at most one rollback copy | `~/.champollion/venv` and `~/.champollion/venv.previous` (Windows: `%LOCALAPPDATA%\Champollion`) | installer and `update`; the rollback copy goes once the new version completes a command, or after 7 days |
| Command shim | `~/.local/bin/champollion` (Windows: the tool's `bin` folder) | installer |

Update downloads and build folders are temporary and are removed when the update ends, whether it succeeds or fails.

## Removing everything

Run `champollion update --auto off`, then delete your project folders, `~/.champollion`, the `champollion` shim and the cache folder above. On Windows, deleting `%LOCALAPPDATA%\Champollion` removes the cache folder too.
