"""
system_doctor.py — SAFE read-only system diagnostics (the agent's eyes on the OS)
=================================================================================
Operators expect an AI agent to troubleshoot the basics — Wi-Fi, drivers,
connectivity — not just chat. It could not, because every system command was
`shell_command` (ESCALATE → a manual gate each time), so the model avoided it
and asked the user in circles instead.

The security theory the operator set stands: state-changing repair stays gated
(human decides). But DIAGNOSIS is read-only — the OS equivalent of read_file —
and read_file is `allow`. So this tool exposes a CURATED ALLOWLIST of
read-only diagnostic commands (Wi-Fi, network, drivers, system, disk, power)
that carry no state change, and is classified `allow`. Repair actions
(netsh reset, driver install, adapter enable/disable) are NOT here — the agent
runs those through shell_command and meets the gate, on purpose.

Safety is enforced structurally, not by trust:
  · the requested `check` must be a known key (no free-form command in)
  · each mapped command is verified read-only at call time (verb denylist)
  · no shell metacharacters are ever accepted from the model

Windows-first (the operator's platform); a POSIX map is provided where the
diagnostic has an equivalent.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import os
import subprocess
from typing import Any, Dict, List, Tuple

# Verbs that MUTATE state — if any diagnostic command ever contains one, it is
# refused. This is the invariant that keeps "diagnostics" from smuggling repair.
_MUTATING = (
    "set", "add", "delete", "del ", "remove", "reset", "install", "uninstall",
    "enable", "disable", "start", "stop", "restart", "format", "flushdns",
    "release", "renew", "netsh int", "reg add", "reg delete", "rmdir", "rd ",
    "shutdown", "sfc", "dism", "chkdsk", "diskpart", "bcdedit", "takeown",
    "icacls", "attrib", "schtasks /create", "sc config", "sc start", "sc stop",
)

# check-key → (windows argv, posix argv, human label). argv form only — never a
# shell string, so no metacharacter injection is possible.
_CHECKS_WIN: Dict[str, Tuple[List[str], str]] = {
    "wifi_status":       (["netsh", "wlan", "show", "interfaces"], "Wi-Fi adapter + current connection"),
    "wifi_profiles":     (["netsh", "wlan", "show", "profiles"], "saved Wi-Fi networks"),
    "wifi_drivers":      (["netsh", "wlan", "show", "drivers"], "Wi-Fi driver capabilities"),
    "ip_config":         (["ipconfig", "/all"], "all network adapters + IP/DNS/gateway"),
    "dns_cache":         (["ipconfig", "/displaydns"], "resolver cache (read-only)"),
    "connections":       (["netstat", "-ano"], "active TCP/UDP connections + owning PID"),
    "route_table":       (["route", "print"], "IP routing table"),
    "arp_table":         (["arp", "-a"], "ARP neighbor cache"),
    "network_adapters":  (["getmac", "/v", "/fo", "list"], "network adapters + MAC"),
    "drivers":           (["driverquery", "/v", "/fo", "csv"], "installed device drivers"),
    "system_info":       (["systeminfo"], "OS, uptime, memory, patches"),
    "running_processes": (["tasklist", "/v"], "running processes"),
    "services":          (["sc", "query"], "running services (read-only query)"),
    "disk":              (["wmic", "logicaldisk", "get", "name,size,freespace,filesystem"], "disk volumes + free space"),
    "battery":           (["powercfg", "/batteryreport", "/output", os.path.join(os.environ.get("TEMP", "."), "sd_battery.html")], "battery health report"),
    "gpu":               (["wmic", "path", "win32_VideoController", "get", "name,driverversion,adapterram"], "GPU + driver version"),
}
_CHECKS_POSIX: Dict[str, List[str]] = {
    "wifi_status":       ["nmcli", "device", "wifi", "list"],
    "ip_config":         ["ip", "addr"],
    "connections":       ["ss", "-tunap"],
    "route_table":       ["ip", "route"],
    "arp_table":         ["ip", "neigh"],
    "system_info":       ["uname", "-a"],
    "running_processes": ["ps", "aux"],
    "disk":              ["df", "-h"],
}

# problem keyword → ordered checks to run (so "wifi ต่อไม่ได้" runs the right sweep)
_PLAYBOOKS: Dict[str, List[str]] = {
    "wifi":     ["wifi_status", "wifi_drivers", "ip_config"],
    "internet": ["ip_config", "connections", "route_table"],
    "network":  ["ip_config", "network_adapters", "route_table"],
    "driver":   ["drivers", "gpu"],
    "slow":     ["running_processes", "disk", "system_info"],
    "disk":     ["disk"],
    "battery":  ["battery"],
}


# Binaries that are READ-ONLY diagnostics regardless of args (their read verbs
# are guarded by _MUTATING below). Used to auto-allow a shell_command that is
# provably just diagnosis, so a small model that reaches for shell instead of
# system_diagnostics still doesn't stall on the human gate.
_READONLY_BINS = (
    "netsh", "ipconfig", "ping", "tracert", "traceroute", "pathping", "nslookup",
    "arp", "route", "getmac", "driverquery", "systeminfo", "tasklist", "wmic",
    "powercfg", "hostname", "whoami", "ver", "netstat", "nmcli", "ip", "ss",
    "ps", "df", "uname", "lspci", "lsusb", "dmesg",
)
# shell metacharacters that could chain a second (mutating) command
_SHELL_META = ("&", "|", ">", "<", ";", "`", "$(", "&&", "||", "\n")


def is_readonly_diagnostic(command: str) -> bool:
    """True only when `command` is a single, read-only diagnostic invocation:
    a known diagnostic binary, no mutating verb, no shell chaining. Used by the
    governance gate to treat such a shell_command like read_file (allow)."""
    cmd = str(command or "").strip()
    if not cmd or any(m in cmd for m in _SHELL_META):
        return False
    low = cmd.lower()
    first = low.split()[0].strip('"').rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
    first = first[:-4] if first.endswith(".exe") else first
    if first not in _READONLY_BINS:
        return False
    return not any(m in low for m in _MUTATING)


# ── REPAIRS — curated, named, state-changing. Each is a FIXED command sequence
# (the model picks a NAME, never writes the command), and every repair is an
# ESCALATE tool: the operator approves it once at the gate before it runs. This
# is the "propose repair → operator approves → repair" half of the loop; the
# allowlist is the review surface (a known action, not model-authored shell).
_REPAIRS_WIN: Dict[str, Dict[str, Any]] = {
    "flush_dns": {
        "steps": [["ipconfig", "/flushdns"]],
        "desc": "clear the DNS resolver cache (fixes stale/last-known-bad name resolution)",
        "reboot": False, "admin": False},
    "renew_ip": {
        "steps": [["ipconfig", "/release"], ["ipconfig", "/renew"]],
        "desc": "release and renew the DHCP lease (fixes a bad/expired IP)",
        "reboot": False, "admin": True},
    "register_dns": {
        "steps": [["ipconfig", "/registerdns"]],
        "desc": "re-register the machine's DNS records",
        "reboot": False, "admin": True},
    "reset_winsock": {
        "steps": [["netsh", "winsock", "reset"]],
        "desc": "reset the Winsock catalog (fixes sockets corrupted by VPN/AV leftovers)",
        "reboot": True, "admin": True},
    "reset_tcpip": {
        "steps": [["netsh", "int", "ip", "reset"]],
        "desc": "reset the TCP/IP stack to defaults (last resort for broken connectivity)",
        "reboot": True, "admin": True},
    "restart_wifi": {
        "steps": [["netsh", "interface", "set", "interface", "Wi-Fi", "admin=disabled"],
                  ["netsh", "interface", "set", "interface", "Wi-Fi", "admin=enabled"]],
        "desc": "disable then re-enable the Wi-Fi adapter (fixes a stuck adapter)",
        "reboot": False, "admin": True},
}


def available_repairs() -> List[Dict[str, Any]]:
    """The repair menu (name + what it does + whether it needs admin/reboot).
    Read-only — listing is safe; RUNNING one is the gated action."""
    return [{"name": k, "desc": v["desc"], "needs_admin": v["admin"],
             "needs_reboot": v["reboot"]} for k, v in sorted(_REPAIRS_WIN.items())]


def run_repair(repair: str, timeout: int = 60) -> Dict[str, Any]:
    """Run ONE named repair from the allowlist. `repair` must be a known key —
    the mapped command sequence is fixed, so the model can never inject a
    command. This function performs a STATE CHANGE and is only reachable through
    the ESCALATE gate (system_repair tool)."""
    key = str(repair or "").strip().lower()
    if os.name != "nt":
        return {"ok": False, "repair": key, "error": "repair playbook is Windows-only for now"}
    spec = _REPAIRS_WIN.get(key)
    if not spec:
        return {"ok": False, "repair": key,
                "error": f"unknown repair; available: {', '.join(sorted(_REPAIRS_WIN))}"}
    outputs = []
    for argv in spec["steps"]:
        try:
            r = subprocess.run(argv, capture_output=True, text=True,
                               timeout=min(int(timeout), 120), encoding="utf-8", errors="replace")
            outputs.append({"cmd": " ".join(argv), "exit": r.returncode,
                            "out": (r.stdout or "").strip()[:800],
                            "err": (r.stderr or "").strip()[:300]})
        except Exception as e:
            outputs.append({"cmd": " ".join(argv), "error": f"{type(e).__name__}: {str(e)[:150]}"})
            break
    ok = all(o.get("exit", 1) == 0 for o in outputs if "exit" in o) and outputs
    note = spec["desc"]
    if spec["reboot"]:
        note += " · ⚠ a RESTART is required for this to take full effect"
    if spec["admin"] and any(("requires elevation" in str(o).lower() or "access is denied" in str(o).lower())
                             for o in outputs):
        note += " · ⚠ needs Administrator — run SkynetClaw as admin and retry"
    return {"ok": bool(ok), "repair": key, "steps": outputs, "note": note}


def available_checks() -> List[str]:
    return sorted(_CHECKS_WIN.keys())


def _is_readonly(argv: List[str]) -> bool:
    joined = " ".join(argv).lower()
    return not any(m in joined for m in _MUTATING)


def run_check(check: str, timeout: int = 40) -> Dict[str, Any]:
    """Run ONE read-only diagnostic by its allowlist key. Never accepts a raw
    command — `check` must be a known key, and the mapped argv is re-verified
    read-only before execution."""
    key = str(check or "").strip().lower()
    win = os.name == "nt"
    table = _CHECKS_WIN if win else {k: (v, "") for k, v in _CHECKS_POSIX.items()}
    if key not in table:
        return {"ok": False, "check": key,
                "error": f"unknown diagnostic; available: {', '.join(sorted(table.keys()))}"}
    argv = table[key][0]
    if not _is_readonly(argv):
        return {"ok": False, "check": key, "error": "refused: not a read-only diagnostic"}
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=min(int(timeout), 120),
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "").strip()
        # battery/report-style checks write a file and print little — point to it
        if key == "battery" and not out:
            out = f"battery report written to {argv[-1]}"
        return {"ok": r.returncode == 0, "check": key, "label": table[key][1] if win else key,
                "exit": r.returncode, "output": out[:6000],
                "stderr": (r.stderr or "").strip()[:500]}
    except FileNotFoundError:
        return {"ok": False, "check": key, "error": f"tool not present on this OS: {argv[0]}"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "check": key, "error": f"timed out after {timeout}s"}
    except Exception as e:
        return {"ok": False, "check": key, "error": f"{type(e).__name__}: {str(e)[:200]}"}


def diagnose(problem: str = "", checks: List[str] = None, timeout: int = 40) -> Dict[str, Any]:
    """Run a sweep. Either an explicit `checks` list (allowlist keys) or a
    free-text `problem` mapped to a playbook. Read-only throughout."""
    keys: List[str] = []
    if checks:
        keys = [str(c).strip().lower() for c in checks]
    else:
        p = (problem or "").lower()
        for kw, plays in _PLAYBOOKS.items():
            if kw in p:
                keys = plays
                break
        if not keys:
            keys = ["ip_config", "wifi_status"]   # sensible default sweep
    results = [run_check(k, timeout=timeout) for k in keys[:6]]
    ran = [r["check"] for r in results]
    ok_any = any(r.get("ok") for r in results)
    return {"ok": ok_any, "problem": problem, "ran": ran, "results": results,
            "hint": ("state-changing repair (reset/enable/install) needs shell_command "
                     "→ human approval; diagnosis above is read-only")}


if __name__ == "__main__":
    import sys, json
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("available:", available_checks())
    r = run_check("wifi_status")
    print("wifi_status ok:", r["ok"], "| first line:", (r.get("output", "") or r.get("error", ""))[:80])
    # safety: a mutating argv must be refused even if smuggled into the table
    assert not _is_readonly(["netsh", "int", "ip", "reset"]), "mutating verb must be caught"
    assert _is_readonly(["netsh", "wlan", "show", "interfaces"]), "read-only must pass"
    print("safety asserts OK — read-only passes, mutating refused")
