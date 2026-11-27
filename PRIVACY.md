# Privacy and local data

Champollion is an offline toolkit. It does not translate, does not upload your
text and does not call a model. This page lists every network route, every file
the toolkit writes, how long each one lives and how to remove it. The
[README](README.md#privacy) keeps the short summary.

## Network

Nothing is sent over the network by the toolkit itself except the anonymous
release check described below. There is no telemetry, analytics, crash reporting
or licence check.

Network use happens only when you start it:

- **Release check.** In an interactive terminal, each command hands a once-daily,
  anonymous check to a detached low-priority helper and returns immediately: one
  GET to the repository's public GitHub latest-release record, with the fixed
  `champollion-update-check` User-Agent and no identity, version, usage or
  machine data. The GET has a 3-second timeout; failures are cached locally with
  their cause and shown only by `champollion update --check`. A due notice from an
  earlier check appears on the next interactive command. Checks are off in CI,
  non-TTY/headless/agent use, with `CHAMPOLLION_NO_UPDATE_CHECK=1`, or when
  `updates.check` is false in the tool's config. Automatic installing is opt-in
  and off by default; when enabled, the same helper installs within a five-minute
  bounded budget and cleans its staging on failure.
- **Installer scripts.** They download the installer, `SHA256SUMS` and the
  release wheel from GitHub. The wheel's SHA-256 is checked before the
  installer's pip installs it offline with `--no-index`, with pip's version check
  and cache off.
- **pip routes.** The `pip install ...git+...` and `pip install .` forms are plain
  pip: pip contacts GitHub (git form) and may download build tooling from PyPI.
  The checksum and offline flags above apply only to the installer scripts.
- **Source URLs.** `champollion source add --url ...` does not fetch the URL. It
  prints a `curl` command for you to run or skip. A source URL or a `--site-url`
  you supply is written into the book's metadata as text; nothing opens it during
  export.
- **Export renderer.** `champollion export` starts a Chrome/Chromium already
  installed on this machine to render a local HTML page. That browser is launched
  with background networking, component updates, metrics and DNS disabled, and
  with `DO_NOT_TRACK=1`; the book is not uploaded.
- **Third parties you choose.** If you send packets or books to a reviewer or
  model provider of your choice, that third party receives what you send it.
  Champollion does not contact that provider.

The release check does not read, hash or transmit a work document, source,
packet, reviewer reply or export.

## Local writes and lifetimes

Every file below is written by the toolkit, not read from your text unless you
put it there. Files and directories the toolkit creates for your text are
owner-only (0600 files, 0700 directories) on macOS and Linux. On Windows, access
follows the folder's own permissions.

| Write | Where | Lifetime |
| --- | --- | --- |
| Project scaffolding: `champollion.json`, `profiles/`, `sources/manifest.json`, `works/`, `sources/raw/` | The project folder you name with `champollion init` | Until you delete the project. `check` never changes work documents. |
| Source snapshots | `sources/raw/` in the project | Until you delete them; replaced only by `source add --replace`. |
| Packets, reviewer replies, review records, assembled work copies | The `--out` or output paths you name | Until you delete them. |
| Exported books (PDF, EPUB) | The output paths you name | Until you delete them. |
| Export temp folder (`champollion-*`: the HTML page, the temporary browser profile, the intermediate PDF or cover) | The system temporary folder | Deleted when the export finishes. A killed export's leftovers are removed by the next successful command run from an installer-managed install once they are a day old. |
| Vendored snapshots | The directory you name with `champollion vendor --into` | Until you delete them. |
| Preferences: `config.json` (check on/off, auto install, skipped version) | `~/.config/champollion` (Windows: `%LOCALAPPDATA%\Champollion`) | Until you change them or delete the file. Rewritten in place, never appended. |
| Update cache: `updates.json` (last check time, latest version, release notes, last error, last install record) | `~/Library/Caches/champollion` on macOS, `~/.cache/champollion` on Linux, `%LOCALAPPDATA%\Champollion\Cache` on Windows | Rewritten at most daily while checks are on; holds no work text. Delete the file to reset it. |
| Install log: `updates-install.log`, one JSON line per install attempt | The same cache folder | Capped at 256 KB; the oldest lines are dropped first. |
| Installed environment and command shim | `~/.champollion` (Windows: `%LOCALAPPDATA%\Champollion`), shim in `~/.local/bin` | Until you reinstall, uninstall, or roll back. |
| Install staging: `.champollion-stage-*`, `venv.next.<pid>` | The install home | Removed on success, failure, timeout or a refused checksum; anything older than about six minutes is pruned by the next command run from that installer-managed install. |
| Rollback copy: `venv.previous`, with its `venv.first-run.json` marker and any `venv.rollback-swap` leftover | The install home | Removed after the installed version has run successfully once, or by the next successful command after seven days from the install time at the latest. The marker's install time sets that clock when the marker exists, so an old replaced environment is not expired early; a marker that cannot be read or holds no date expires from its own timestamp instead, and one without even that is treated as seven days old; a future-dated marker is treated as fresh until the next successful command, not as an extension of the seven-day clock. `champollion update --rollback` restores it and clears the marker; a later install replaces it. |
| Python bytecode caches (`__pycache__`) | Next to the installed modules, and in the install home | Code, not your text; deleted with the environment. |

No logs of your text, commands, history or transcripts are stored. The one
exception listed above is `updates-install.log`, which records install attempts
only (version, result and error cause), is capped at 256 KB and never contains
work text. The toolkit writes no other file, and it never copies a work document
into a cache, a log or the install home.

## Retention that runs by itself

- **Update cache and preferences** are a single small JSON file each, replaced
  atomically; they do not grow with use.
- **Install log** keeps complete JSON lines and at most 256 KB of them.
- **Install staging** is deleted by the install that made it, and stale staging
  is pruned before the next install and by the next command from that install.
- **Rollback copy** is dropped by the first successful run of the version that
  was just installed, which is why it is kept at all; if that run never happens,
  the copy is removed by the next successful command after seven days from the install time recorded in its marker,
  or from the marker's own timestamp when it is unreadable or undated, and from
  the copy's own timestamp for an install without a marker. A marker whose
  timestamp cannot be read at all is treated as seven days old, so no marker
  state extends the bound. `update --auto off`
  stops future automatic installs but is not a deletion command; remove `venv.previous`
  yourself if you want it gone sooner, or run `update --rollback` first.
- **Export leftovers** in the system temporary folder are removed by the next
  successful command from an installer-managed install once they are a day old.

These steps run after the command has finished, print nothing and cannot change
a command's exit status. Staging and temporary-folder cleanup runs only from the
installer-managed environment: a checkout, a pip install or a test run leaves a
real install home and the shared system temporary folder untouched. Set
`CHAMPOLLION_HOME`, `CHAMPOLLION_CONFIG_DIR`,
`CHAMPOLLION_CACHE_DIR` or `TMPDIR` to move the corresponding files.

## Deleting your data

Remove the project folders and any packets, review records, vendored snapshots or
exported books you created. If you used the installer, also remove `~/.champollion`
(Windows: `%LOCALAPPDATA%\Champollion`) and the `champollion` shim on your `PATH`
(Windows: the tool's `bin` folder). To drop only the update state, delete
`config.json`, `updates.json` and `updates-install.log` from the folders named
above. Nothing else is kept, so no request or account is needed.
