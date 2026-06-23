"""Release checklist template."""

# Hermes OS Release Checklist

## Pre-release
- [ ] bump version in `pyproject.toml`
- [ ] ensure `tests/` is green
- [ ] update `CHANGELOG.md`
- [ ] review `docs/adr-index.md`

## Release
- [ ] create release branch
- [ ] run `python scripts/run_benchmarks.py`
- [ ] build package `python -m build`
- [ ] tag release

## Post-release
- [ ] publish release notes
- [ ] verify docs deployed
