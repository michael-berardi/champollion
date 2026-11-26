# Privacy

Champollion is an offline toolkit. This page lists every network request it makes and every file it writes outside your project folders.

## Network

- **Update check** (automatic, at most once a day): one anonymous GET of `https://api.github.com/repos/<owner>/<repo>/releases/latest` for the repository in the package metadata, with the User-Agent `champollion-update-check`. It sends nothing about you, your machine, your version or your texts; GitHub sees the request's IP address, as for any web request. It runs only in an interactive terminal: never in CI, under agent hosts, for `--json` output, or from a source checkout or vendored snapshot. Turn it off with `CHAMPOLLION_NO_UPDATE_CHECK=1` or `"check": false` in the state file. See [docs/updates.md](docs/updates.md).
- **Updates** (only when you run `champollion update`, or after you turn automatic installs on): the same release record, then the release's `SHA256SUMS` and wheel from GitHub. pip, uv and pipx installs run that package manager, which fetches the tagged release from GitHub with git.
- **Installers** (`install.sh`, `install.ps1`): download `SHA256SUMS` and the wheel from the GitHub release; the wheel's SHA-256 is checked before pip installs it offline with `--no-index`, with pip's cache and version check off. The `pip install ...git+...` and `pip install .` routes are plain pip: pip contacts GitHub and may download build tooling from PyPI.
- **`source add --url`** fetches nothing; it prints a `curl` command for you to run.
- **`export`** starts the Chrome or Chromium already on your machine to render a local page, with background networking, component updates, metrics, extensions and DNS disabled and `DO_NOT_TRACK=1`, in a temporary profile deleted afterwards. Champollion sends the book nowhere. A source URL or `--site-url` you supply is written into the book's metadata as text; nothing opens it.
- **Reviewers and model providers you choose** receive whatever packets or books you send them; Champollion never contacts them.

There is no telemetry, analytics, crash reporting, account or licence check. Checks, reports and review read and write local files and call no model.

## Files in your project

`champollion init` writes `champollion.json`, `profiles/`, `sources/manifest.json` and `works/`; source snapshots go under `sources/raw/`, and packets, review records and books go where you direct them. Files and folders the toolkit creates for your text are owner-only (0600/0700) on macOS and Linux; on Windows, access follows the folder's own permissions. No logs, history or transcripts are kept.

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
