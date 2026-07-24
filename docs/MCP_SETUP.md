# SkynetClaw เป็น MCP Server — วิธีติดตั้ง

เปิดให้ Claude Desktop / Claude Code (หรือ MCP client อื่น) เรียกใช้ tools ของ SkynetClaw ได้
(อ่าน/เขียนไฟล์, grep, shell, python, dev server, Obsidian vault) — ทุก call ผ่าน GPS-2 gate เหมือนเดิม

## 1. ติดตั้ง dependency (ครั้งเดียว)

```
pip install "mcp[cli]" httpx
```

## 2. Backend ต้องรันอยู่

```
cd <YOUR_WORKSPACE>\backend
python main.py
```

## 3a. Claude Desktop

แก้ `%APPDATA%\Claude\claude_desktop_config.json` เพิ่ม:

```json
{
  "mcpServers": {
    "skynetclaw": {
      "command": "python",
      "args": ["<YOUR_WORKSPACE>\\backend\\mcp_server.py"]
    }
  }
}
```

แล้ว restart Claude Desktop → จะเห็น tools ชื่อ `skynetclaw_*`

## 3b. Claude Code

```
claude mcp add skynetclaw -- python <YOUR_WORKSPACE>\backend\mcp_server.py
```

## ทดสอบด้วย MCP Inspector (ไม่บังคับ)

```
npx @modelcontextprotocol/inspector python <YOUR_WORKSPACE>\backend\mcp_server.py
```

## Governance

- ทุก tool call วิ่งผ่าน `POST /api/tools/execute` → GPS-2 gate (deny-by-default)
- Tools ปลอดภัย (read/grep/list/write ใน workspace) ใช้ได้ทันที
- Tools อันตราย (`shell`, `run_python`, `dev_server`) ต้องมี standing approval —
  อนุมัติครั้งเดียวผ่าน UI SkynetClaw (กด "approve-tool" ตอนระบบถาม) หรือย้ายชื่อ tool
  ไป `allow` ใน `backend/governance_config.json` แล้ว restart backend
- เช็คสิทธิ์ปัจจุบัน: เรียก tool `skynetclaw_governance_status` จากฝั่ง Claude ได้เลย
- ถ้า backend อยู่เครื่อง/พอร์ตอื่น: ตั้ง env `SKYNETCLAW_URL` ให้ MCP server
