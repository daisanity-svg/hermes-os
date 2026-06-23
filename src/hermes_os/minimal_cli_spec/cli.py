"""Minimal CLI entry point for Hermes OS (MVP)."""

from __future__ import annotations

import sys

from hermes_os.minimal_cli_spec import DEFAULT_CLI_SPEC


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args or args[0] in {"--help", "-h", "help"}:
        print(f"{DEFAULT_CLI_SPEC.binary_name} {DEFAULT_CLI_SPEC.version}")
        print("commands:", ", ".join(DEFAULT_CLI_SPEC.list_commands()))
        return 0
    if args[0] in {"--version", "-v"}:
        print(DEFAULT_CLI_SPEC.version)
        return 0
    print(f"unknown command: {args[0]}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
