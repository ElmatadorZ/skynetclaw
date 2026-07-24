"""
test_genesis_os.py — OX-HOUSE-OS-1 Phase 10
Validation for the OS layer: IPC bus, permissions+audit, service lifecycle,
workspace, application lifecycle (install/start/stop/uninstall, dependencies,
permission gating), and package manager (.gpkg install/update/rollback).
Deterministic; data dirs redirected to tmp.
"""
from __future__ import annotations
import os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pytest
from config import paths as cpaths
import os_ipc, os_permissions, os_services, os_workspace, os_packages, genesis_os


def test_ipc_pubsub_wildcard_and_isolation():
    bus = os_ipc.EventBus()
    got = []
    bus.subscribe("a.*", lambda t, p: got.append((t, p)))
    bus.subscribe("a.x", lambda t, p: (_ for _ in ()).throw(ValueError()))  # bad handler
    n = bus.publish("a.x", 1)
    assert ("a.x", 1) in got            # wildcard prefix delivered
    assert n >= 1                       # isolation: bad handler didn't break publish
    assert bus.publish("b.y", 2) == 0   # no subscriber match


def test_permissions_grant_check_deny_audit():
    pm = os_permissions.PermissionManager()
    r = pm.grant("app", ["ipc.publish", "bogus.cap"])
    assert "ipc.publish" in r["granted"] and "bogus.cap" in r["unknown"]
    assert pm.check("app", "ipc.publish") is True
    assert pm.check("app", "net.http") is False
    with pytest.raises(os_permissions.PermissionDenied):
        pm.require("app", "net.http")
    assert any(not e["allowed"] for e in pm.audit.denials())


def test_service_lifecycle():
    s = os_services.WorkflowService()
    s.start(); assert s.state == "running" and s.health()["state"] == "running"
    s.restart(); assert s.state == "running"
    s.stop(); assert s.state == "stopped"


def test_scheduler_service_runs_job():
    s = os_services.SchedulerService(); hits = []
    s.add_job("j", lambda: hits.append(1), 0.05); s.start()
    time.sleep(0.7); s.stop()
    assert len(hits) >= 1


def test_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(cpaths, "user_data_dir", lambda: str(tmp_path))
    wm = os_workspace.WorkspaceManager()
    wm.create("w1"); assert "w1" in wm.list()
    assert wm.switch("w1")["current"] == "w1"
    assert os.path.isdir(wm.current().dir("memory"))


def _os(tmp_path, monkeypatch):
    monkeypatch.setattr(cpaths, "user_data_dir", lambda: str(tmp_path))
    return genesis_os.GenesisOS()


def test_app_install_start_stop_uninstall(tmp_path, monkeypatch):
    o = _os(tmp_path, monkeypatch)
    man = {"id": "t.app", "name": "T", "version": "1.0.0",
           "permissions": ["ipc.publish"], "entrypoint": "app.py"}
    o.apps.install(man, {"app.py": "def setup(ctx): ctx.publish('t.ev', 1)\n"})
    got = []; o.ipc.subscribe("t.ev", lambda t, p: got.append(p), owner="test")
    assert o.apps.start("t.app")["state"] == "running"
    assert got == [1]                                   # app ran + published via IPC
    assert "ipc.publish" in o.permissions.granted("t.app")
    assert o.apps.stop("t.app")["state"] == "stopped"
    o.apps.uninstall("t.app"); assert o.apps.list() == []


def test_app_dependency_enforced(tmp_path, monkeypatch):
    o = _os(tmp_path, monkeypatch)
    o.apps.install({"id": "b", "version": "1", "dependencies": ["a"], "entrypoint": "app.py"},
                   {"app.py": "def setup(c): pass\n"})
    r = o.apps.start("b")
    assert r["state"] == "error" and "depend" in r["error"]


def test_app_permission_gating_blocks_undeclared(tmp_path, monkeypatch):
    o = _os(tmp_path, monkeypatch)
    o.apps.install({"id": "np", "version": "1", "permissions": [], "entrypoint": "app.py"},
                   {"app.py": "def setup(ctx): ctx.publish('x', 1)\n"})
    r = o.apps.start("np")
    assert r["state"] == "error"                        # PermissionDenied during setup


def test_package_install_update_rollback(tmp_path, monkeypatch):
    o = _os(tmp_path, monkeypatch)
    gp = str(tmp_path / "p.gpkg")
    man = {"id": "pk", "version": "1.0.0", "permissions": [], "entrypoint": "app.py"}
    os_packages.build_gpkg(man, {"app.py": "def setup(c): pass\n"}, gp)
    o.packages.install(gp); assert o.apps.apps["pk"].manifest.version == "1.0.0"
    man2 = dict(man); man2["version"] = "2.0.0"
    os_packages.build_gpkg(man2, {"app.py": "def setup(c): pass\n"}, gp)
    o.packages.update(gp); assert o.apps.apps["pk"].manifest.version == "2.0.0"
    assert o.packages.list_versions("pk")               # history kept
    o.packages.rollback("pk"); assert o.apps.apps["pk"].manifest.version == "1.0.0"


def test_os_boot_status(tmp_path, monkeypatch):
    o = _os(tmp_path, monkeypatch)
    b = o.boot(start_services=False)
    assert b["state"] == "running"
    st = o.status()
    assert st["state"] == "running" and "services" in st and "workspace" in st
