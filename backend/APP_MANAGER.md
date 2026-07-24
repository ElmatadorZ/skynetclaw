# APP_MANAGER.md — OX-HOUSE-OS-1 Phase 1
Applications live in `plugins/apps/<id>/` (under config.paths data dir) with a
`manifest.json` and an entrypoint module exporting `setup(ctx)` / `teardown(ctx)`.

## Manifest
```json
{ "id":"sample.hello", "name":"Hello", "version":"1.0.0",
  "dependencies":["other.app"], "permissions":["ipc.publish","ipc.subscribe"],
  "entrypoint":"app.py", "description":"..." }
```
## Lifecycle (ApplicationManager)
discover → install → **start** (check deps → grant declared permissions → import
entrypoint → `setup(AppContext)`) → stop (`teardown` + unsubscribe) → uninstall.
States: installed | running | stopped | error.

## Isolation
Apps receive an **AppContext** — the only OS surface they get. Every privileged
method (`infer`/`publish`/`subscribe`/`service`) checks a capability via the
Permission Manager first, then routes through IPC / Service Manager / Kernel.
Apps hold NO direct references to runtime/memory/fs/network. Unmet dependency or
missing permission → app enters `error`, never partial-privilege.

API: `GET /api/os/apps`, `POST /api/os/apps/{id}/{start|stop|uninstall}`.
