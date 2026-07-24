# PERMISSION_MODEL.md — OX-HOUSE-OS-1 Phase 3
Applications never touch runtime/memory/fs/network directly. Every privileged
action is brokered by the Permission + Capability Manager and recorded in the
Audit Log.

Capabilities (declared in the app manifest):
`runtime.infer · runtime.read · memory.read · memory.write · fs.read · fs.write ·
net.http · service.use · ipc.publish · ipc.subscribe · package.manage ·
workspace.manage`

PermissionManager: grant(app, caps) (unknown caps rejected) · revoke · granted ·
check(app, cap) → bool (audited) · require(app, cap) → raises PermissionDenied.
AuditLog: every check (allow + deny) is recorded; `denials()` surfaces violations.
API: `GET /api/os/permissions?actor=`.

Enforcement point = `AppContext`: e.g. `ctx.publish()` calls
`permissions.require(app,"ipc.publish")` before the bus ever sees the message.
