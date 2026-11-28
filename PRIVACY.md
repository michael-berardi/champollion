# Privacy and local data

Champollion is an offline toolkit. It does not translate, does not upload your
text and does not call a model. This page lists every network route, every file
the toolkit writes, how long each one lives and how to remove it. The
[README](README.md#privacy) keeps the short summary.

## Network

Nothing is sent over the network by the toolkit itself except the anonymous
daily release check and the downloads of an update you ask for, both described
below. There is no telemetry, analytics, crash reporting, account or licence
check.

Network use happens only in these cases:

- **Release check** (automatic, at most once every 24 hours). In an interactive
  terminal, Champollion makes one anonymous GET of
  `https://api.github.com/repos/<owner>/<repo>/releases/latest` for the
  repository named in the package metadata, with the fixed
  `champollion-update-check` User-Agent. It sends no identity, version, usage,
  machine or project data and needs no account; GitHub sees the request's IP
  address, as for any web request. The request runs on a background thread
  while your command runs and is given up after four seconds. After a
  successful command, the result (or the failure and its cause) is cached for a
  day and shown by `champollion update --check`, and a newer stable `x.y.z`
  release is announced on stderr. Checks are off when stdout or stderr is not a
  terminal, in CI, under agent hosts, for `--json`, from a source checkout or
  vendored snapshot, or when you opt out with `CHAMPOLLION_NO_UPDATE_CHECK=1` or
  `"check": false` in the state file. See [docs/updates.md](docs/updates.md).
- **Updates you ask for.** `champollion update` reads the same release record
  when you run it. Installing a release, on request or after you turn automatic
  installs on (they are off by default), downloads the release's `SHA256SUMS`
  and wheel from GitHub for an installer copy. A pip, uv or pipx copy runs that
  package manager, which fetches the tagged release from GitHub with git and
  keeps its own cache as it normally does.
- **Installer scripts** (`install.sh`, `install.ps1`). They download
  `SHA256SUMS` and the release wheel from GitHub. The wheel's SHA-256 is checked
  before the installer's pip installs it offline with `--no-index`, with pip's
  version check and cache off.
- **pip routes.** The `pip install ...git+...` and `pip install .` forms are plain
  pip: pip contacts GitHub (git form) and may download build tooling from PyPI.
  The checksum and offline flags above apply only to the installer scripts.
- **Source URLs.** `champollion source add --url ...` does not fetch the URL. It
  prints a `curl` command for you to run or skip. A source URL or a `--site-url`
  you supply is written into the book's metadata as text; nothing opens it during
  export.
- **Export renderer.** `champollion export` starts a Chrome/Chromium already
  installed on this machine to render a local HTML page. That browser is launched
  with background networking, component updates, metrics, extensions and DNS
  disabled, with `DO_NOT_TRACK=1` and a temporary profile; the book is not
  uploaded. The cover capture drives that browser over a pipe pair, not a
  debugging port, so no socket is opened and nothing listens on the machine.
- **Reviewers and model providers you choose.** If you send packets or books to
  a reviewer or model provider of your choice, that third party receives what
  you send it. Champollion does not contact that provider.

The release check does not read, hash or transmit a work document, source,
packet, reviewer reply or export.

## Local writes and lifetimes

Every file below is written by the toolkit, not read from your text unless you
put it there. Files and directories the toolkit creates for your text are
owner-only (0600 files, 0700 directories) on macOS and Linux. On Windows, access
follows the folder's own permissions. The install home is `~/.champollion`
(Windows: `%LOCALAPPDATA%\Champollion`), or `CHAMPOLLION_HOME` if you set it.

| Write | Where | Lifetime |
| --- | --- | --- |
| Project scaffolding: `champollion.json`, `profiles/`, `sources/manifest.json`, `works/`, `sources/raw/` | The project folder you name with `champollion init` | Until you delete the project. `check` never changes work documents. |
| Source snapshots | `sources/raw/` in the project | Until you delete them; replaced only by `source add --replace`. |
| Packets, reviewer replies, review records, assembled work copies | The `--out` or output paths you name | Until you delete them. |
| Exported books (PDF, EPUB) | The output paths you name | Until you delete them. |
| Export temporary folder (`champollion-*`: the HTML page, the temporary browser profile, the intermediate PDF or cover) | The system temporary folder | Deleted when each render finishes, including when it fails. If the process is killed first, the next command run from an installer-managed install removes `champollion-*` entries there that are more than a day old (on macOS and Linux, only ones you own). |
| Vendored snapshots | The directory you name with `champollion vendor --into` | Until you delete them. |
| Update state: last check time and result or failure cause, skipped version, last notice, automatic-install choice and last error | macOS `~/Library/Caches/champollion/update.json`; Linux `~/.cache/champollion/update.json` (or under `$XDG_CACHE_HOME`); Windows `%LOCALAPPDATA%\Champollion\Cache\update.json` | Written after the first check or setting. One owner-only file, replaced atomically and never appended; delete it to reset the state. |
| Automatic-install log: a timestamped result line per attempt, plus any output of the install's venv and pip steps | `update.log` beside `update.json` | Only after you turn automatic installs on. Owner-only; before and after each attempt a log over 128 KB is cut to its newest 128 KB, keeping it within 256 KB. Never contains work text. |
| Installed program and at most one rollback copy | `venv` and `venv.previous` in the install home | The program stays until you delete it. Only `champollion update` on macOS and Linux keeps `venv.previous`; see the rollback copy below. |
| First-run marker `venv.first-run.json`: the installed version and the install time | The install home | Written by `champollion update` after a swap. Removed with the rollback copy, by `update --rollback`, or once the rollback copy is gone. |
| Install staging and swap remnants: `venv.tmp.<pid>` (update and installers), `venv.rollback.<pid>` (`update --rollback`), `venv.old` (installers) | The install home | Removed by the step that made them, on success, failure or a refused checksum. A `venv.tmp.<pid>` or `venv.rollback.<pid>` left by a killed step is removed by the next command from that installer-managed install once it is six minutes old; the installers remove a leftover `venv.old` on their next run. |
| Update and installer downloads | `champollion-update.*` (`update`), `champollion-install.*` (`install.sh`) and `champollion-install-*` (`install.ps1`) under the system temporary folder | Removed when the update or install ends, whether it succeeds or fails. |
| Command shim | `~/.local/bin/champollion` (Windows: the tool's `bin` folder) | Installer; until you delete it. |
| Python bytecode caches (`__pycache__`) | Next to the installed modules, and in the install home | Code, not your text; deleted with the environment. |

Logs of your text, commands, history or transcripts are not stored. The one
exception above is `update.log`, which records automatic install attempts only,
stays within 256 KB and never contains work text. The toolkit writes no other
file and never copies a work document into a cache, a log or the install home.

## Retention that runs by itself

Nothing runs in the background between commands: these lifetimes are applied
when you next run Champollion.

- **Update state** is a single small owner-only JSON file, replaced atomically;
  it does not grow with use.
- **Install log** is cut to its newest 128 KB before and after each automatic
  install attempt.
- **Install staging** is deleted by the install that made it, and stale staging
  is pruned by the next command from the installer-managed install.
- **Rollback copy** is dropped by the first successful command run by the
  version that `champollion update` just installed. If that run never happens,
  the first command at least seven days after the install time recorded in
  `venv.first-run.json` removes it, whether or not that command succeeds. A
  fresh marker keeps an old copy until one of those happens. An unreadable or
  undated marker falls back to its own modification time; a marker with no
  readable timestamp is treated as seven days old, so no marker state extends
  the bound. A copy without a marker goes after the next successful command or
  seven days after the swap. `champollion update --rollback` restores the copy
  and removes the marker; `update --auto off` only stops future automatic
  installs and is not a deletion command.
- **Export leftovers** in the system temporary folder are removed by the next
  command from an installer-managed install once they are a day old.

These steps run after the command has finished, print nothing and cannot change
a command's exit status. They apply only to the installer-managed environment
(`venv` in the install home): a checkout, a pip install or a test run leaves a
real install home and the shared system temporary folder untouched. Set
`CHAMPOLLION_HOME` to move the install home and `TMPDIR` to move the temporary
folder.

## Removing everything

Run `champollion update --auto off`, then delete your project folders, any
packets, review records, vendored snapshots or exported books you created, the
install home, the `champollion` shim on your `PATH` and the cache folder that
holds `update.json` and `update.log`. On Windows, deleting
`%LOCALAPPDATA%\Champollion` removes the install, the default `bin` folder and
the cache folder together. To drop only the update state, delete `update.json`
and `update.log`. Nothing else is kept, so no request or account is needed.
