# Privacy and local data

Champollion is an offline toolkit. It does not translate, does not upload your
text and does not call a model. This page lists every network route, every file
the toolkit writes, how long each one lives and how to remove it. The
[README](README.md#privacy) keeps the short summary.

## Network

Nothing is sent over the network by the toolkit itself except the anonymous
release check described below. There is no telemetry, analytics, crash
reporting, account or licence check.

Network use happens only in these cases:

- **Release check.** In an interactive terminal, at most once every 24 hours,
  Champollion makes one anonymous GET to the public GitHub "latest release"
  record of the repository named in the package metadata, with the fixed
  `champollion-update-check` User-Agent. It sends no identity, version, usage,
  machine or project data and needs no account. The check runs on a background
  thread while your command finishes; it waits at most four seconds, and a
  failure is cached with its cause for `champollion update --check`. A due
  notice is printed on stderr after your command. Checks are off when stdout or
  stderr is not a terminal, in CI, in agent hosts, for `--json`, from a source
  checkout or vendored snapshot, or when `CHAMPOLLION_NO_UPDATE_CHECK=1` or
  `"check": false` in the state file. Only a newer stable `x.y.z` release is
  announced. Automatic installs are opt-in and off by default.
- **Installer scripts.** They download `SHA256SUMS` and the release wheel from
  GitHub. The wheel's SHA-256 is checked before the installer's pip installs it
  offline with `--no-index`, with pip's version check and cache off.
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
- **Reviewers and model providers you choose.** If you send packets or books to
  a reviewer or model provider of your choice, that third party receives what
  you send it. Champollion does not contact that provider.

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
| Export temp folder (`champollion-*`: the HTML page, the temporary browser profile, the intermediate PDF or cover) | The system temporary folder | Deleted when the export finishes. A killed export's leftovers are removed by the next successful command from an installer-managed install once they are a day old. |
| Vendored snapshots | The directory you name with `champollion vendor --into` | Until you delete them. |
| Update state: last check time and result or failure cause, skipped version, last notice, automatic-install choice and last error | macOS `~/Library/Caches/champollion/update.json`; Linux `~/.cache/champollion/update.json` (or under `$XDG_CACHE_HOME`); Windows `%LOCALAPPDATA%\Champollion\Cache\update.json` | One owner-only file, rewritten in place and never appended; delete it to reset the state. |
| Automatic-install log: one line per attempt with version, result and error cause | `update.log` beside `update.json` | Only after you turn automatic installs on; capped at 256 KB, oldest lines dropped first. Never contains work text. |
| Installed program and at most one rollback copy | `~/.champollion/venv` and `~/.champollion/venv.previous` (Windows: `%LOCALAPPDATA%\Champollion`) | Installer and `update`; see the rollback lifetime below. |
| Install staging and swap remnants: `venv.tmp.<pid>`, `venv.rollback.<pid>`, `venv.first-run.json` | The install home | Removed on success, failure or a refused checksum; stale staging older than about six minutes is pruned by the next command from that installer-managed install. |
| Update downloads | `champollion-update.*` under the system temporary folder | Removed when the update ends, whether it succeeds or fails. |
| Command shim | `~/.local/bin/champollion` (Windows: the tool's `bin` folder) | Installer; until you delete it. |
| Python bytecode caches (`__pycache__`) | Next to the installed modules, and in the install home | Code, not your text; deleted with the environment. |

Logs of your text, commands, history or transcripts are not stored. The one
exception above is `update.log`, which records install attempts only, is capped
at 256 KB and never contains work text. The toolkit writes no other file and never
copies a work document into a cache, a log or the install home.

## Retention that runs by itself

- **Update state** is a single small owner-only JSON file, replaced atomically;
  it does not grow with use.
- **Install log** keeps complete JSON lines and at most 256 KB of them.
- **Install staging** is deleted by the install that made it, and stale staging
  is pruned by the next command from the installer-managed install.
- **Rollback copy** is dropped by the first successful run of the version that
  was just installed. If that run never happens, the copy is removed by the next
  successful command after seven days from the install time recorded in
  `venv.first-run.json`. A fresh marker keeps an old copy until the first
  successful run. An unreadable or undated marker falls back to its own
  modification time; a marker with no readable timestamp is treated as seven
  days old, so no marker state extends the bound. `champollion update --rollback`
  restores the copy and clears the marker; `update --auto off` only stops future
  automatic installs and is not a deletion command.
- **Export leftovers** in the system temporary folder are removed by the next
  successful command from an installer-managed install once they are a day old.

These steps run after the command has finished, print nothing and cannot change
a command's exit status. They apply only to the installer-managed environment:
a checkout, a pip install or a test run leaves a real install home and the shared
system temporary folder untouched. Set `CHAMPOLLION_HOME` to move the install
home and `TMPDIR` to move the temporary folder.

## Removing everything

Run `champollion update --auto off`, then delete your project folders, any
packets, review records, vendored snapshots or exported books you created,
`~/.champollion` (Windows: `%LOCALAPPDATA%\Champollion`) and the `champollion`
shim on your `PATH` (Windows: the tool's `bin` folder). To drop only the update
state, delete `update.json` and `update.log` from the cache folder named above.
Nothing else is kept, so no request or account is needed.
