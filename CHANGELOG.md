# Changelog

All notable changes to Hermes OS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Event bus replay API for historical event replay.
- Graceful shutdown support for `ProcessAdapter`.
- Dependency groups in `pyproject.toml`.
- Persistent Run Journal (append/update/list) in `src/hermes_os/run_journal`.
- `RunJournalEntry` dataclass in `src/hermes_os/types.py`.

### Fixed
- Moved bootstrap test artifacts from `docs/contracts/` to `docs/contracts/_test_artifacts/`.
- Restored `contracts-index.yaml` consistency with actual contract count.
- Updated `test_bootstrap_tools.py` for date-agnostic contract creation assertions.
