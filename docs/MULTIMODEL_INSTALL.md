# SkynetClaw Multi-Model — Install Guide

ระบบหลาย-โมเดล สลับอัตโนมัติตาม intent + UI ให้ผู้ใช้ตั้งค่าเอง

## 1. ไฟล์ที่ถูกสร้างไว้แล้ว

| ไฟล์ | หน้าที่ |
|---|---|
| `backend/skynetclaw_router.py` | Router logic + endpoints (intent classifier, role-based model selection) |
| `multimodel_panel.js` | Frontend module (Setup modal, sentinel options, live indicator) |
| `MULTIMODEL_INSTALL.md` | คู่มือนี้ |

ระบบจะสร้าง runtime files เหล่านี้ตอนรันครั้งแรก:
- `backend/router_config.json` — roster ของผู้ใช้
- `backend/router_audit.jsonl` — log การ routing ทุกครั้ง

## 2. แก้ `backend/main.py` (3 จุด)

**จุดที่ 1 — บนสุดของไฟล์ (หลัง imports):**
```python
from skynetclaw_router import register_router, resolve_model
```

**จุดที่ 2 — หลังบรรทัด `app = FastAPI(...)` ประมาณบรรทัด 88:**
```python
register_router(app)
```

**จุดที่ 3 — ใน `/api/chat` (ราว ๆ บรรทัด 2222) เปลี่ยน:**
```python
# เดิม:
payload={"model":req.model,"messages":messages,"stream":True,...}

# เป็น:
_last_user = next((m["content"] for m in reversed(messages) if m.get("role")=="user"), "")
_actual_model = resolve_model(req.model, _last_user)
payload={"model":_actual_model,"messages":messages,"stream":True,...}
```

**(ทางเลือก) จุดที่ 4 — ใน `/api/agent/run` (ราว ๆ บรรทัด 2490) เปลี่ยน:**
```python
# เดิม:
model = req.model or get_active_model() or ""

# เป็น:
model = resolve_model(req.model or get_active_model() or "", req.task)
```

## 3. แก้ `index.html` (1 บรรทัด)

ก่อน `</body>` ใส่:
```html
<script src="multimodel_panel.js" defer></script>
```

## 4. รีสตาร์ท + ใช้งาน

```cmd
restart_backend.bat
```

แล้วเปิด `index.html` — จะเห็น:
- ปุ่ม **🎛️ Setup** ข้าง model dropdown
- ใน dropdown มีตัวเลือกใหม่ที่หัวลิสต์: `@AUTO`, `@workhorse`, `@chat`, `@specialist`
- กดปุ่ม Setup → เลือกโมเดลให้แต่ละ role (เช่น nemotron3:33b เป็น workhorse, qwen3.5:9b เป็น chat)
- ทดสอบในช่องล่าง: พิมพ์ "รัน python script" จะเห็นว่า router เลือก workhorse
- กลับมาเลือก `🎯 @AUTO` ใน dropdown → ทุกข้อความถัดไป router จะตัดสินใจเอง
- บนแต่ละข้อความตอบของ AI จะมี chip สีแสดงว่าใช้ model ไหน

## 5. การทำงาน — flow

```
user พิมพ์ข้อความ
  → frontend ส่ง /api/chat ด้วย model = "@auto"
  → resolve_model("@auto", user_text) ใน main.py
  → classify_intent(user_text) → "workhorse" / "chat" / "specialist"
  → roster.roles[role].model → "nemotron3:33b"
  → Ollama ใช้ "nemotron3:33b" จริง
  → response กลับ + entry บันทึกใน router_audit.jsonl
  → frontend poll /api/router/audit → ติด chip บน bubble
```

## 6. Sentinel models ที่ใช้ได้

| ค่าใน dropdown | ผลลัพธ์ |
|---|---|
| `@auto` | classify_intent ตัดสินใจเอง |
| `@workhorse` | บังคับใช้ workhorse model |
| `@chat` | บังคับใช้ chat model |
| `@specialist` | บังคับใช้ specialist model |
| `@code` | alias ของ @specialist |
| ชื่อโมเดลจริง เช่น `nemotron3:33b` | ใช้ตามที่ระบุ (พฤติกรรมเดิม) |

## 7. เพิ่ม/แก้ routing rules

แก้ `router_config.json` ตรง `rules`:
```json
{
  "rules": [
    {"pattern": "\\b(วิเคราะห์ตลาด|trade|signal)\\b", "role": "specialist"},
    ...
  ]
}
```
หรือใช้ endpoint `PUT /api/router/config` ส่ง JSON merge-patch

## 8. ทดสอบ router แบบ standalone (ไม่ต้องเปิด UI)

```cmd
cd backend
python skynetclaw_router.py
```

จะเห็น self-test รัน 7 cases และโชว์ resolve_model + preview_routing

## 9. ข้อควรระวัง

- Sentinel `@auto` จะ **ไม่** ถูกเซฟลง `settings.json` เป็น default model — ป้องกัน Telegram bot สับสน
- `router_audit.jsonl` ขยายเร็วถ้าใช้บ่อย — ลบเองเป็นระยะหรือเขียน rotation ภายหลัง
- ถ้า role ไม่ได้ตั้ง model ไว้ → router จะ fallback ไป workhorse → specialist → chat ตามลำดับ
- Hot-swap dropdown ใช้ผลทันทีรอบถัดไป — ประวัติแชทเดิมคงไว้ (frontend `chatHistory` array ไม่ถูกล้าง)

## 10. Verification checklist

หลังติดตั้ง รันคำสั่งนี้เพื่อตรวจ:
```cmd
curl -X POST http://localhost:8766/api/router/preview -H "Content-Type: application/json" -d "{\"text\":\"รัน python สร้าง bot\"}"
```
ควรได้กลับมา:
```json
{"role":"workhorse","model":"nemotron3:33b","matched_pattern":"...","router_enabled":true}
```
