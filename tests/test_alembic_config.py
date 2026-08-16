"""Tests for Alembic database configuration.

The migration URL used to be hardcoded in alembic.ini as a localhost address,
which was wrong inside Docker where the database host is a service name.
alembic/env.py now sets it at runtime from the application settings, so these
tests pin that contract down.
"""

import configparser
from pathlib import Path

from alembic.config import Config

from app.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = REPO_ROOT / "alembic.ini"
DOCKERIGNORE = REPO_ROOT / ".dockerignore"

# env.py escapes "%" before handing the URL to ConfigParser; a password
# containing an encoded "@" is the realistic case that would otherwise break.
URL_WITH_PERCENT = "postgresql+asyncpg://user:p%40ss@db:5432/lead_discovery"


def _read_ini() -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    parser.read(ALEMBIC_INI)
    return parser


class TestAlembicIni:
    def test_declares_no_hardcoded_url(self):
        assert not _read_ini().has_option("alembic", "sqlalchemy.url")

    def test_carries_no_localhost_address(self):
        assert "localhost" not in ALEMBIC_INI.read_text()

    def test_alembic_reads_no_url_from_the_file_alone(self):
        assert Config(str(ALEMBIC_INI)).get_main_option("sqlalchemy.url") is None


class TestSettingsDriveTheUrl:
    def test_database_url_follows_the_environment(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", URL_WITH_PERCENT)
        assert Settings().database_url == URL_WITH_PERCENT

    def test_alembic_receives_the_application_url(self, monkeypatch):
        """Reproduces exactly what alembic/env.py does to the config object."""
        monkeypatch.setenv("DATABASE_URL", URL_WITH_PERCENT)
        settings = Settings()

        config = Config(str(ALEMBIC_INI))
        config.set_main_option(
            "sqlalchemy.url", settings.database_url.replace("%", "%%")
        )

        assert config.get_main_option("sqlalchemy.url") == URL_WITH_PERCENT

    def test_engine_section_carries_the_url(self, monkeypatch):
        """run_async_migrations builds the engine from the section, not the option."""
        monkeypatch.setenv("DATABASE_URL", URL_WITH_PERCENT)
        settings = Settings()

        config = Config(str(ALEMBIC_INI))
        config.set_main_option(
            "sqlalchemy.url", settings.database_url.replace("%", "%%")
        )

        section = config.get_section(config.config_ini_section, {})
        assert section["sqlalchemy.url"] == URL_WITH_PERCENT


class TestDockerignore:
    def _entries(self) -> list[str]:
        return [
            line.strip()
            for line in DOCKERIGNORE.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]

    def test_excludes_env_and_build_artifacts(self):
        entries = self._entries()
        for pattern in (".env", ".env.*", ".git", "__pycache__", "*.pyc"):
            assert pattern in entries

    def test_keeps_the_env_example(self):
        assert "!.env.example" in self._entries()

    def test_negation_follows_the_pattern_it_reincludes(self):
        entries = self._entries()
        assert entries.index("!.env.example") > entries.index(".env.*")
