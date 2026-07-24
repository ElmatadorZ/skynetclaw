# PACKAGE_SYSTEM.md — OX-HOUSE-OS-1 Phase 5
Genesis Packages (`.gpkg`) = a ZIP containing `manifest.json` + app files.

PackageManager: build_gpkg(manifest, files, out) · read_gpkg · install(gpkg) ·
update(gpkg) · rollback(app_id) · uninstall(app_id) · list_versions(app_id).

Versioning: every install/update over an existing app snapshots the current app
dir into `plugins/versions/<id>/<ver>-<ts>/` first, so **rollback** restores the
previous version (and rollback itself snapshots current → reversible). Uninstall
delegates to the Application Manager. All paths via config.paths (portable).
