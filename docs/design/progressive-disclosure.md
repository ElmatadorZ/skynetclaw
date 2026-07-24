# Progressive Disclosure Map

> For every screen: what is **Always Visible** (the one question + primary action),
> what is **Contextual** (revealed on intent), and what is **Advanced** (power/expert).
> Progressive disclosure ≠ hiding everything — it means *different levels see different
> depth*. Implemented for Skills & Connections (UI-0009); the rest is the target.

## Rule
`Always Visible` = the single question + Primary Action + ≤3 Secondary.
`Contextual` = appears when the user signals intent (New / edit / add).
`Advanced` = destructive or authoring depth, never in the default scan.

| Screen | Always Visible | Contextual (on intent) | Advanced |
|---|---|---|---|
| **Chat** | message input · Send · mode (segmented) | attachments · skill badge | Exec toggle · Run-Task panel · Internet |
| **Skills** ✅ | skill list · per-row **toggle** · New · Import | **authoring form** (name/desc/prompt) via New/edit | Delete · Apply · tool authoring |
| **Connections** ✅ | endpoint list · integration list · activate · **➕ Add** · Refresh | **add-endpoint / add-integration forms** via ➕ Add | API keys (masked) · delete · type/preset |
| **Tools** | tool list (grouped) · New | tool authoring form | code editor · delete |
| **Obsidian** | one default panel (notes) | search · chat · graph on demand | embed/index · vault switch |
| **Intel** | node map (single view) | node details on click | (embedded) |
| **Council** | the deliberation view | agent detail on click | (embedded) |

✅ = implemented this sprint. Others are the **target** hierarchy (no new features —
same controls, re-leveled).

## Levels (who sees what)
```
Beginner   → Always Visible only  (list + one primary action; can complete the core task)
Power User → + Contextual         (opens New/edit/add when they choose to)
Expert     → + Advanced           (delete, authoring depth, keyboard)
```

## Implementation pattern (reusable)
1. Give the authoring/add panel a stable `id` and default `display:none` + `.open`.
2. Reveal from an explicit intent control (**+ New**, **➕ Add**, row-click-to-edit);
   focus the first field.
3. Auto-close on Save/Delete/Add-success; offer an explicit ✕ ปิด.
4. **Decorate** existing functions (don't rewrite them) so logic is untouched.

This is exactly how Skills (`skill-form-skills` / `skill-form-tools`) and Connections
(`conn-add-box` / `intg-add-box`) were done — additive, all functionality preserved.
