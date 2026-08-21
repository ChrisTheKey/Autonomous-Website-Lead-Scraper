"""Entry point HWD-ZERO invokes.

Reads one JSON invocation from stdin, runs the action, prints one JSON object as
the final stdout line. Exit code 0 means the action ran; a non-zero code means it
did not, and ZERO reads both.
"""

from __future__ import annotations

import sys

from zero_agent.actions import dispatch
from zero_agent.protocol import Invocation, Outcome


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    try:
        invocation = Invocation.from_json(raw)
    except ValueError as exc:
        Outcome(ok=False, error=str(exc)).emit()
        return 2

    outcome = dispatch(invocation)
    outcome.emit()
    # `unavailable` is not a crash: the action could not run, ZERO records why,
    # and the mission decides what to do. Exit 3 distinguishes it from a failure.
    if outcome.unavailable:
        return 3
    return 0 if outcome.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
