"""Tests for the Compose service definitions.

The flower service runs `celery ... flower`, but that subcommand only exists
when the separate `flower` distribution is installed. It was missing from
requirements.txt, so the container failed at startup with exit code 2 and
"No such command 'flower'". These tests pin the dependency down and guard the
general case for any other non-builtin celery subcommand.
"""

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
COMPOSE = REPO_ROOT / "docker-compose.yml"
REQUIREMENTS = REPO_ROOT / "requirements.txt"

# Subcommands celery ships with. Anything else has to come from its own package.
CELERY_BUILTIN_COMMANDS = frozenset(
    {
        "amqp",
        "beat",
        "call",
        "control",
        "events",
        "graph",
        "inspect",
        "list",
        "logtool",
        "migrate",
        "multi",
        "purge",
        "report",
        "result",
        "shell",
        "status",
        "upgrade",
        "worker",
    }
)


def _compose() -> dict:
    return yaml.safe_load(COMPOSE.read_text())


def _requirement_names() -> set[str]:
    names = set()
    for raw in REQUIREMENTS.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        name = re.split(r"[<>=!~\[;]", line, maxsplit=1)[0].strip().lower()
        if name:
            names.add(name)
    return names


def _celery_subcommand(command: str) -> str | None:
    """Return the subcommand from a `celery ...` command line, else None."""
    tokens = command.split()
    if not tokens or tokens[0] != "celery":
        return None
    index = 1
    while index < len(tokens):
        token = tokens[index]
        if token in ("-A", "--app", "-b", "--broker"):
            index += 2
            continue
        if token.startswith("-"):
            index += 1
            continue
        return token
    return None


class TestComposeFile:
    def test_parses(self):
        assert isinstance(_compose().get("services"), dict)

    def test_declares_no_obsolete_version_key(self):
        assert "version" not in _compose()


class TestCelerySubcommandsAreInstalled:
    def test_flower_service_still_uses_the_flower_subcommand(self):
        command = _compose()["services"]["flower"]["command"]
        assert _celery_subcommand(command) == "flower"

    def test_flower_package_is_declared(self):
        assert "flower" in _requirement_names()

    def test_every_non_builtin_subcommand_has_a_requirement(self):
        names = _requirement_names()
        for service, definition in _compose()["services"].items():
            subcommand = _celery_subcommand(definition.get("command") or "")
            if subcommand is None or subcommand in CELERY_BUILTIN_COMMANDS:
                continue
            assert subcommand in names, (
                f"service {service!r} runs 'celery {subcommand}' but "
                f"{subcommand!r} is not declared in requirements.txt"
            )
