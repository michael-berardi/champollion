# Updates

<!-- update-contract: v1 -->

Champollion is a command-line toolkit. Updates are announced as one or two lines
on **stderr after your command has finished**; there is no graphical window,
settings sheet or rendered UI for updates. Automatic checks never add text to
`--json` output.

## Check (on by default in a terminal)

- Once every 24 hours per machine, an interactive command makes **one anonymous
  GET** to the public GitHub "latest release" record of the repository named in
  the installed package's metadata. The fixed User-Agent is
  `champollion-update-check`. No identity, version, usage, machine data or local
  file content is sent. Drafts, prereleases, malformed tags and equal or older
  versions are ignored.
- After a successful interactive command, the check is handed to a **detached,
  low-priority one-shot helper process**. The CLI does not wait for it and does
  not block on the network: the helper's single GET has a 3-second timeout. Its
  result is recorded in a shared, owner-only (0600) cache file with any cause,
  never printed as noise and never retried in a loop. An in-flight claim in
  the cache prevents a second command from starting a duplicate helper. A due
  notice from a previous check is shown on the next interactive command;
  `champollion update --check` remains synchronous and shows the recorded cause.
- Checks are off when stdout or stderr is not a TTY, when `CI` is set, in
  headless/print mode (`--json`), in agent mode, or when opted out.
- Opt out with `CHAMPOLLION_NO_UPDATE_CHECK=1` for one shell, or set
  `updates.check` to `false` in the tool's config JSON. Preference and cache
  files live in the platform config and cache directories; both are written
  atomically with owner-only permissions.

When a newer stable release is found and notice is due, stderr shows:

```text
champollion 1.2.3 available (you have 1.2.2) · run: champollion update
turn on automatic updates: champollion update --auto on · skip: champollion update --skip
```

The second line is dimmed on a colour terminal. A version is announced at most
once per 24 hours; `champollion update --skip` hides it until a newer release
appears.

## Commands

| Command | Behaviour |
| --- | --- |
| `champollion update --check` | Report current → latest stable and the first lines of release notes; no install. Exit `0` current, `10` available, `1` check failed with cause. `--json` emits one JSON object. |
| `champollion update` | Show the release, then on a TTY ask `Install 1.2.3 now? [Y/n]`. With no TTY the explicit command installs without questions. |
| `champollion update --skip` | Remember the checked version and suppress its notice until a newer one exists. |
| `champollion update --auto on\|off\|status` | Opt in/out of automatic installs, or report the state. Automatic installs are **off by default**. |
| `champollion update --rollback` | Restore the one previous installer-managed venv. |

After a successful interactive install, with auto still off, the CLI asks once
`Install future updates automatically? [y/N]` and remembers the answer; answering
`n` means it is never asked again. `update --auto on` is the explicit alternative.
The choice is stored in the tool's config, not just in the environment, so it
survives upgrades.

## Automatic installs (opt-in)

When automatic installs are on, the same detached helper performs the install
instead of printing a notice. It has a real bounded budget (five minutes total
for downloads, staging, the health check and the swap), is low priority, and
writes one install log capped at 256 KB in the tool's cache directory. The new
version applies on the next invocation; running work is never swapped underneath
a process. Downloads and staging live in one temporary folder inside the
private install home and are removed on success, failure or a refused swap, so
a failed install leaves neither a half-built environment nor stale `venv.next.*`
directories. A failed install leaves the current version working, records its
cause and falls back to a notice on the next interactive command. If the helper
cannot start at all, the failure is recorded with its cause and nothing is
staged.

## Install safety

Installer-managed copies download the release wheel and `SHA256SUMS`, verify the
wheel's SHA-256, stage a fresh private environment, run a health check, and only
then swap it into place. The prior environment is kept once as `venv.previous`
for `champollion update --rollback`; a failed swap restores it. A checksum
mismatch refuses the install and changes nothing.

### Known gap in contract §4a

Contract §4a asks for a rollback copy to be deleted after the new version has
run successfully once, and at the latest within seven days; it also asks
`update --auto off` to clear saved auto state. This build does **not** implement
that cleanup. An installer-managed swap keeps its single rollback environment
(`venv.previous` in the private install home) **indefinitely**: there is no
first-successful-run check and no seven-day expiry. Remove that directory
manually when you no longer need it, or run `champollion update --rollback` to
restore it first. `champollion update --auto off` sets the saved automatic-install
preference to off and stops future automatic installs, but it **does not delete
the rollback copy** and does not start any timed cleanup.

Package-manager installs are detected instead of overwritten. The prompt names
the right command (`uv tool upgrade champollion-protocol`,
`python3 -m pip install --upgrade "champollion-protocol @ git+…@vX"`, or the
equivalent manager command), and `champollion update` runs that command rather
than touching files the manager owns.

## Privacy boundary

The release check does not read, hash or transmit a work document, source,
packet, reviewer reply or export. Local text remains in the directories you
choose; installer-managed code remains under the private install home. If you
opt out, the CLI makes no update request at all. See the [Privacy section of the
README](../README.md#privacy) for the rest of the toolkit's network and file
behaviour.
