# DESKTOP_SHELL.md — OX-HOUSE-OS-1 Phase 9
`GET /desktop` serves the Genesis Desktop shell: a sidebar (Runtime Monitor /
Services / Applications / IPC Bus / Permissions / Marketplace / Launcher) and a
live panel that polls `/api/os` (state, service health, installed apps, IPC
topics, permission audit counts). Auto-refresh; backend-only mission so this is a
minimal HTML shell over the OS APIs — no framework, no build step, themed to the
House. Richer UI is a frontend concern layered on the same `/api/os/*` surface.
