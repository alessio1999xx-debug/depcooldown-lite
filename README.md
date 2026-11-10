# depcooldown-lite: dependency cooldown check that fails CI when a pinned PyPI or npm package is too new

depcooldown-lite helps with a dependency cooldown for the pins you already committed: it reads a `requirements.txt` or `package-lock.json`, asks the public PyPI / npm registry when each pinned version was published, and exits `1` if any is younger than `--cooldown` days (default 7). One file, Python 3.9+ standard library only, read-only, MIT.

- Nothing to `pip install`. One file per run, no config, no state.
- Flags: `--cooldown`, `--json`, `--version`.

## Install

```bash
curl -fsSLO https://raw.githubusercontent.com/alessio1999xx-debug/depcooldown-lite/main/depcooldown_lite.py
python3 depcooldown_lite.py --help
```

## Check a requirements.txt or package-lock.json for releases that are too new

```bash
python3 depcooldown_lite.py requirements.txt
# 2 pinned pypi packages in requirements.txt, cooldown 7 days
#   OK         requests==2.32.3  (894.7 days old)
#   OK         urllib3==2.2.3  (788.9 days old)
# OK: nothing inside the cooldown

python3 depcooldown_lite.py package-lock.json --cooldown 3
python3 depcooldown_lite.py requirements.txt --json
```

Only exact pins are checked (`name==version` lines in requirements files, every resolved package in `package-lock.json` v1/v2/v3). Ranges like `flask>=2` are skipped. A version the registry can't confirm is shown as `UNVERIFIED` and does not fail the run.

## Exit codes for CI

| Exit code | Meaning |
| --- | --- |
| `0` | No pinned version is younger than `--cooldown` days |
| `1` | At least one pinned version was published fewer than `--cooldown` days ago |
| `2` | Bad arguments, missing file, or a file type the lite version doesn't read |

```yaml
# any CI: run it as a step before installing
- run: curl -fsSLO https://raw.githubusercontent.com/alessio1999xx-debug/depcooldown-lite/main/depcooldown_lite.py && python3 depcooldown_lite.py requirements.txt
```

## Already using pip --uploaded-prior-to or uv exclude-newer?

New pip versions have `--uploaded-prior-to` and uv has `exclude-newer`, which stop the resolver from picking very new releases at install time. If those cover you, use them. depcooldown-lite is for checking the pins you **already** committed, in Python and npm projects alike, with a plain exit code.

## depcooldown-lite vs DepCooldown

depcooldown-lite checks one `requirements*.txt` or `package-lock.json` against the live registry and tells you which pins are too new. That's it.

The full **[DepCooldown](https://py-forge.com/products/depcooldown-dependency-release-age-gate?utm_source=github&utm_medium=readme&utm_campaign=depcooldown-lite)** helps with:

- `uv.lock`, `poetry.lock` and `pyproject.toml` as well as requirements and npm lockfiles
- a suggested older version that is outside the cooldown, for each flagged package
- `--diff-base` against a git ref to flag brand-new dependencies and major version jumps
- an offline mode that reuses a local JSON cache of registry release dates
- a Markdown report for the CI job summary

One-time payment, yours to keep. No subscription.

Or get every PyForge tool, current and future, with the [All-Access Pass](https://py-forge.com/pass?utm_source=github&utm_medium=readme&utm_campaign=depcooldown-lite).

See also [pthguard-lite](https://github.com/alessio1999xx-debug/pthguard-lite), which scans a virtualenv for `.pth` startup backdoors.

## Tests

```bash
python3 test_depcooldown_lite.py
```

The tests are offline: registry answers are faked.

## License

MIT (this lite version). The full DepCooldown is sold separately under its own license.
