# IPC_BUS.md — OX-HOUSE-OS-1 Phase 4
Apps and services communicate only through the Event Bus — never by direct
references. Topics are dotted; subscribe to an exact topic, a prefix wildcard
(`runtime.*`), or all (`*`).

EventBus: subscribe(pattern, handler, owner) → unsubscribe fn ·
unsubscribe_owner(owner) · publish(topic, payload, source) → #delivered ·
history(prefix, limit) · topics() · subscriptions().

Guarantees: synchronous delivery; **handler isolation** (a raising subscriber
never breaks the publisher or other subscribers); bounded history for
observability. App subscriptions are tagged by owner and torn down on app stop.
OS lifecycle events: `os.boot_start/os.ready`, `app.installed/started/stopped/
uninstalled`, `package.installed/rolledback`. API: `GET /api/os/ipc?topic=`.
