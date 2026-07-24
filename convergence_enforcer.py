#!/usr/bin/env python3
"""
Convergence Enforcer — บังคับให้ agent หยุดสำรวจและสังเคราะห์ผลงาน

กลไก: 
1. ตรวจสอบ artifact ครบถ้วนหรือไม่ (reports, dashboards, analysis)
2. ถ้าครบ → ส่งสัญญาณ converge และหยุด list_files วนลูป  
3. ถ้าไม่ครบ → บังคับสร้างผลงานชิ้นต่อไป

Usage: python convergence_enforcer.py [--check|--force]
"""

import os
from pathlib import Path
from datetime import datetime

# The repository root this file lives in — portable across machines.
# Override with SKYNETCLAW_WORKSPACE to point somewhere else.
WORKSPACE = os.environ.get("SKYNETCLAW_WORKSPACE") or str(Path(__file__).resolve().parent)


def scan_artifacts():
    """สแกน artifact ที่ agent สร้างแล้ว (reports, dashboards, analysis)"""
    artifacts = {
        "reports": [],
        "dashboards": [],
        "analyses": [],
        "strategies": []
    }

    for root, dirs, files in os.walk(WORKSPACE):
        # Skip system folders
        if any(root.endswith(x) for x in ["__pycache__", ".git"]):
            continue
            
        for f in files:
            path = Path(root) / f
            name_lower = f.lower()
            
            if "report" in name_lower or "audit" in name_lower:
                artifacts["reports"].append(str(path))
            elif any(x in name_lower for x in ["dashboard", "panel"]):
                artifacts["dashboards"].append(str(path))
            elif any(x in name_lower for x in ["analysis", "study", "review"]):
                artifacts["analyses"].append(str(path))
            elif any(x in name_lower for x in ["strategy", "plan", "scenario"]):
                artifacts["strategies"].append(str(path))

    return artifacts


def check_convergence(artifacts, min_threshold=3):
    """ตรวจสอบว่า artifact ครบตาม threshold หรือไม่"""
    total = sum(len(v) for v in artifacts.values())
    
    if total >= min_threshold:
        status = "CONVERGED"
        message = f"✅ Converged! มีผลงานสังเคราะห์ {total} ชิ้นแล้ว — หยุดสำรวจ, เริ่ม phase ใหม่"
    else:
        status = "EXPLORE" 
        missing_types = [k for k, v in artifacts.items() if not v]
        hint = f"ยังขาด artifact ประเภท: {', '.join(missing_types) or 'ทุกประเภท'}"
        message = f"⚠️ ยังไม่ converge ({total}/{min_threshold}) — ต้องสร้างผลงานเพิ่ม\n   → {hint}"

    return status, total, message


def main():
    print("=" * 60)
    print("CONVERGENCE ENFORGER v1.0")
    print(f"Workspace: {WORKSPACE}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    artifacts = scan_artifacts()
    
    status, total, message = check_convergence(artifacts)
    
    print(message)
    print("\n--- Artifact Inventory ---")
    for category, items in artifacts.items():
        if items:
            print(f"📄 {category.upper()} ({len(items)}):")
            for item in items[:5]:  # Show first 5 only
                rel = Path(item).relative_to(WORKSPACE)
                print(f"   • {rel}")

    return status == "CONVERGED", artifacts


if __name__ == "__main__":
    converged, _ = main()
    exit(0 if converged else 1)
