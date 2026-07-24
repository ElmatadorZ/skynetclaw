/* ============================================================================
 * SkynetClaw — Multi-Model Panel (frontend module)
 * ============================================================================
 * Drop-in JS that adds:
 *   1) A "🎛️ Setup" button next to the existing #model-sel dropdown
 *   2) Sentinel options at the top of the dropdown:
 *        @AUTO  / @workhorse / @chat / @specialist
 *      → backend skynetclaw_router.py resolves these to real Ollama models
 *   3) A modal where the user assigns 2-3 real models to roles
 *   4) Live indicator chip on each AI response showing which model handled it
 *   5) Hot-swap: changing the dropdown takes effect on the very next message
 *      without losing chatHistory
 *
 * Install (one line in index.html, just before </body>):
 *     <script src="multimodel_panel.js" defer></script>
 *
 * Requires:
 *   - Backend has skynetclaw_router.py registered (register_router(app))
 *   - main.py /api/chat + /api/agent/run call resolve_model(req.model, ...)
 *
 * ============================================================================
 */
(function () {
  if (window.__SKYNETCLAW_MULTIMODEL__) return; // idempotent
  window.__SKYNETCLAW_MULTIMODEL__ = true;

  const API = (window.API && typeof window.API === "string") ? window.API : "http://localhost:8766";

  // ────────────────────────────────────────────────────────────────────────
  // Styles (scoped, dark-theme friendly, falls back gracefully)
  // ────────────────────────────────────────────────────────────────────────
  const css = `
    /* Trigger button next to model dropdown */
    .mm-btn {
      display: inline-flex; align-items: center; gap: 6px;
      background: rgba(108,95,240,.08);
      border: 1px solid rgba(108,95,240,.32);
      color: #cdd8ea; padding: 5px 11px; border-radius: 7px;
      font-size: 11px; font-weight: 600; cursor: pointer; margin-left: 8px;
      transition: all .15s; letter-spacing: .03em;
      font-family: inherit;
    }
    .mm-btn:hover {
      background: rgba(108,95,240,.18);
      border-color: rgba(155,143,255,.6);
      color: #fff;
      box-shadow: 0 4px 14px rgba(108,95,240,.25);
    }
    .mm-btn .mm-glyph { font-size: 13px; line-height: 1; }

    /* Modal overlay */
    .mm-overlay {
      position: fixed; inset: 0; background: rgba(7,9,15,.78);
      display: none; align-items: center; justify-content: center;
      z-index: 99999; backdrop-filter: blur(8px);
      animation: mm-fadeIn .18s ease;
    }
    .mm-overlay.open { display: flex; }
    @keyframes mm-fadeIn { from { opacity: 0 } to { opacity: 1 } }
    @keyframes mm-slideUp { from { transform: translateY(12px); opacity: 0 } to { transform: translateY(0); opacity: 1 } }

    .mm-modal {
      background: linear-gradient(180deg, #0f1320 0%, #0a0d18 100%);
      color: #cdd8ea;
      border: 1px solid #223050;
      border-radius: 14px; width: min(620px, 94vw);
      max-height: 92vh; overflow-y: auto;
      padding: 0; box-shadow: 0 24px 80px rgba(0,0,0,.65), 0 0 0 1px rgba(108,95,240,.08);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Sarabun", sans-serif;
      animation: mm-slideUp .22s ease;
    }

    /* Modal header */
    .mm-head {
      padding: 20px 24px 14px;
      border-bottom: 1px solid #1b2740;
      background: linear-gradient(180deg, rgba(108,95,240,.06) 0%, transparent 100%);
    }
    .mm-title { display: flex; align-items: center; gap: 10px; }
    .mm-title h2 {
      margin: 0; font-size: 15px; font-weight: 700;
      letter-spacing: .03em; color: #e8ecf5;
      flex: 1;
    }
    .mm-title .mm-version {
      font-size: 9px; padding: 2px 7px; border-radius: 3px;
      background: rgba(108,95,240,.18); color: #9b8fff;
      letter-spacing: .08em; font-weight: 700;
    }
    .mm-sub { color: #6a84a8; font-size: 11.5px; line-height: 1.5; margin-top: 6px; }
    .mm-toggle {
      display: inline-flex; align-items: center; gap: 6px;
      font-size: 10px; color: #6a84a8; cursor: pointer;
      letter-spacing: .04em; text-transform: uppercase; font-weight: 600;
    }
    .mm-toggle input { accent-color: #6c5ff0; cursor: pointer; }

    /* Body */
    .mm-body { padding: 14px 24px 18px; }

    /* Role row — one card per role with left accent bar */
    .mm-row {
      display: grid;
      grid-template-columns: 130px 1fr;
      gap: 14px; align-items: center;
      padding: 14px 14px 14px 16px;
      border-radius: 8px;
      border: 1px solid #1b2740;
      background: rgba(13,16,24,.5);
      margin-bottom: 8px;
      transition: all .15s;
      position: relative; overflow: hidden;
    }
    .mm-row:hover { border-color: #2c3a5a; background: rgba(17,23,34,.7); }
    .mm-row::before {
      content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
    }
    .mm-row.exec::before      { background: linear-gradient(180deg, #ff6b35, #c84617); }
    .mm-row.ambient::before   { background: linear-gradient(180deg, #00c8ff, #0078a8); }
    .mm-row.precision::before { background: linear-gradient(180deg, #9b8fff, #6c5ff0); }

    .mm-role-cell { display: flex; flex-direction: column; gap: 2px; }
    .mm-role-name {
      font-weight: 800; font-size: 12px; letter-spacing: .08em;
      display: flex; align-items: center; gap: 6px;
    }
    .mm-glyph-big {
      font-size: 14px; line-height: 1;
    }
    .mm-row.exec      .mm-role-name { color: #ff8a5c; }
    .mm-row.ambient   .mm-role-name { color: #5cd6ff; }
    .mm-row.precision .mm-role-name { color: #9b8fff; }
    .mm-role-tag {
      font-size: 9px; color: #3d5068; letter-spacing: .06em;
      text-transform: uppercase; font-weight: 600;
    }

    .mm-row select {
      background: #0a0d18; color: #cdd8ea;
      border: 1px solid #223050;
      padding: 8px 10px; border-radius: 6px; width: 100%;
      font-size: 12px; font-family: inherit; cursor: pointer;
      transition: border-color .12s;
    }
    .mm-row select:hover  { border-color: #2c3a5a; }
    .mm-row select:focus  { outline: none; border-color: #6c5ff0; box-shadow: 0 0 0 2px rgba(108,95,240,.18); }
    .mm-row select.unset  { color: #3d5068; font-style: italic; }

    .mm-desc { font-size: 10.5px; color: #6a84a8; margin-top: 6px; line-height: 1.4; }

    /* Test sandbox */
    .mm-test {
      margin: 16px 0 0; padding: 16px 16px 14px;
      border: 1px solid #1b2740; border-radius: 8px;
      background: rgba(13,16,24,.5);
    }
    .mm-test-head {
      display: flex; align-items: center; gap: 8px; margin-bottom: 8px;
    }
    .mm-test-head .mm-test-icon {
      width: 22px; height: 22px; border-radius: 5px;
      background: rgba(0,229,158,.12); color: #00e59e;
      display: inline-flex; align-items: center; justify-content: center;
      font-size: 12px;
    }
    .mm-test-head label {
      font-size: 10px; color: #6a84a8; letter-spacing: .06em;
      text-transform: uppercase; font-weight: 700;
    }
    .mm-test input {
      width: 100%; box-sizing: border-box;
      background: #0a0d18; color: #cdd8ea;
      border: 1px solid #223050;
      padding: 9px 12px; border-radius: 6px; font-size: 12px;
      font-family: inherit; transition: border-color .12s;
    }
    .mm-test input:focus { outline: none; border-color: #6c5ff0; box-shadow: 0 0 0 2px rgba(108,95,240,.18); }
    .mm-result {
      margin-top: 10px; padding: 10px 12px;
      background: rgba(108,95,240,.08);
      border: 1px solid rgba(108,95,240,.25);
      border-radius: 6px; font-size: 11.5px; line-height: 1.55;
      color: #cdd8ea;
    }
    .mm-result strong { color: #c4b5fd; font-weight: 700; }
    .mm-result code { font-family: "SF Mono", Consolas, monospace; font-size: 10.5px; color: #6a84a8; }

    /* Action bar */
    .mm-actions {
      display: flex; gap: 10px; justify-content: flex-end;
      padding: 14px 24px 18px;
      border-top: 1px solid #1b2740;
      background: rgba(7,9,15,.4);
      border-radius: 0 0 13px 13px;
    }
    .mm-actions button {
      padding: 9px 18px; border-radius: 7px; cursor: pointer;
      font-size: 12px; font-weight: 700; border: none; letter-spacing: .03em;
      font-family: inherit; transition: all .12s;
    }
    .mm-actions .mm-cancel {
      background: transparent; color: #6a84a8;
      border: 1px solid #223050;
    }
    .mm-actions .mm-cancel:hover { color: #cdd8ea; border-color: #2c3a5a; }
    .mm-actions .mm-save {
      background: linear-gradient(135deg, #6c5ff0 0%, #9b8fff 100%);
      color: #fff;
      box-shadow: 0 4px 14px rgba(108,95,240,.35);
    }
    .mm-actions .mm-save:hover {
      transform: translateY(-1px);
      box-shadow: 0 8px 22px rgba(108,95,240,.5);
    }

    /* Live indicator chip on AI response bubbles */
    .mm-chip {
      display: inline-flex; align-items: center; gap: 4px;
      background: rgba(108,95,240,.12);
      border: 1px solid rgba(108,95,240,.32);
      color: #9b8fff; font-size: 9.5px;
      padding: 2px 8px; border-radius: 10px;
      margin-left: 6px; vertical-align: middle;
      letter-spacing: .06em; font-weight: 700; text-transform: uppercase;
      font-family: -apple-system, BlinkMacSystemFont, "SF Mono", Consolas, monospace;
    }
    .mm-chip.exec      { background: rgba(255,107,53,.10); border-color: rgba(255,107,53,.32); color: #ff8a5c; }
    .mm-chip.ambient   { background: rgba(0,200,255,.10); border-color: rgba(0,200,255,.32); color: #5cd6ff; }
    .mm-chip.precision { background: rgba(155,143,255,.12); border-color: rgba(155,143,255,.34); color: #9b8fff; }

    /* Result preview chips inside test box */
    .mm-mini-chip {
      display: inline-block; padding: 1px 7px; border-radius: 8px;
      font-size: 9px; font-weight: 700; letter-spacing: .07em;
      text-transform: uppercase; vertical-align: middle;
    }
    .mm-mini-chip.exec      { background: rgba(255,107,53,.14); color: #ff8a5c; }
    .mm-mini-chip.ambient   { background: rgba(0,200,255,.14); color: #5cd6ff; }
    .mm-mini-chip.precision { background: rgba(155,143,255,.14); color: #9b8fff; }

    /* ═══════════════════════════════════════════════════════════════════
       Enhanced Thinking / Processing indicator
       Apply to EVERY .thinking — don't wait for JS to set data attribute,
       so the size upgrade is visible even if MutationObserver loses a race.
       Single-card design, no separate panels, no runner bar.
       ═══════════════════════════════════════════════════════════════════ */
    .thinking {
      min-width: 380px !important;
      max-width: 560px !important;
      padding: 16px 20px 16px 16px !important;
      gap: 16px !important;
    }
    /* Slightly larger orb for better proportion with the bigger card */
    .thinking .orb-wrap {
      width: 50px !important; height: 50px !important;
    }
    .thinking .orb-r1 { width: 25px !important; height: 25px !important; margin: -12.5px 0 0 -12.5px !important; }
    .thinking .orb-r2 { width: 38px !important; height: 38px !important; margin: -19px   0 0 -19px   !important; }
    .thinking .orb-r3 { width: 50px !important; height: 50px !important; margin: -25px   0 0 -25px   !important; }
    .thinking .thinking-label { font-size: 13.5px !important; }
    .thinking .thinking-text  { gap: 6px !important; flex: 1 1 auto; min-width: 0; }

    /* Subtitle becomes a flexible row with role label · model name */
    .thinking .thinking-sub {
      display: flex !important;
      align-items: center !important;
      gap: 7px !important;
      font-size: 10.5px !important;
      letter-spacing: .04em !important;
      text-transform: none !important;
      flex-wrap: nowrap;
      overflow: hidden;
    }

    .mm-tm-label {
      font-weight: 700;
      letter-spacing: .1em;
      text-transform: uppercase;
      color: #6a84a8;
      display: inline-flex; align-items: center; gap: 5px;
      flex-shrink: 0;
      font-size: 10px;
      transition: color .25s;
    }
    .mm-tm-label.exec      { color: #ff8a5c; }
    .mm-tm-label.ambient   { color: #5cd6ff; }
    .mm-tm-label.precision { color: #9b8fff; }
    .mm-tm-pulse {
      display: inline-block; width: 6px; height: 6px; border-radius: 50%;
      background: currentColor;
      animation: mm-pulseDot 1.2s ease-in-out infinite;
      box-shadow: 0 0 6px currentColor;
      flex-shrink: 0;
    }
    @keyframes mm-pulseDot {
      0%,100% { opacity: .4; transform: scale(.85); }
      50%     { opacity: 1;  transform: scale(1.2);  }
    }
    .mm-tm-divider { color: #3d5068; opacity: .55; flex-shrink: 0; }
    .mm-tm-model {
      color: #cdd8ea;
      font-family: "SF Mono", "Cascadia Mono", Consolas, monospace;
      letter-spacing: .02em;
      font-size: 10.5px;
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
      flex: 1 1 auto; min-width: 0;
      transition: color .3s;
    }
    .mm-tm-model.mm-resolved {
      color: #9b8fff;
      animation: mm-resolveIn .42s cubic-bezier(.4,0,.2,1);
    }
    @keyframes mm-resolveIn {
      from { opacity: .25; transform: translateX(6px); }
      to   { opacity: 1;   transform: translateX(0);   }
    }
  `;

  function injectStyle() {
    if (document.getElementById("mm-style")) return;
    const s = document.createElement("style");
    s.id = "mm-style";
    s.textContent = css;
    document.head.appendChild(s);
  }

  // ────────────────────────────────────────────────────────────────────────
  // State + helpers
  // ────────────────────────────────────────────────────────────────────────
  let modelList = [];
  let roster = null;

  async function fetchModels() {
    try {
      const r = await fetch(API + "/api/models", { signal: AbortSignal.timeout(5000) });
      const d = await r.json();
      modelList = d.models || [];
      return modelList;
    } catch { return []; }
  }
  async function fetchRoster() {
    try {
      const r = await fetch(API + "/api/router/config");
      roster = await r.json();
      return roster;
    } catch { return null; }
  }
  async function saveRoster(patch) {
    const r = await fetch(API + "/api/router/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    return r.json();
  }
  async function previewRoute(text) {
    try {
      const r = await fetch(API + "/api/router/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      return r.json();
    } catch { return null; }
  }
  async function fetchAuditTail(limit = 6) {
    try {
      const r = await fetch(API + "/api/router/audit?limit=" + limit);
      const d = await r.json();
      return d.entries || [];
    } catch { return []; }
  }

  // ────────────────────────────────────────────────────────────────────────
  // Inject sentinel options + setup button into existing dropdown
  // ────────────────────────────────────────────────────────────────────────
  // Canonical UI names — backend still uses workhorse/chat/specialist as keys
  const SENTINELS = [
    { value: "@auto",      label: "◎  AUTO  ·  router decides" },
    { value: "@executor",  label: "▲  EXECUTOR  ·  heavy compute" },
    { value: "@ambient",   label: "○  AMBIENT  ·  light reasoning" },
    { value: "@precision", label: "◆  PRECISION  ·  domain expert" },
  ];

  // Backend role key  ←→  UI display
  const ROLE_DISPLAY = {
    workhorse:  { name: "EXECUTOR",  glyph: "▲", color: "exec",      desc: "งานหนัก · รันโค้ด · agent loop · สร้างไฟล์ · วิเคราะห์ลึก" },
    chat:       { name: "AMBIENT",   glyph: "○", color: "ambient",   desc: "ถาม-ตอบสั้น · สนทนา · สรุปเร็ว · ตอบทักทาย" },
    specialist: { name: "PRECISION", glyph: "◆", color: "precision", desc: "เฉพาะทาง · code review · finance · domain reasoning" },
  };
  // Reverse map: backend may emit "workhorse (auto-fallback)" — we strip suffix and look up
  const roleClass = (roleKey) => {
    const k = (roleKey || "").split(" ")[0].trim();
    return (ROLE_DISPLAY[k] && ROLE_DISPLAY[k].color) || "exec";
  };
  const roleName = (roleKey) => {
    const k = (roleKey || "").split(" ")[0].trim();
    return (ROLE_DISPLAY[k] && ROLE_DISPLAY[k].name) || k.toUpperCase();
  };

  function injectSentinels(sel) {
    if (!sel) return;
    // Remove old sentinels first to avoid duplicates after loadModels() refresh
    [...sel.querySelectorAll("option[data-mm-sentinel]")].forEach(o => o.remove());
    SENTINELS.slice().reverse().forEach(s => {
      const opt = document.createElement("option");
      opt.value = s.value;
      opt.textContent = s.label;
      opt.setAttribute("data-mm-sentinel", "1");
      sel.insertBefore(opt, sel.firstChild);
    });
  }

  // ────────────────────────────────────────────────────────────────────────
  // Robust sentinel persistence — 3 defensive layers so sentinels never
  // vanish when index.html's loadModels() rewrites <select>.innerHTML.
  // ────────────────────────────────────────────────────────────────────────
  let _mmObserverInstalled = false;
  function installRobustSentinels(sel) {
    if (!sel) return;

    // Layer 1: wrap window.loadModels — re-inject right after every refresh
    if (typeof window.loadModels === "function" && !window.__mmLoadModelsWrapped) {
      const orig = window.loadModels;
      window.loadModels = async function () {
        let res;
        try { res = await orig.apply(this, arguments); }
        finally {
          const s = document.getElementById("model-sel");
          if (s) injectSentinels(s);
        }
        return res;
      };
      window.__mmLoadModelsWrapped = true;
    }

    // Layer 2: MutationObserver — if sentinel count drops below expected, re-inject
    if (!_mmObserverInstalled) {
      const obs = new MutationObserver(() => {
        try {
          const have = sel.querySelectorAll("option[data-mm-sentinel]").length;
          if (have < SENTINELS.length) {
            // Defer to next tick to avoid recursive observation while we mutate
            setTimeout(() => injectSentinels(sel), 0);
          }
        } catch {}
      });
      obs.observe(sel, { childList: true });
      _mmObserverInstalled = true;
    }

    // Layer 3: when user opens the dropdown, sync sentinels right before
    sel.addEventListener("mousedown", () => injectSentinels(sel), true);
    sel.addEventListener("focus",     () => injectSentinels(sel), true);
    sel.addEventListener("click",     () => injectSentinels(sel), true);
  }

  function injectSetupButton(sel) {
    if (!sel || sel.parentElement.querySelector(".mm-btn")) return;
    const btn = document.createElement("button");
    btn.className = "mm-btn";
    btn.title = "Multi-Model Routing — assign Executor / Ambient / Precision";
    btn.innerHTML = `<span class="mm-glyph">◎</span><span>ROUTING</span>`;
    btn.onclick = openModal;
    // Insert AFTER the dropdown
    sel.parentElement.insertBefore(btn, sel.nextSibling);
  }

  // ────────────────────────────────────────────────────────────────────────
  // Modal
  // ────────────────────────────────────────────────────────────────────────
  let overlay = null;
  function buildModal() {
    if (overlay) return overlay;
    overlay = document.createElement("div");
    overlay.className = "mm-overlay";
    overlay.innerHTML = `
      <div class="mm-modal" onclick="event.stopPropagation()">
        <div class="mm-head">
          <div class="mm-title">
            <h2>Multi-Model Routing</h2>
            <span class="mm-version">v1.0</span>
            <label class="mm-toggle">
              <input type="checkbox" id="mm-enabled"> Active
            </label>
          </div>
          <div class="mm-sub">เลือก model ให้ 3 บทบาท. พิมพ์ <strong style="color:#9b8fff">@AUTO</strong> ในแชท router จะตัดสินใจอัตโนมัติตาม intent ของข้อความ</div>
        </div>

        <div class="mm-body">
          <div id="mm-roles"></div>

          <div class="mm-test">
            <div class="mm-test-head">
              <span class="mm-test-icon">▶</span>
              <label>Live Preview · ทดสอบ classify</label>
            </div>
            <input id="mm-test-input" placeholder="เช่น: รัน python script สร้าง telegram bot">
            <div class="mm-result" id="mm-test-result" style="display:none"></div>
          </div>
        </div>

        <div class="mm-actions">
          <button class="mm-cancel" onclick="window.__mmClose()">ยกเลิก</button>
          <button class="mm-save"   onclick="window.__mmSave()">บันทึก & ปิด</button>
        </div>
      </div>
    `;
    overlay.onclick = closeModal;
    document.body.appendChild(overlay);
    return overlay;
  }

  function rolesHTML() {
    // Backend keys remain workhorse/chat/specialist for compat;
    // UI displays EXECUTOR / AMBIENT / PRECISION
    const order = ["workhorse", "chat", "specialist"];

    const buildOptions = (selected) => {
      const items = [`<option value="" ${!selected ? 'selected' : ''}>— ไม่ตั้ง —</option>`]
        .concat(modelList.map(m => {
          const sel = m === selected ? " selected" : "";
          return `<option value="${escapeAttr(m)}"${sel}>${escapeHtml(m)}</option>`;
        }));
      return items.join("");
    };

    return order.map(key => {
      const cfg = (roster && roster.roles && roster.roles[key]) || {};
      const ui = ROLE_DISPLAY[key];
      const unsetClass = cfg.model ? "" : " unset";
      return `
        <div class="mm-row ${escapeAttr(ui.color)}">
          <div class="mm-role-cell">
            <div class="mm-role-name"><span class="mm-glyph-big">${ui.glyph}</span>${ui.name}</div>
            <div class="mm-role-tag">role · ${escapeHtml(key)}</div>
          </div>
          <div>
            <select data-mm-role="${key}" data-mm-field="model" class="${unsetClass}">${buildOptions(cfg.model || "")}</select>
            <div class="mm-desc">${escapeHtml(ui.desc)}</div>
          </div>
        </div>
      `;
    }).join("");
  }

  async function openModal() {
    injectStyle();
    buildModal();
    await Promise.all([fetchModels(), fetchRoster()]);
    document.getElementById("mm-enabled").checked = !!(roster && roster.enabled !== false);
    document.getElementById("mm-roles").innerHTML = rolesHTML();
    overlay.classList.add("open");

    // Wire test input
    const ti = document.getElementById("mm-test-input");
    const tr = document.getElementById("mm-test-result");
    let timer = null;
    ti.oninput = () => {
      clearTimeout(timer);
      timer = setTimeout(async () => {
        const text = ti.value.trim();
        if (!text) { tr.style.display = "none"; return; }
        // Use unsaved selections from the modal
        const live = readModalRoster();
        await saveRoster(live);  // commit before preview so backend sees latest
        const p = await previewRoute(text);
        if (!p) { tr.style.display = "none"; return; }
        tr.style.display = "block";
        const cls  = roleClass(p.role);
        const name = roleName(p.role);
        tr.innerHTML = `
          → routed to <span class="mm-mini-chip ${escapeAttr(cls)}">${escapeHtml(name)}</span>
          using <strong>${escapeHtml(p.model || "(model not set)")}</strong>
          ${p.matched_pattern ? `<br/><span style="color:#3d5068">matched rule: <code>${escapeHtml(p.matched_pattern)}</code></span>` : `<br/><span style="color:#3d5068">fallback by length heuristic</span>`}
        `;
      }, 280);
    };
  }

  function closeModal(e) {
    if (e && e.target !== overlay) return; // only close on backdrop click
    if (overlay) overlay.classList.remove("open");
  }
  window.__mmClose = closeModal;

  function readModalRoster() {
    const enabled = document.getElementById("mm-enabled").checked;
    const roles = {};
    document.querySelectorAll("[data-mm-role]").forEach(el => {
      const role = el.getAttribute("data-mm-role");
      const field = el.getAttribute("data-mm-field");
      roles[role] = roles[role] || {};
      roles[role][field] = el.value;
    });
    return { enabled, roles };
  }

  async function saveAndClose() {
    const patch = readModalRoster();
    await saveRoster(patch);
    showMmToast(`✓ ROSTER UPDATED · <span style="color:#5cd6ff">router active</span>`);
    closeModal({ target: overlay });
  }
  window.__mmSave = saveAndClose;

  function showMmToast(msg) {
    const t = document.createElement("div");
    t.style.cssText = `position:fixed;bottom:80px;left:50%;transform:translateX(-50%);
      background:linear-gradient(135deg,#0f1320,#0a0d18);
      border:1px solid rgba(108,95,240,.45);color:#9b8fff;
      padding:9px 20px;border-radius:22px;font-size:11.5px;z-index:99999;
      letter-spacing:.04em;font-weight:600;
      box-shadow:0 10px 30px rgba(0,0,0,.5),0 0 20px rgba(108,95,240,.15);
      transition:opacity .4s`;
    t.innerHTML = msg;
    document.body.appendChild(t);
    setTimeout(() => { t.style.opacity = "0"; setTimeout(() => t.remove(), 400); }, 2400);
  }

  // ────────────────────────────────────────────────────────────────────────
  // Live indicator — tag each AI bubble with the model that handled it
  // Strategy: poll /api/router/audit periodically and append a chip to the
  // most recent .bubble.ai (or .ai-bubble / .msg-ai — fall back to last AI msg)
  // ────────────────────────────────────────────────────────────────────────
  let lastAuditHash = "";
  async function pollAudit() {
    try {
      const entries = await fetchAuditTail(3);
      if (!entries.length) return;
      const latest = entries[entries.length - 1];
      const hash = latest.ts + "|" + (latest.chosen_model || "");
      if (hash === lastAuditHash) return;
      lastAuditHash = hash;
      tagLastAiBubble(latest.chosen_role, latest.chosen_model);
    } catch {}
  }
  function tagLastAiBubble(role, model) {
    if (!model) return;
    // Try common selectors used in SkynetClaw's index.html
    const candidates = document.querySelectorAll(
      ".bubble.ai, .msg-ai, .ai-bubble, .bbl-ai, .bbl.ai, .msg.assistant, [data-role='assistant']"
    );
    if (!candidates.length) return;
    const last = candidates[candidates.length - 1];
    if (last.querySelector(".mm-chip")) return; // already tagged
    const chip = document.createElement("span");
    const cls  = roleClass(role);
    const name = roleName(role);
    chip.className = "mm-chip " + cls;
    const shortModel = model.length > 22 ? model.slice(0, 20) + "…" : model;
    chip.innerHTML = `${name} · <span style="opacity:.7">${escapeHtml(shortModel)}</span>`;
    chip.title = `role: ${role}\nmodel: ${model}`;
    last.appendChild(chip);
  }

  // ────────────────────────────────────────────────────────────────────────
  // Hot-swap glue — patch the existing onModelChange so sentinels persist
  // and dropdown change takes effect IMMEDIATELY without losing chatHistory
  // ────────────────────────────────────────────────────────────────────────
  function patchModelChangeHandler() {
    const sel = document.getElementById("model-sel");
    if (!sel) return;
    // Remove other listeners' "onchange" string handler isn't ours to touch;
    // instead add a capture-phase listener that runs first, sets currentModel,
    // and signals success. Existing onModelChange() still runs after.
    sel.addEventListener("change", () => {
      try {
        if (typeof window.currentModel !== "undefined") {
          window.currentModel = sel.value;
        }
        // Don't persist sentinels to /api/settings (they aren't real models for Telegram bot)
        if (sel.value && sel.value.startsWith("@")) {
          const mode = sel.value.toUpperCase().replace("@", "");
          showMmToast(`◎ ROUTING <strong style="color:#cdd8ea">${escapeHtml(mode)}</strong> · router selects model per message`);
        } else if (sel.value) {
          showMmToast(`⇄ MODEL <strong style="color:#cdd8ea">${escapeHtml(sel.value)}</strong>`);
        }
      } catch (e) { console.warn("[multimodel] hot-swap glue:", e); }
    }, true); // capture
  }

  // ────────────────────────────────────────────────────────────────────────
  // Enhanced "Processing..." indicator
  //   - Detects when index.html creates a `.thinking` bubble
  //   - Adds a model badge on the right (role + model name)
  //   - Adds a progress runner along the bottom edge
  //   - When @AUTO/@executor/etc was selected, polls /api/router/audit
  //     to update the badge from "ROUTING…" to the actual resolved model
  // ────────────────────────────────────────────────────────────────────────
  let _lastSeenAuditTs = 0;

  function setupThinkingEnhancer() {
    const obs = new MutationObserver(muts => {
      for (const m of muts) {
        for (const n of m.addedNodes) {
          if (n.nodeType !== 1) continue;
          if (n.classList && n.classList.contains("thinking")) {
            enhanceThinking(n);
          } else if (n.querySelectorAll) {
            n.querySelectorAll(".thinking").forEach(enhanceThinking);
          }
        }
      }
    });
    obs.observe(document.body, { childList: true, subtree: true });
  }

  function getRequestedModel() {
    // index.html declares `let currentModel` (script-scope, NOT window-attached),
    // so window.currentModel is always undefined for us. Read the dropdown DOM
    // directly — it's the source of truth either way.
    const sel = document.getElementById("model-sel");
    let v = sel ? (sel.value || "") : "";
    if (!v && typeof window.currentModel !== "undefined") {
      v = window.currentModel || "";
    }
    return v.trim();
  }

  function enhanceThinking(el) {
    if (el.dataset.mmEnhanced) return;
    el.dataset.mmEnhanced = "1";

    // Find the existing subtitle element ("AI · SkynetClaw") inside the card
    const subEl = el.querySelector(".thinking-sub");
    if (!subEl) return;

    // Read what model the user requested for this turn (from DOM, not window)
    const requested = getRequestedModel();
    const isSentinel = requested.startsWith("@");

    // Compute initial label / model text + role color class
    let labelText, modelText, labelCls = "";
    if (isSentinel) {
      const sent = requested.toLowerCase();
      if (sent === "@auto") {
        labelText = "ROUTING";
        modelText = "selecting…";
      } else {
        const map = { "@executor": "workhorse", "@ambient": "chat", "@precision": "specialist" };
        const roleKey = map[sent] || sent.replace("@", "");
        labelText = roleName(roleKey);
        labelCls  = roleClass(roleKey);
        modelText = "starting…";
      }
    } else if (requested) {
      labelText = "MODEL";
      modelText = requested;
    } else {
      labelText = "AI · SKYNETCLAW";
      modelText = "";
    }

    // Replace the subtitle CONTENT in place — single inline row, no separate panel
    // and NO bottom runner bar. The original .thinking::after gradient line provides
    // enough motion already.
    subEl.innerHTML = `
      <span class="mm-tm-label ${escapeHtml(labelCls)}"><span class="mm-tm-pulse"></span>${escapeHtml(labelText)}</span>
      ${modelText ? `<span class="mm-tm-divider">·</span><span class="mm-tm-model">${escapeHtml(modelText)}</span>` : ""}
    `;

    // If sentinel was used → poll audit to learn the actual resolved model
    if (isSentinel) {
      pollResolvedModel(el);
    }
  }

  async function pollResolvedModel(el) {
    const t0 = Date.now();
    const baseSeen = _lastSeenAuditTs;
    while (Date.now() - t0 < 12000 && el.isConnected) {
      try {
        const entries = await fetchAuditTail(2);
        if (entries.length) {
          const latest = entries[entries.length - 1];
          if (latest.ts > baseSeen) {
            _lastSeenAuditTs = Math.max(_lastSeenAuditTs, latest.ts);
            const labelEl = el.querySelector(".mm-tm-label");
            const modelEl = el.querySelector(".mm-tm-model");
            if (modelEl && latest.chosen_model) {
              modelEl.textContent = latest.chosen_model;
              modelEl.classList.add("mm-resolved");
            }
            if (labelEl && latest.chosen_role) {
              const cls = roleClass(latest.chosen_role);
              const nm  = roleName(latest.chosen_role);
              // Replace inner content but keep the pulse dot
              labelEl.innerHTML = `<span class="mm-tm-pulse"></span>${escapeHtml(nm)}`;
              ["exec","ambient","precision"].forEach(c => labelEl.classList.remove(c));
              if (cls) labelEl.classList.add(cls);
            }
            return; // resolved
          }
        }
      } catch {}
      await new Promise(r => setTimeout(r, 350));
    }
  }

  // ────────────────────────────────────────────────────────────────────────
  // Helpers
  // ────────────────────────────────────────────────────────────────────────
  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  function escapeAttr(s) { return escapeHtml(s); }

  // ────────────────────────────────────────────────────────────────────────
  // Boot
  // ────────────────────────────────────────────────────────────────────────
  async function boot() {
    injectStyle();
    const sel = document.getElementById("model-sel");
    if (!sel) {
      // Page hasn't loaded the dropdown yet — retry
      setTimeout(boot, 800);
      return;
    }
    await fetchModels();
    injectSentinels(sel);
    installRobustSentinels(sel);   // ← 3-layer persistence (wrap loadModels + observer + click)
    injectSetupButton(sel);
    patchModelChangeHandler();
    setupThinkingEnhancer();       // ← enhance the .thinking processing bubble

    // Re-inject sentinels every 3s as final fallback (down from 5s)
    setInterval(() => {
      const s = document.getElementById("model-sel");
      if (s && s.querySelectorAll("option[data-mm-sentinel]").length < SENTINELS.length) {
        injectSentinels(s);
      }
    }, 3000);

    // Live indicator polling (chip on completed AI bubbles)
    setInterval(pollAudit, 1500);

    console.log("[multimodel] ready — sentinels:", SENTINELS.map(s => s.value).join(", "));
    console.log("[multimodel] processing enhancer active");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
