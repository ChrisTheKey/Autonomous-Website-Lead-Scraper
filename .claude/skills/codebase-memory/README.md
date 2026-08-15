# codebase-memory (Skill)

Herkunft: [DeusData/codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp)

- Quelle: `src/cli/cli.c`, eingebettete Konstante `skill_content`
  (dort die Single Source of Truth für den CLI-Installer)
- Stand: Commit `c0bd4bbf8dace58cffdb24fad86d95e325df99f4` (2026-08-14)
- Lizenz: MIT, Copyright (c) 2025 DeusData

`SKILL.md` ist unverändert übernommen (byte-genau der Text, den `cbm install`
nach `~/.claude/skills/codebase-memory/SKILL.md` schreibt).

## Voraussetzung

Der Skill beschreibt nur die Nutzung der 15 MCP-Tools. Damit er etwas bewirkt,
muss der MCP-Server `codebase-memory-mcp` installiert und im Agent
konfiguriert sein:

```bash
curl -fsSL https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/main/install.sh | bash
```

Der Installer konfiguriert erkannte Clients selbst und legt den Skill global
ab. Diese Kopie hier ist die repo-lokale Variante (`.claude/skills/`), damit
der Skill auch ohne globale Installation im Projekt verfügbar ist.

## Aktualisieren

Bei einer neuen Upstream-Version den Text erneut aus `skill_content` in
`src/cli/cli.c` ziehen und `SKILL.md` sowie die Commit-Angabe oben ersetzen.
