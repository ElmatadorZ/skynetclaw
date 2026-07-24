# WORKSPACE_MODEL.md — OX-HOUSE-OS-1 Phase 7
A workspace is a portable, self-contained directory under
`<data>/workspaces/<name>/` with subdirs: `memory · registry · runtime · logs ·
settings · plugins` + a `workspace.json`. No absolute paths (config.paths), so a
workspace can be zipped, moved, or shipped inside GenesisHouse.exe.

WorkspaceManager: create(name) · list() · switch(name) · current() · describe().
Multiple workspaces isolate memory/registry/runtime/logs/settings/plugins.
