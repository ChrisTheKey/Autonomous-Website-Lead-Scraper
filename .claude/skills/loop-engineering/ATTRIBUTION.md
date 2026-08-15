# Attribution

This skill is vendored from an upstream project, unmodified.

- **Upstream:** https://github.com/maxmilian/loop-engineering
- **Commit:** `da0030b2fabbed7a6f8e7f18f5f9157bf63db7b3`
- **Vendored on:** 2026-08-15
- **License:** MIT © 2026 Max Hsu (see `LICENSE` in this directory)

## What was copied

| Path | Included |
|---|---|
| `SKILL.md` | yes |
| `references/` | yes |
| `evals/` | yes |
| `LICENSE` | yes |
| `README.md` (+ translations), `assets/` | no — upstream marketing/docs, not needed at runtime |

## Updating

```sh
git clone --depth 1 https://github.com/maxmilian/loop-engineering /tmp/le
cp /tmp/le/SKILL.md .claude/skills/loop-engineering/
cp -r /tmp/le/references /tmp/le/evals /tmp/le/LICENSE .claude/skills/loop-engineering/
```

Then update the commit SHA above.
