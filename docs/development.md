# Development

```
uv sync --group dev
corepack enable
pnpm --dir brawlfarm/web install
pnpm --dir brawlfarm/web build     # the panel is served from brawlfarm/web/dist
uv run pytest
pnpm --dir brawlfarm/web test && pnpm --dir brawlfarm/web typecheck
uv run ruff check . && uv run ruff format --check .
uv run python tools/scrub_check.py
```

If `corepack enable` fails with EPERM, which is what a Windows shell without elevation gives you, `npm install -g pnpm@10.17.1` installs the same pnpm.

`pnpm --dir brawlfarm/web dev` serves the panel on Vite's port with hot reload and proxies `/api` to a `uv run brawlfarm` on 8765, so the two run side by side while you work on the UI.

## Contributing

Bug reports and pull requests are welcome, and [CONTRIBUTING.md](../CONTRIBUTING.md) has the conventions and the checks to run before you open one. One rule outranks every other: a change to the never-tap logic or the safety rails is not merged on any other merit, however good the rest of the change is.
