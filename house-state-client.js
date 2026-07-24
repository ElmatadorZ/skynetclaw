/**
 * house-state-client.js — THE HOUSE Unified State Layer · Client
 * ===============================================================
 * SharedStateStore + EventBus for all THE HOUSE UI surfaces.
 *
 * Each UI that loads this script connects to the backend SSE stream
 * (/api/house/state/stream) and receives every state change made by
 * any other surface in real time.
 *
 * API:
 *   HouseState.get('model')            — read local value
 *   HouseState.set('model', 'llama3')  — update locally + broadcast to backend
 *   HouseState.on('model', fn)         — subscribe to changes on a field
 *   HouseState.off('model', fn)        — unsubscribe
 *   HouseState.snapshot()              — copy of full local state
 *
 *   HouseEvent.emit('mission:start', data)  — local-only event
 *   HouseEvent.on('mission:start', fn)
 *   HouseEvent.off('mission:start', fn)
 *
 * Loop prevention:
 *   Remote updates (from SSE) are applied with { _remote: true } and
 *   are NOT posted back to the backend — only local user-initiated
 *   changes propagate outward.
 */

(function (global) {
  'use strict';

  // Idempotent — safe to include multiple times
  if (global.HouseState && global.HouseState.__v) return;

  /* ── Resolve backend URL ─────────────────────────────────────────────────── */
  var _api = (function () {
    if (typeof global.API === 'string' && global.API) return global.API;
    if (location.protocol === 'file:' || location.hostname === '') {
      return 'http://localhost:8766';
    }
    return location.protocol + '//' + location.hostname + ':8766';
  })();

  /* ── EventBus ─────────────────────────────────────────────────────────────── */
  var _bus = Object.create(null);

  var HouseEvent = {
    on: function (ev, fn) {
      (_bus[ev] = _bus[ev] || []).push(fn);
      return function () { HouseEvent.off(ev, fn); };
    },
    off: function (ev, fn) {
      if (_bus[ev]) _bus[ev] = _bus[ev].filter(function (h) { return h !== fn; });
    },
    emit: function (ev, data) {
      (_bus[ev] || []).slice().forEach(function (fn) {
        try { fn(data); } catch (e) { console.error('[HouseEvent]', ev, e); }
      });
    },
  };

  /* ── Local state mirror ──────────────────────────────────────────────────── */
  var _local = {
    model: '',
    connection: { id: null, name: '' },
    active_session: { id: null, type: null, started_at: null },
    mission: { active: false, phase: '', phase_name: '', conv_id: null },
    active_agents: [],
  };

  /* ── Batched POST to backend ─────────────────────────────────────────────── */
  var _pendingTimer = null;
  var _pendingBatch = Object.create(null);
  var _origin = '';   // set by each UI's wiring block

  function _schedulePost(updates) {
    Object.assign(_pendingBatch, updates);
    if (_pendingTimer) clearTimeout(_pendingTimer);
    _pendingTimer = setTimeout(function () {
      var payload = Object.assign({ _origin: _origin }, _pendingBatch);
      _pendingBatch = Object.create(null);
      _pendingTimer = null;
      fetch(_api + '/api/house/state', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        keepalive: true,
      }).catch(function (e) {
        console.warn('[HouseState] POST failed:', e.message);
      });
    }, 60);   // 60 ms batch window
  }

  /* ── Apply a set of changes to local state + fire subscribers ────────────── */
  function _applyChanges(changes, remote) {
    var fired = [];
    Object.keys(changes).forEach(function (k) {
      if (!(k in _local)) return;
      var prev = JSON.stringify(_local[k]);
      var next = JSON.stringify(changes[k]);
      if (prev === next) return;
      _local[k] = changes[k];
      fired.push(k);
    });
    if (!fired.length) return;
    fired.forEach(function (k) {
      HouseEvent.emit(k, _local[k]);
    });
    HouseEvent.emit('state:change', {
      keys: fired,
      remote: !!remote,
      snapshot: HouseState.snapshot(),
    });
    // Remote changes are NOT posted back (loop prevention)
    if (!remote) _schedulePost(changes);
  }

  /* ── SharedStateStore ────────────────────────────────────────────────────── */
  var HouseState = {
    __v: '1.0',

    get: function (key) { return _local[key]; },

    snapshot: function () { return JSON.parse(JSON.stringify(_local)); },

    set: function (key, value, opts) {
      var changes = Object.create(null);
      changes[key] = value;
      _applyChanges(changes, opts && opts._remote);
    },

    patch: function (updates, opts) {
      _applyChanges(updates, opts && opts._remote);
    },

    on:  function (ev, fn) { return HouseEvent.on(ev, fn); },
    off: function (ev, fn) { return HouseEvent.off(ev, fn); },

    /** Set the UI identity tag used in all outgoing POST payloads. */
    setOrigin: function (name) { _origin = name; },

    /** Manually trigger a full re-sync from the backend. */
    resync: function () {
      fetch(_api + '/api/house/state')
        .then(function (r) { return r.json(); })
        .then(function (j) {
          if (j && j.state) _applyChanges(j.state, true);
        })
        .catch(function () {});
    },
  };

  /* ── SSE connection to backend ───────────────────────────────────────────── */
  var _sse = null;
  var _reconnectDelay = 1000;
  var _maxDelay = 30000;

  function _connect() {
    if (_sse) { try { _sse.close(); } catch (_) {} }

    _sse = new EventSource(_api + '/api/house/state/stream');

    _sse.onmessage = function (e) {
      var msg;
      try { msg = JSON.parse(e.data); } catch (_) { return; }

      if (msg.type === 'keepalive') return;

      if (msg.type === 'state_snapshot') {
        _applyChanges(msg.state, true);
        HouseEvent.emit('state:connected', { state: _local, subscribers: msg.subscribers });
        _reconnectDelay = 1000;
        console.log('[HouseState] connected ·', msg.subscribers, 'subscriber(s) ·', _api);
        return;
      }

      if (msg.type === 'state_update' && msg.changes) {
        // Ignore echoes of our own writes (same origin and very recent)
        if (msg.origin && msg.origin === _origin) return;
        _applyChanges(msg.changes, true);
      }
    };

    _sse.onerror = function () {
      console.warn('[HouseState] SSE lost — retry in', _reconnectDelay, 'ms');
      _sse.close();
      setTimeout(_connect, _reconnectDelay);
      _reconnectDelay = Math.min(_reconnectDelay * 2, _maxDelay);
    };
  }

  _connect();

  /* ── Expose globals ──────────────────────────────────────────────────────── */
  global.HouseState = HouseState;
  global.HouseEvent = HouseEvent;

  console.log('[HouseState] initialised · connecting to', _api);

}(window));
