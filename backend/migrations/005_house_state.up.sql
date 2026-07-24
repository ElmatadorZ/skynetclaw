-- 005 house_state (HOUSE STATE ENGINE) UP — self-contained
CREATE TABLE IF NOT EXISTS house_state (
    id TEXT PRIMARY KEY, session_id TEXT, question TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open', confidence REAL NOT NULL DEFAULT 0.0,
    summary TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL, updated_at REAL NOT NULL DEFAULT 0.0);
CREATE TABLE IF NOT EXISTS state_items (
    id TEXT PRIMARY KEY, state_id TEXT NOT NULL, kind TEXT NOT NULL,
    content TEXT NOT NULL, confidence REAL NOT NULL DEFAULT 0.0,
    agent TEXT NOT NULL DEFAULT '', evidence TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active', superseded INTEGER NOT NULL DEFAULT 0, ts REAL NOT NULL,
    FOREIGN KEY (state_id) REFERENCES house_state(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS belief_changes (
    id TEXT PRIMARY KEY, state_id TEXT NOT NULL, item_id TEXT,
    previous TEXT NOT NULL DEFAULT '', new TEXT NOT NULL DEFAULT '',
    prev_confidence REAL NOT NULL DEFAULT 0.0, new_confidence REAL NOT NULL DEFAULT 0.0,
    reason TEXT NOT NULL DEFAULT '', evidence TEXT NOT NULL DEFAULT '',
    agent TEXT NOT NULL DEFAULT '', ts REAL NOT NULL,
    FOREIGN KEY (state_id) REFERENCES house_state(id) ON DELETE CASCADE);
CREATE INDEX IF NOT EXISTS idx_state_session  ON house_state(session_id);
CREATE INDEX IF NOT EXISTS idx_state_status   ON house_state(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_items_state    ON state_items(state_id, kind);
CREATE INDEX IF NOT EXISTS idx_items_active   ON state_items(state_id, superseded);
CREATE INDEX IF NOT EXISTS idx_changes_state  ON belief_changes(state_id, ts DESC);
INSERT OR IGNORE INTO schema_migrations (version, name, applied_at) VALUES (5, 'house_state_engine', strftime('%s','now'));
