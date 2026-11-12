// LexiSyncAI single-page frontend (no build step). All data comes from the local FastAPI backend.

// ------------------------------------------------------------------ icons (Lucide-style strokes)
const ICONS = {
  scale: '<path d="M12 3v18M7 21h10M5 7h14M5 7l-3 7a4 4 0 0 0 6 0zM19 7l-3 7a4 4 0 0 0 6 0z"/>',
  dashboard: '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>',
  briefcase: '<rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2M2 13h20"/>',
  files: '<path d="M15 2H7a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V6z"/><path d="M14 2v5h5M9 13h6M9 9h2"/><path d="M5 7H4a1 1 0 0 0-1 1v13a1 1 0 0 0 1 1h11"/>',
  sparkles: '<path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8zM5 2l.6 1.4L7 4l-1.4.6L5 6l-.6-1.4L3 4l1.4-.6z"/>',
  chart: '<path d="M3 3v18h18"/><rect x="7" y="12" width="3" height="6" rx="1"/><rect x="12" y="8" width="3" height="10" rx="1"/><rect x="17" y="5" width="3" height="13" rx="1"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/>',
  trash: '<path d="M3 6h18M8 6V4h8v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>',
  refresh: '<path d="M21 12a9 9 0 1 1-2.6-6.4L21 8M21 3v5h-5"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
  left: '<path d="M15 18l-6-6 6-6"/>',
  right: '<path d="M9 18l6-6-6-6"/>',
  check: '<path d="M20 6L9 17l-5-5"/>',
  alert: '<path d="M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0zM12 9v4M12 17h.01"/>',
  x: '<path d="M18 6L6 18M6 6l12 12"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
  file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h5"/>',
  link: '<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>',
  play: '<path d="M5 3l14 9-14 9z"/>',
  panel: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M9 12l2 2 4-4"/>',
  cpu: '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3"/>',
  layers: '<path d="M12 2l10 5-10 5L2 7z"/><path d="M2 17l10 5 10-5M2 12l10 5 10-5"/>',
  eye: '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12z"/><circle cx="12" cy="12" r="3"/>',
  clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
  scan: '<path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2M7 12h10"/>',
  folder: '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>',
  external: '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"/>',
  rotate: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5"/>',
};
const icon = (name, size = 18) =>
  `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ""}</svg>`;
const hydrateIcons = (root = document) =>
  root.querySelectorAll("[data-icon]").forEach((el) => { el.innerHTML = icon(el.dataset.icon, el.classList.contains("brand-mark") ? 20 : 18); });

// ------------------------------------------------------------------ helpers
const sectionName = (sec) => (!sec || sec === "General" ? "Preamble / untitled part" : sec);
const $ = (sel, root = document) => root.querySelector(sel);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (n, d = 0) => (n === null || n === undefined || Number.isNaN(n) ? "—" : Number(n).toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: d }));
const pct = (n, d = 0) => (n === null || n === undefined ? "—" : `${(n * 100).toFixed(d)}%`);
const store = {
  get(k, f = null) { try { const v = localStorage.getItem(k); return v === null ? f : JSON.parse(v); } catch { return f; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* storage unavailable */ } },
};
function timeAgo(iso) {
  if (!iso) return "—";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(iso).toLocaleDateString();
}

async function api(path, options = {}) {
  const init = { ...options };
  if (init.body && !(init.body instanceof FormData)) {
    init.headers = { "Content-Type": "application/json", ...(init.headers || {}) };
    init.body = JSON.stringify(init.body);
  }
  const response = await fetch(path, init);
  if (response.status === 204) return null;
  const text = await response.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = { detail: text }; }
  if (!response.ok) {
    const detail = data?.detail;
    throw new Error(typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((d) => d.msg).join("; ") : `Request failed (${response.status})`);
  }
  return data;
}

function toast(message, kind = "") {
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.innerHTML = `${icon(kind === "bad" ? "alert" : "check", 16)}<div>${esc(message)}</div>`;
  $("#toasts").append(el);
  setTimeout(() => el.remove(), kind === "bad" ? 7000 : 3500);
}

function dialog({ title, body = "", fields = [], confirm = "Confirm", danger = false }) {
  return new Promise((resolve) => {
    const dlg = $("#dialog");
    const form = $("#dialog-form");
    form.innerHTML = `
      <h3>${esc(title)}</h3>
      ${body ? `<div class="muted">${body}</div>` : ""}
      ${fields.map((f) => `<label class="field">${esc(f.label)}${f.type === "textarea"
        ? `<textarea name="${f.name}" placeholder="${esc(f.placeholder || "")}" maxlength="${f.max || 500}">${esc(f.value || "")}</textarea>`
        : `<input type="text" name="${f.name}" value="${esc(f.value || "")}" placeholder="${esc(f.placeholder || "")}" maxlength="${f.max || 120}" ${f.required ? "required" : ""}/>`}</label>`).join("")}
      <div class="dlg-actions">
        <button class="btn ghost" value="cancel" formnovalidate>Cancel</button>
        <button class="btn ${danger ? "danger" : "primary"}" value="ok">${esc(confirm)}</button>
      </div>`;
    const onClose = () => {
      dlg.removeEventListener("close", onClose);
      if (dlg.returnValue !== "ok") return resolve(null);
      const data = Object.fromEntries(new FormData(form).entries());
      resolve(data);
    };
    dlg.addEventListener("close", onClose);
    dlg.returnValue = "";
    dlg.showModal();
    form.querySelector("input,textarea")?.focus();
  });
}

// ------------------------------------------------------------------ state
const state = {
  system: null,
  cases: [],
  caseId: store.get("lexisync-case"),
  results: {},        // caseId -> last result
  selected: null,     // { sourceId, quote }
  viewer: null,       // { docId, page }
  pollers: {},
  asking: false,
};

function setCase(id) {
  state.caseId = id;
  store.set("lexisync-case", id);
}
const currentCase = () => state.cases.find((c) => c.id === state.caseId) || null;

async function refreshCases() {
  state.cases = await api("/api/cases");
  if (state.caseId && !currentCase()) setCase(null);
  if (!state.caseId && state.cases.length) setCase(state.cases[0].id);
  return state.cases;
}

async function refreshSystem() {
  try {
    state.system = await api("/api/system");
  } catch {
    state.system = null;
  }
  const el = $("#ollama-status");
  const o = state.system?.ollama;
  const ok = o?.connected && o?.model_available;
  el.innerHTML = `<span class="dot ${ok ? "ok" : o?.connected ? "warn" : "bad"}"></span><span class="footer-text">${
    ok ? "Ollama connected" : o?.connected ? "Model not pulled" : "Ollama offline"}</span>`;
  el.title = o?.error || (o ? `${o.base_url}` : "");
  $("#model-line").textContent = `Model: ${state.system?.models?.llm || "—"}`;
  $("#version-line").textContent = `v${state.system?.version || "—"}`;
}

// ------------------------------------------------------------------ router
const ROUTES = {
  dashboard: { title: "Dashboard", render: renderDashboard },
  cases: { title: "My Cases", render: renderCases },
  library: { title: "Document Library", render: renderLibrary },
  workspace: { title: "Legal AI Workspace", render: renderWorkspace },
  evaluation: { title: "Evaluation & Analytics", render: renderEvaluation },
  settings: { title: "Settings", render: renderSettings },
};

function navigate(route) { location.hash = `#/${route}`; }

async function router() {
  const route = (location.hash.replace(/^#\//, "") || "dashboard").split("?")[0];
  const def = ROUTES[route] || ROUTES.dashboard;
  document.querySelectorAll("#nav button").forEach((b) => b.classList.toggle("active", b.dataset.route === route));
  $("#page-title").textContent = def.title;
  $("#crumb").textContent = currentCase() ? `LexiSyncAI · ${currentCase().name}` : "LexiSyncAI";
  $("#topbar-actions").innerHTML = "";
  const view = $("#view");
  view.innerHTML = `<div class="grid kpis">${'<div class="card kpi skeleton" style="height:96px"></div>'.repeat(4)}</div>`;
  try {
    await def.render(view);
  } catch (error) {
    view.innerHTML = `<div class="card card-pad empty"><div class="ico">${icon("alert", 32)}</div><h3>Something went wrong</h3><p>${esc(error.message)}</p><button class="btn" id="retry">${icon("refresh", 16)} Retry</button></div>`;
    $("#retry").onclick = router;
  }
  hydrateIcons(view);
  view.focus({ preventScroll: true });
}

function topAction(html, handler) {
  const wrap = document.createElement("span");
  wrap.innerHTML = html;
  const btn = wrap.firstElementChild;
  btn.onclick = handler;
  $("#topbar-actions").append(btn);
}

async function createCaseFlow(goLibrary = true) {
  const data = await dialog({
    title: "Create a new case",
    body: "A case is an isolated bundle of 1–5 public legal PDFs with its own search index.",
    fields: [
      { name: "name", label: "Case name", placeholder: "e.g. GDPR compliance review", required: true },
      { name: "description", label: "Description (optional)", type: "textarea", placeholder: "What is this case about?" },
    ],
    confirm: "Create case",
  });
  if (!data || !data.name?.trim()) return;
  try {
    const created = await api("/api/cases", { method: "POST", body: { name: data.name, description: data.description || "" } });
    setCase(created.id);
    await refreshCases();
    toast(`Case “${created.name}” created`, "good");
    if (goLibrary) navigate("library"); else router();
  } catch (error) { toast(error.message, "bad"); }
}

const statusBadge = (status) => {
  const map = { indexed: ["good", "Indexed"], indexing: ["info", "Indexing…"], pending: ["warn", "Needs indexing"], empty: ["", "No documents"], error: ["bad", "Error"] };
  const [cls, label] = map[status] || ["", status];
  return `<span class="badge ${cls}">${label}</span>`;
};

function caseSelect(id = "case-select", onlyIndexed = false) {
  if (!state.cases.length) return "";
  return `<select id="${id}" aria-label="Select case" style="width:auto;min-width:220px">${state.cases.map((c) =>
    `<option value="${esc(c.id)}" ${c.id === state.caseId ? "selected" : ""} ${onlyIndexed && c.status !== "indexed" ? "disabled" : ""}>${esc(c.name)}${c.status !== "indexed" ? " (not indexed)" : ""}</option>`).join("")}</select>`;
}
function bindCaseSelect(id = "case-select") {
  const el = $(`#${id}`);
  if (el) el.onchange = () => { setCase(el.value); state.selected = null; state.viewer = null; router(); };
}

// ------------------------------------------------------------------ dashboard
async function renderDashboard(view) {
  const data = await api("/api/dashboard");
  await refreshCases();
  topAction(`<button class="btn primary">${icon("plus", 16)} Create New Case</button>`, () => createCaseFlow());
  const t = data.totals;
  const o = data.ollama;
  const kpi = (ic, label, value, hint) => `<div class="card kpi"><div class="label"><span class="ico">${icon(ic, 16)}</span>${label}</div><div class="value">${value}</div><div class="hint">${hint}</div></div>`;
  view.innerHTML = `
    <div class="card card-pad" style="margin-bottom:18px;display:flex;gap:18px;align-items:center;flex-wrap:wrap;background:linear-gradient(120deg,var(--accent-soft),transparent 55%),var(--glass)">
      <div style="flex:1;min-width:260px">
        <div class="faint" style="text-transform:uppercase;letter-spacing:.6px">Evidence-grounded legal intelligence</div>
        <h2 style="font-size:22px;margin:6px 0">Every answer cites its page and clause, or the system abstains.</h2>
        <div class="muted">Hybrid BM25 + dense retrieval, cross-encoder reranking, a local LLM and claim-level verification, all running on this machine.</div>
      </div>
      <div class="row">
        <button class="btn primary" id="cta-new">${icon("plus", 16)} Create New Case</button>
        <button class="btn" id="cta-ws">${icon("sparkles", 16)} Open workspace</button>
      </div>
    </div>
    <div class="grid kpis" style="margin-bottom:18px">
      ${kpi("briefcase", "Cases", fmt(t.cases), `${t.indexed_cases} indexed`)}
      ${kpi("files", "Documents", fmt(t.documents), "public legal PDFs")}
      ${kpi("layers", "Indexed pages", fmt(t.pages), `${fmt(t.chunks)} searchable passages`)}
      ${kpi("scale", "Legal sections", fmt(t.sections), "articles, sections, clauses")}
      ${kpi("scan", "Scanned pages", fmt(t.scanned_pages), "flagged for OCR")}
    </div>
    <div class="grid two">
      <div class="card card-pad">
        <div class="card-head"><h2>Recent cases</h2><div class="spacer"></div><button class="btn ghost sm" id="all-cases">View all</button></div>
        ${data.recent_cases.length ? `<div class="list">${data.recent_cases.map((c) => `
          <div class="list-item" data-case="${esc(c.id)}">
            <span class="ico" style="color:var(--accent-2)">${icon("folder", 18)}</span>
            <div class="grow"><div class="ellipsis" style="font-weight:600">${esc(c.name)}</div>
            <div class="faint">${c.document_count} documents · ${fmt(c.page_count)} pages · updated ${timeAgo(c.updated_at)}</div></div>
            ${statusBadge(c.status)}
          </div>`).join("")}</div>`
        : `<div class="empty"><div class="ico">${icon("briefcase", 30)}</div><h3>No cases yet</h3><p>Create a case and upload 2–5 public legal PDFs.</p></div>`}
      </div>
      <div class="card card-pad">
        <div class="card-head"><h2>Recent questions</h2></div>
        ${data.recent_queries.length ? `<div class="list">${data.recent_queries.map((q) => `
          <div class="list-item" data-q-case="${esc(q.case_id)}" data-q-id="${esc(q.id)}">
            <span class="conf ${esc(q.confidence)}" style="padding:3px 8px;font-size:11px">${esc(q.confidence || "—")}</span>
            <div class="grow"><div class="ellipsis">${esc(q.question)}</div><div class="faint">${esc(q.case_name)} · ${timeAgo(q.asked_at)} · ${fmt(q.seconds, 1)} s</div></div>
          </div>`).join("")}</div>`
        : `<div class="empty"><div class="ico">${icon("sparkles", 30)}</div><h3>No questions yet</h3><p>Ask your first question in the Legal AI Workspace.</p></div>`}
      </div>
      <div class="card card-pad">
        <div class="card-head"><h2>System status</h2><div class="spacer"></div><button class="btn ghost sm" id="sys-refresh">${icon("refresh", 15)} Refresh</button></div>
        <dl class="kv">
          <dt>Local LLM</dt><dd><span class="badge ${o.connected && o.model_available ? "good" : "bad"}">${o.connected ? (o.model_available ? "Connected" : "Model missing") : "Offline"}</span> ${esc(o.model)}</dd>
          <dt>Ollama URL</dt><dd>${esc(o.base_url)}</dd>
          ${!o.connected ? `<dt>Fix</dt><dd>Start the Ollama app, then refresh.</dd>` : !o.model_available ? `<dt>Fix</dt><dd>ollama pull ${esc(o.model)}</dd>` : ""}
          <dt>Embeddings</dt><dd>${esc(state.system?.models?.embedding || "—")}</dd>
          <dt>Reranker</dt><dd>${esc(state.system?.models?.reranker || "—")}</dd>
          <dt>OCR</dt><dd>${state.system?.ocr?.tesseract_found ? "Tesseract available" : "Tesseract not found (scanned pages are flagged only)"}</dd>
        </dl>
      </div>
      <div class="card card-pad">
        <div class="card-head"><h2>Indexing status</h2></div>
        ${state.cases.length ? `<table class="data"><tbody>${state.cases.slice(0, 6).map((c) => `<tr><td>${esc(c.name)}</td><td class="num">${fmt(c.chunk_count)} passages</td><td class="num">${statusBadge(c.status)}</td></tr>`).join("")}</tbody></table>` : `<div class="faint">No cases to index yet.</div>`}
      </div>
    </div>`;
  $("#cta-new").onclick = () => createCaseFlow();
  $("#cta-ws").onclick = () => navigate("workspace");
  $("#all-cases").onclick = () => navigate("cases");
  $("#sys-refresh").onclick = async () => { await refreshSystem(); router(); };
  view.querySelectorAll("[data-case]").forEach((el) => (el.onclick = () => { setCase(el.dataset.case); navigate("workspace"); }));
  view.querySelectorAll("[data-q-case]").forEach((el) => (el.onclick = async () => {
    setCase(el.dataset.qCase);
    const history = await api(`/api/cases/${encodeURIComponent(el.dataset.qCase)}/history`);
    const record = history.find((h) => h.id === el.dataset.qId);
    if (record) state.results[el.dataset.qCase] = record;
    state.selected = null; state.viewer = null;
    navigate("workspace");
  }));
}

// ------------------------------------------------------------------ cases
async function renderCases(view) {
  await refreshCases();
  topAction(`<button class="btn primary">${icon("plus", 16)} New case</button>`, () => createCaseFlow());
  const filter = store.get("lexisync-case-filter", "");
  view.innerHTML = `
    <div class="card card-pad">
      <div class="card-head">
        <div style="position:relative;flex:1;max-width:380px">
          <input type="search" id="case-search" placeholder="Search cases…" value="${esc(filter)}" style="padding-left:34px" aria-label="Search cases"/>
          <span style="position:absolute;left:10px;top:10px;color:var(--text-3)">${icon("search", 16)}</span>
        </div>
        <div class="spacer"></div><span class="faint">${state.cases.length} case(s)</span>
      </div>
      <div id="case-table"></div>
    </div>`;
  const draw = () => {
    const q = $("#case-search").value.trim().toLowerCase();
    store.set("lexisync-case-filter", q);
    const rows = state.cases.filter((c) => !q || c.name.toLowerCase().includes(q) || (c.description || "").toLowerCase().includes(q));
    $("#case-table").innerHTML = rows.length ? `<div class="table-wrap"><table class="data">
      <thead><tr><th>Case</th><th class="num">Docs</th><th class="num">Pages</th><th class="num">Passages</th><th>Status</th><th>Created</th><th>Updated</th><th></th></tr></thead>
      <tbody>${rows.map((c) => `<tr>
        <td><div style="font-weight:600">${esc(c.name)}</div><div class="faint">${esc(c.description || c.id)}</div></td>
        <td class="num">${c.document_count}</td><td class="num">${fmt(c.page_count)}</td><td class="num">${fmt(c.chunk_count)}</td>
        <td>${statusBadge(c.status)}</td>
        <td class="faint">${new Date(c.created_at).toLocaleString()}</td><td class="faint">${timeAgo(c.updated_at)}</td>
        <td><div class="row" style="justify-content:flex-end;flex-wrap:nowrap">
          <button class="btn sm" data-act="open" data-id="${esc(c.id)}" title="Open in workspace">${icon("sparkles", 15)} Ask</button>
          <button class="btn sm" data-act="docs" data-id="${esc(c.id)}" title="Manage documents">${icon("files", 15)} Documents</button>
          <button class="btn sm ghost" data-act="reset" data-id="${esc(c.id)}" title="Remove all documents and the index">${icon("rotate", 15)}</button>
          <button class="btn sm danger" data-act="delete" data-id="${esc(c.id)}" title="Delete case">${icon("trash", 15)}</button>
        </div></td></tr>`).join("")}</tbody></table></div>`
      : `<div class="empty"><div class="ico">${icon("briefcase", 30)}</div><h3>${state.cases.length ? "No matching cases" : "No cases yet"}</h3><p>Create a case to start analysing documents.</p></div>`;
    hydrateIcons($("#case-table"));
    $("#case-table").querySelectorAll("[data-act]").forEach((btn) => (btn.onclick = () => caseAction(btn.dataset.act, btn.dataset.id)));
  };
  $("#case-search").oninput = draw;
  draw();
}

async function caseAction(action, id) {
  const c = state.cases.find((x) => x.id === id);
  if (action === "open") { setCase(id); return navigate("workspace"); }
  if (action === "docs") { setCase(id); return navigate("library"); }
  if (action === "reset") {
    const ok = await dialog({ title: `Reset “${c.name}”?`, body: "All uploaded documents, the search index and the question history of this case will be removed. The case itself is kept.", confirm: "Reset case", danger: true });
    if (!ok) return;
    try { await api(`/api/cases/${encodeURIComponent(id)}/reset`, { method: "POST" }); toast("Case reset", "good"); delete state.results[id]; router(); } catch (e) { toast(e.message, "bad"); }
  }
  if (action === "delete") {
    const ok = await dialog({ title: `Delete “${c.name}”?`, body: "This permanently deletes the case, its documents and its index. This cannot be undone.", confirm: "Delete permanently", danger: true });
    if (!ok) return;
    try { await api(`/api/cases/${encodeURIComponent(id)}`, { method: "DELETE" }); toast("Case deleted", "good"); delete state.results[id]; if (state.caseId === id) setCase(null); router(); } catch (e) { toast(e.message, "bad"); }
  }
}

// ------------------------------------------------------------------ library
async function renderLibrary(view) {
  await refreshCases();
  const c = currentCase();
  topAction(`<button class="btn">${icon("plus", 16)} New case</button>`, () => createCaseFlow());
  if (!c) {
    view.innerHTML = `<div class="card card-pad empty"><div class="ico">${icon("folder", 34)}</div><h3>Create a case first</h3><p>Documents belong to a case so each case keeps an isolated index.</p><button class="btn primary" id="mk">${icon("plus", 16)} Create New Case</button></div>`;
    $("#mk").onclick = () => createCaseFlow();
    return;
  }
  const running = c.progress?.running;
  view.innerHTML = `
    <div class="row" style="margin-bottom:16px">${caseSelect()}<span class="faint">${esc(c.description || "")}</span><div class="spacer" style="flex:1"></div>${statusBadge(c.status)}</div>
    <div class="grid two" style="margin-bottom:16px">
      <div class="card card-pad">
        <h2>Add documents</h2>
        <div class="dropzone" id="drop" tabindex="0" role="button" aria-label="Upload PDF files">
          <div class="ico">${icon("upload", 30)}</div>
          <div style="font-weight:600;color:var(--text)">Drop PDFs here or click to browse</div>
          <div class="faint">1–5 public legal PDFs per case · max ${50} MB each · duplicates are detected</div>
          <input type="file" id="file-input" accept="application/pdf,.pdf" multiple hidden />
        </div>
        <div id="upload-progress" style="margin-top:12px"></div>
        <form class="row" id="url-form" style="margin-top:12px;flex-wrap:nowrap">
          <input type="url" id="url-input" placeholder="…or paste a public PDF URL (EUR-Lex, gov.uk, SEC EDGAR)" aria-label="PDF URL" />
          <button class="btn" type="submit">${icon("link", 16)} Fetch</button>
        </form>
      </div>
      <div class="card card-pad">
        <h2>Index</h2>
        <p class="muted" style="margin-top:0">Indexing extracts text in reading order, removes running headers, detects scanned pages and tables, chunks by legal structure, embeds passages and builds this case's BM25 + FAISS index.</p>
        <div class="row">
          <button class="btn primary" id="index-btn" ${!c.document_count || running ? "disabled" : ""}>${icon("play", 16)} ${c.status === "indexed" ? "Re-index documents" : "Index documents"}</button>
          ${c.status === "indexed" ? `<button class="btn" id="go-ws">${icon("sparkles", 16)} Ask questions</button>` : ""}
        </div>
        <div id="index-progress" style="margin-top:14px">${running ? progressHtml(c.progress.message) : c.status === "error" ? `<div class="callout bad">${icon("alert", 16)} ${esc(c.error)}</div>` : c.indexed_at ? `<div class="faint">Last indexed ${timeAgo(c.indexed_at)}${c.index_seconds ? ` in ${fmt(c.index_seconds, 1)} s` : ""}.</div>` : ""}</div>
      </div>
    </div>
    <div class="card card-pad">
      <div class="card-head"><h2>Documents (${c.document_count})</h2><div class="spacer"></div><span class="faint">${fmt(c.page_count)} pages · ${fmt(c.section_count)} sections · ${fmt(c.chunk_count)} passages</span></div>
      ${c.documents.length ? `<div class="table-wrap"><table class="data"><thead><tr>
        <th>File</th><th class="num">Pages</th><th class="num">Sections</th><th class="num">Passages</th><th class="num">Scanned</th><th>OCR</th><th class="num">Tables</th><th>Status</th><th></th></tr></thead>
        <tbody>${c.documents.map((d) => docRow(d)).join("")}</tbody></table></div>`
      : `<div class="empty"><div class="ico">${icon("files", 30)}</div><h3>No documents yet</h3><p>Upload public legal PDFs to this case.</p></div>`}
    </div>`;
  bindCaseSelect();
  const input = $("#file-input");
  const drop = $("#drop");
  drop.onclick = () => input.click();
  drop.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); } };
  drop.ondragover = (e) => { e.preventDefault(); drop.classList.add("over"); };
  drop.ondragleave = () => drop.classList.remove("over");
  drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove("over"); uploadFiles([...e.dataTransfer.files]); };
  input.onchange = () => uploadFiles([...input.files]);
  $("#url-form").onsubmit = async (e) => {
    e.preventDefault();
    const url = $("#url-input").value.trim();
    if (!url) return;
    $("#upload-progress").innerHTML = progressHtml(`Downloading ${url}`);
    try { await api(`/api/cases/${encodeURIComponent(c.id)}/documents/url`, { method: "POST", body: { url } }); toast("Document added. Index the case to make it searchable.", "good"); router(); }
    catch (err) { $("#upload-progress").innerHTML = ""; toast(err.message, "bad"); }
  };
  $("#index-btn").onclick = async () => {
    try { await api(`/api/cases/${encodeURIComponent(c.id)}/index`, { method: "POST" }); pollIndexing(c.id); router(); } catch (e) { toast(e.message, "bad"); }
  };
  if ($("#go-ws")) $("#go-ws").onclick = () => navigate("workspace");
  view.querySelectorAll("[data-remove]").forEach((b) => (b.onclick = async () => {
    const ok = await dialog({ title: "Remove document?", body: `<b>${esc(b.dataset.name)}</b> will be deleted from this case. The case must be re-indexed afterwards.`, confirm: "Remove", danger: true });
    if (!ok) return;
    try { await api(`/api/cases/${encodeURIComponent(c.id)}/documents/${encodeURIComponent(b.dataset.remove)}`, { method: "DELETE" }); toast("Document removed", "good"); router(); } catch (e) { toast(e.message, "bad"); }
  }));
  view.querySelectorAll("[data-preview]").forEach((b) => (b.onclick = () => previewDocument(c, b.dataset.preview)));
  view.querySelectorAll("[data-structure]").forEach((b) => (b.onclick = () => {
    const row = $(`#struct-${CSS.escape(b.dataset.structure)}`);
    row.hidden = !row.hidden;
  }));
  if (running) pollIndexing(c.id);

  async function uploadFiles(files) {
    const pdfs = files.filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    if (!pdfs.length) return toast("Please choose PDF files.", "bad");
    const form = new FormData();
    pdfs.forEach((f) => form.append("files", f));
    const box = $("#upload-progress");
    box.innerHTML = `<div class="faint">Uploading ${pdfs.length} file(s)…</div><div class="progress"><div style="width:0%"></div></div>`;
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/cases/${encodeURIComponent(c.id)}/documents`);
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) box.querySelector(".progress div").style.width = `${(e.loaded / e.total) * 100}%`; };
    xhr.onload = () => {
      let data = null;
      try { data = JSON.parse(xhr.responseText); } catch { /* handled below */ }
      if (xhr.status >= 400 || !data) { box.innerHTML = ""; return toast(data?.detail || "Upload failed", "bad"); }
      data.results.forEach((r) => toast(r.ok ? `Added ${r.document.file_name}` : r.error, r.ok ? "good" : "bad"));
      router();
    };
    xhr.onerror = () => { box.innerHTML = ""; toast("Upload failed: the server is not reachable.", "bad"); };
    xhr.send(form);
  }
}

const progressHtml = (message) => `<div class="row" style="margin-bottom:8px"><span class="spinner"></span><span>${esc(message || "Working…")}</span></div><div class="progress indeterminate"><div></div></div>`;

function docRow(d) {
  const scanned = d.scanned_pages?.length || 0;
  const ocr = d.ocr_pages?.length ? `<span class="badge info">${d.ocr_pages.length} page(s) OCR</span>` : scanned ? (d.ocr_available ? '<span class="badge warn">OCR failed</span>' : '<span class="badge warn">Unavailable</span>') : '<span class="faint">Not needed</span>';
  const warnings = d.warnings?.length ? `<div class="faint" style="color:var(--warn)">${icon("alert", 13)} ${esc(d.warnings.join(" "))}</div>` : "";
  const flagged = (d.page_details || []).filter((p) => p.scanned || p.tables || p.columns > 1 || p.warnings?.length);
  return `<tr>
    <td><div class="row" style="flex-wrap:nowrap;gap:8px"><span style="color:var(--accent-2)">${icon("file", 18)}</span><div><div style="font-weight:600">${esc(d.file_name)}</div>
      <div class="faint">${esc(d.title || "")}${d.title ? " · " : ""}${fmt((d.size_bytes || 0) / 1024, 0)} KB</div>${warnings}</div></div></td>
    <td class="num">${fmt(d.pages)}</td><td class="num">${fmt(d.sections)}</td><td class="num">${fmt(d.chunks)}</td>
    <td class="num">${scanned ? `<span class="badge warn">${scanned}</span>` : "0"}</td><td>${ocr}</td><td class="num">${fmt(d.tables)}</td>
    <td>${statusBadge(d.status === "indexed" ? "indexed" : "pending")}</td>
    <td><div class="row" style="justify-content:flex-end;flex-wrap:nowrap">
      ${d.status === "indexed" ? `<button class="btn sm ghost" data-structure="${esc(d.document_id)}" title="Show detected structure">${icon("layers", 15)}</button>` : ""}
      <button class="btn sm ghost" data-preview="${esc(d.document_id)}" title="Preview">${icon("eye", 15)}</button>
      <button class="btn sm danger" data-remove="${esc(d.document_id)}" data-name="${esc(d.file_name)}" title="Remove">${icon("trash", 15)}</button>
    </div></td></tr>
    <tr id="struct-${esc(d.document_id)}" hidden><td colspan="9">
      <div class="grid two">
        <div><h4 style="margin:0 0 6px">Detected sections (${d.sections || 0})</h4>
          <div style="max-height:220px;overflow:auto" class="faint">${(d.section_titles || []).map((s) => `<div>${esc(s)}</div>`).join("") || "No headings detected"}</div></div>
        <div><h4 style="margin:0 0 6px">Extraction report</h4>
          <dl class="kv">
            <dt>Running heads removed</dt><dd>${fmt(d.running_heads_removed)}</dd>
            <dt>Footnotes found</dt><dd>${fmt(d.footnotes)}</dd>
            <dt>Multi-column pages</dt><dd>${(d.multi_column_pages || []).join(", ") || "none"}</dd>
            <dt>Scanned pages</dt><dd>${(d.scanned_pages || []).join(", ") || "none"}</dd>
            <dt>OCR pages</dt><dd>${(d.ocr_pages || []).join(", ") || "none"}</dd>
            <dt>Table passages</dt><dd>${fmt(d.table_chunks)}</dd>
          </dl>
          ${flagged.length ? `<div class="faint" style="margin-top:8px">${flagged.slice(0, 12).map((p) => `p.${p.page}: ${[p.scanned ? "scanned" : "", p.method === "ocr" ? `OCR ${fmt(p.ocr_confidence, 0)}/100` : "", p.tables ? `${p.tables} table(s)` : "", p.columns > 1 ? "2 columns" : "", ...(p.warnings || [])].filter(Boolean).join(", ")}`).join("<br>")}</div>` : ""}
        </div>
      </div></td></tr>`;
}

function pollIndexing(caseId) {
  if (state.pollers[caseId]) return;
  state.pollers[caseId] = setInterval(async () => {
    try {
      const c = await api(`/api/cases/${encodeURIComponent(caseId)}`);
      const box = $("#index-progress");
      if (c.progress?.running) { if (box) box.innerHTML = progressHtml(c.progress.message); return; }
      clearInterval(state.pollers[caseId]);
      delete state.pollers[caseId];
      if (c.status === "indexed") toast(`Indexed ${c.document_count} document(s): ${c.chunk_count} passages`, "good");
      else if (c.status === "error") toast(`Indexing failed: ${c.error}`, "bad");
      if (location.hash.includes("library")) router();
    } catch { /* transient */ }
  }, 1500);
}

async function previewDocument(c, docId) {
  const d = c.documents.find((x) => x.document_id === docId);
  let page = 1;
  const total = d.pages || 1;
  const dlg = $("#dialog");
  const form = $("#dialog-form");
  dlg.style.width = "min(860px, 94vw)";
  const draw = () => {
    form.innerHTML = `<div class="row"><h3 style="flex:1">${esc(d.file_name)}</h3>
      <button type="button" class="btn sm" id="pv-prev" ${page <= 1 ? "disabled" : ""}>${icon("left", 15)}</button>
      <span class="faint">Page ${page}${d.pages ? ` / ${total}` : ""}</span>
      <button type="button" class="btn sm" id="pv-next" ${d.pages && page >= total ? "disabled" : ""}>${icon("right", 15)}</button>
      <button class="btn sm ghost" value="cancel">${icon("x", 15)}</button></div>
      <div class="page-stage" style="max-height:72vh"><div class="page-frame" style="max-width:720px"><img alt="Page ${page} of ${esc(d.file_name)}" src="/api/cases/${encodeURIComponent(c.id)}/documents/${encodeURIComponent(docId)}/pages/${page}/image"></div></div>`;
    $("#pv-prev").onclick = () => { page -= 1; draw(); };
    $("#pv-next").onclick = () => { page += 1; draw(); };
  };
  draw();
  dlg.addEventListener("close", () => { dlg.style.width = ""; }, { once: true });
  dlg.showModal();
}

// ------------------------------------------------------------------ workspace
function suggestions(c) {
  const titles = c.documents.flatMap((d) => d.section_titles || []).filter((t) => /—/.test(t) && /^(article|section|clause|§)/i.test(t));
  const pick = (i) => titles[Math.floor((titles.length * i) / 5)];
  const out = [];
  const t1 = pick(1), t2 = pick(3);
  if (t1) out.push(`What does ${t1.split("—")[0].trim()} (${t1.split("—")[1].trim()}) require?`);
  if (t1 && t2 && t1 !== t2) out.push(`How do ${t1.split("—")[0].trim()} and ${t2.split("—")[0].trim()} relate to each other?`);
  out.push("What are the main obligations and deadlines in these documents?");
  out.push("What is the governing law of the subcontractor agreement?");
  return out;
}

async function renderWorkspace(view) {
  await refreshCases();
  const indexed = state.cases.filter((c) => c.status === "indexed");
  if (!indexed.length) {
    view.innerHTML = `<div class="card card-pad empty"><div class="ico">${icon("sparkles", 34)}</div><h3>No indexed case yet</h3><p>Create a case, upload 2–5 public legal PDFs and index them. Then ask questions here.</p>
      <div class="row" style="justify-content:center"><button class="btn primary" id="mk">${icon("plus", 16)} Create New Case</button>${state.cases.length ? `<button class="btn" id="lib">${icon("files", 16)} Document Library</button>` : ""}</div></div>`;
    $("#mk").onclick = () => createCaseFlow();
    if ($("#lib")) $("#lib").onclick = () => navigate("library");
    return;
  }
  const linkedCase = new URLSearchParams(location.hash.split("?")[1] || "").get("case");
  if (linkedCase && indexed.some((x) => x.id === linkedCase)) setCase(linkedCase);
  if (!currentCase() || currentCase().status !== "indexed") setCase(indexed[0].id);
  const c = currentCase();
  $("#crumb").textContent = `LexiSyncAI · ${c.name}`;
  const history = await api(`/api/cases/${encodeURIComponent(c.id)}/history?limit=30`).catch(() => []);
  // Deep link to a past answer: #/workspace?case=<id>&h=<answer id>
  const linked = new URLSearchParams(location.hash.split("?")[1] || "").get("h");
  if (linked) {
    const record = history.find((h) => h.id === linked);
    if (record && state.results[c.id]?.id !== record.id) { state.results[c.id] = record; state.selected = null; state.viewer = null; }
  }
  const result = state.results[c.id];

  view.innerHTML = `
    <div class="workspace">
      <section class="ws-left" aria-label="Question and answer">
        <div class="card card-pad ask-box">
          <div class="row" style="margin-bottom:12px">${caseSelect("case-select", true)}
            <select id="doc-filter" aria-label="Limit to document" style="width:auto">
              <option value="">${c.document_count === 1 ? "The case document" : `All ${c.document_count} documents`}</option>
              ${c.documents.map((d) => `<option value="${esc(d.document_id)}">${esc(d.file_name)}</option>`).join("")}
            </select>
          </div>
          <form id="ask-form">
            <label class="sr-only" for="question">Question</label>
            <textarea id="question" placeholder="Ask a question a lawyer, auditor or compliance officer would ask…" maxlength="1000"></textarea>
            <div class="row" style="margin-top:10px">
              <span class="faint">Ctrl + Enter to ask · answers use only this case's documents</span>
              <div class="spacer" style="flex:1"></div>
              <button class="btn primary" id="ask-btn" type="submit">${icon("sparkles", 16)} Ask LexiSyncAI</button>
            </div>
          </form>
          <div style="margin-top:12px"><div class="faint" style="margin-bottom:6px">Suggested questions</div>
            <div class="chips">${suggestions(c).map((q) => `<button class="chip" type="button" data-suggest="${esc(q)}">${esc(q)}</button>`).join("")}</div></div>
        </div>
        <div id="answer-area">${result ? "" : `<div class="card card-pad empty"><div class="ico">${icon("shield", 32)}</div><h3>Grounded answers only</h3><p>Every claim is checked against the cited passage. If the evidence is missing, LexiSyncAI says so instead of guessing.</p></div>`}</div>
        ${history.length ? `<div class="card card-pad"><h3>Recent questions in this case</h3><div class="list">${history.map((h) => `
          <div class="list-item" data-hist="${esc(h.id)}"><span class="conf ${esc(h.confidence?.level)}" style="padding:3px 8px;font-size:11px">${esc(h.confidence?.level || "—")}</span>
          <div class="grow ellipsis">${esc(h.question)}</div><span class="faint">${timeAgo(h.asked_at)}</span></div>`).slice(0, 8).join("")}</div></div>` : ""}
      </section>
      <section class="ws-right" aria-label="Evidence viewer"><div class="card viewer" id="viewer"></div></section>
    </div>`;

  bindCaseSelect();
  const q = $("#question");
  $("#ask-form").onsubmit = (e) => { e.preventDefault(); ask(c); };
  q.onkeydown = (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); ask(c); } };
  view.querySelectorAll("[data-suggest]").forEach((b) => (b.onclick = () => { q.value = b.dataset.suggest; q.focus(); }));
  view.querySelectorAll("[data-hist]").forEach((el) => (el.onclick = () => {
    const record = history.find((h) => h.id === el.dataset.hist);
    if (!record) return;
    state.results[c.id] = record; state.selected = null; state.viewer = null;
    q.value = record.question;
    drawAnswer(c, record);
  }));
  if (result) { q.value = result.question; drawAnswer(c, result); } else drawViewer(c, null);
}

async function ask(c) {
  const question = $("#question").value.trim();
  if (!question || state.asking) return;
  state.asking = true;
  $("#ask-btn").disabled = true;
  const docFilter = $("#doc-filter").value;
  const started = Date.now();
  const area = $("#answer-area");
  area.innerHTML = `<div class="card"><div class="steps">
      <div class="row"><span class="spinner"></span><b>Working on it…</b><span class="faint" id="elapsed">0 s</span></div>
      <div class="step active">${icon("search", 16)} Planning sub-questions, hybrid BM25 + dense retrieval, cross-encoder reranking</div>
      <div class="step active">${icon("cpu", 16)} Drafting a structured answer with the local LLM (${esc(state.system?.models?.llm || "Ollama")})</div>
      <div class="step active">${icon("shield", 16)} Verifying every claim against its cited passage</div>
      <div class="faint">On a laptop this usually takes 5–40 seconds.</div></div></div>`;
  const timer = setInterval(() => { const el = $("#elapsed"); if (el) el.textContent = `${Math.round((Date.now() - started) / 1000)} s`; }, 500);
  try {
    const result = await api(`/api/cases/${encodeURIComponent(c.id)}/ask`, { method: "POST", body: { question, document_ids: docFilter ? [docFilter] : null } });
    state.results[c.id] = result;
    state.selected = null; state.viewer = null;
    drawAnswer(c, result);
  } catch (error) {
    area.innerHTML = `<div class="card card-pad callout bad">${icon("alert", 16)} <b>Could not answer.</b> ${esc(error.message)}</div>`;
  } finally {
    clearInterval(timer);
    state.asking = false;
    const btn = $("#ask-btn"); if (btn) btn.disabled = false;
  }
}

function citeChips(claim, sources) {
  return claim.sources.map((sid) => {
    const s = sources.find((x) => x.source_id === sid);
    if (!s) return "";  // never render a broken citation
    const label = `${sid} · p.${s.pages.join(",")}`;
    return `<button class="cite" type="button" data-cite="${esc(sid)}" data-quote="${esc(claim.quote || "")}" title="${esc(s.file_name)} · ${esc(sectionName(s.section))}">${esc(label)}</button>`;
  }).join("");
}

function drawAnswer(c, r) {
  const area = $("#answer-area");
  const level = r.confidence?.level || "INSUFFICIENT";
  const usage = r.usage || {};
  const meta = `<div class="meta-row">
      <span>${icon("clock", 13)} <b>${fmt(r.timings?.total_seconds, 1)} s</b> total</span>
      <span>retrieval <b>${fmt(r.timings?.retrieval_seconds, 2)} s</b></span>
      <span>generation <b>${fmt(r.timings?.generation_seconds, 1)} s</b></span>
      <span><b>${fmt(usage.llm_calls)}</b> LLM call(s) · <b>${fmt(usage.prompt_tokens)}</b>+<b>${fmt(usage.completion_tokens)}</b> tokens</span></div>`;
  const confReasons = (r.confidence?.reasons || []).map((x) => `<li>${esc(x)}</li>`).join("");

  if (r.abstained) {
    const a = r.abstention || {};
    area.innerHTML = `<div class="card answer abstain">
      <div class="answer-head"><span class="conf INSUFFICIENT">${icon("alert", 15)} INSUFFICIENT EVIDENCE</span><span class="badge bad">Abstained</span><div class="spacer" style="flex:1"></div>${meta}</div>
      <div class="answer-body">
        <div class="abstain-msg">${esc(a.message || r.answer)}</div>
        <div class="callout"><b>Why:</b> ${esc(a.reason || "")}
          ${a.missing?.length ? `<div style="margin-top:6px"><b>Missing:</b><ul>${a.missing.map((m) => `<li>${esc(m)}</li>`).join("")}</ul></div>` : ""}
          <div style="margin-top:6px"><b>Documents searched:</b> ${esc((a.documents_searched || []).join(", ") || "—")}</div></div>
        ${r.removed_claims?.length ? `<div class="faint">${r.removed_claims.length} drafted claim(s) were rejected by verification (see diagnostics).</div>` : ""}
      </div></div>${diagnosticsHtml(r)}`;
  } else {
    const verification = r.verification || {};
    area.innerHTML = `<div class="card answer">
      <div class="answer-head">
        <span class="conf ${level}" title="Rule-based confidence (not a calibrated probability)">${icon(level === "HIGH" ? "shield" : level === "LOW" ? "alert" : "check", 15)} ${level} CONFIDENCE</span>
        ${r.status === "partial" ? '<span class="badge warn">Partially answered</span>' : ""}
        <span class="badge good">${icon("check", 13)} ${verification.supported}/${verification.total_claims} claims verified</span>
        ${verification.retry_count ? `<span class="badge violet">${verification.retry_count} corrective retry</span>` : ""}
      </div>
      <div class="answer-body">
        <div><h4>Direct answer</h4><div class="direct">${esc(r.direct_answer.text)} ${citeChips(r.direct_answer, r.sources)}<span class="verify-tag">${icon("check", 12)} ${r.direct_answer.method === "llm_review" ? "LLM-reviewed" : "quote-verified"}</span></div></div>
        ${r.findings.length ? `<div><h4>Key findings</h4>${r.findings.map((f) => `<div class="finding">${esc(f.text)} ${citeChips(f, r.sources)}<span class="verify-tag">${icon("check", 12)} ${f.method === "llm_review" ? "LLM-reviewed" : "quote-verified"}</span></div>`).join("")}</div>` : ""}
        ${r.explanation ? `<div><h4>Evidence and reasoning</h4><div class="muted">${esc(r.explanation)}</div><div class="faint">Model explanation; contains no figures absent from the cited passages.</div></div>` : ""}
        ${r.conflicts?.length ? `<div class="callout warn"><b>${icon("alert", 15)} Conflicting provisions detected</b><ul>${r.conflicts.map((k) => `<li>${esc(k.kind)}: <b>${esc(k.value_a)}</b> (${esc(k.document_a)}, p.${k.pages_a.join(",")}${k.source_a ? ` <button class="cite" data-cite="${esc(k.source_a)}" data-quote="${esc(k.sentence_a)}">${esc(k.source_a)}</button>` : ""}) vs <b>${esc(k.value_b)}</b> (${esc(k.document_b)}, p.${k.pages_b.join(",")}${k.source_b ? ` <button class="cite" data-cite="${esc(k.source_b)}" data-quote="${esc(k.sentence_b)}">${esc(k.source_b)}</button>` : ""})${k.version_note ? `<div class="faint">${esc(k.version_note)}. The documents alone do not establish which provision prevails.</div>` : ""}</li>`).join("")}</ul></div>` : ""}
        ${r.limitations?.length ? `<div class="callout"><b>Limitations</b><ul>${r.limitations.map((l) => `<li>${esc(l)}</li>`).join("")}</ul></div>` : ""}
        <div class="faint">Confidence basis:<ul style="margin:4px 0 0;padding-left:18px">${confReasons}</ul></div>
        ${meta}
      </div></div>${diagnosticsHtml(r)}`;
  }
  hydrateIcons(area);
  area.querySelectorAll("[data-cite]").forEach((b) => (b.onclick = () => selectSource(c, r, b.dataset.cite, b.dataset.quote)));
  area.querySelectorAll("[data-diag-tab]").forEach((b) => (b.onclick = () => {
    area.querySelectorAll("[data-diag-tab]").forEach((x) => x.classList.toggle("active", x === b));
    area.querySelectorAll("[data-diag-panel]").forEach((p) => (p.hidden = p.dataset.diagPanel !== b.dataset.diagTab));
  }));
  // Default evidence: first cited source of the direct answer, else the top source.
  const first = r.direct_answer?.sources?.[0] || r.sources?.[0]?.source_id;
  if (!state.selected && first) selectSource(c, r, first, r.direct_answer?.quote || "");
  else drawViewer(c, r);
}

function rankTable(rows) {
  if (!rows?.length) return '<div class="faint">—</div>';
  return `<table class="mini-table"><thead><tr><th>#</th><th>Section</th><th>p.</th><th class="num">score</th></tr></thead><tbody>${rows.slice(0, 8).map((x) =>
    `<tr><td>${x.rank}</td><td class="ellipsis" style="max-width:160px" title="${esc(x.section)}">${esc((x.section || "").split("—")[0])}</td><td>${x.pages.join(",")}</td><td class="num">${fmt(x.score, 3)}</td></tr>`).join("")}</tbody></table>`;
}

function diagnosticsHtml(r) {
  const ret = r.retrieval || {};
  const all = [...(r.direct_answer ? [r.direct_answer] : []), ...(r.findings || []), ...(r.removed_claims || [])];
  const queries = ret.per_query || [];
  return `<details class="diag" style="margin-top:16px"><summary>${icon("cpu", 16)} Advanced diagnostics</summary><div class="diag-body">
    <div><b>Query plan:</b> ${esc(ret.plan?.strategy || "single")} ${ret.plan?.is_multi_hop ? `— ${ret.plan.sub_queries.length} sub-questions` : ""}
      ${ret.plan?.is_multi_hop ? `<ol style="margin:4px 0 0">${ret.plan.sub_queries.map((s, i) => `<li>${esc(s)} ${(r.coverage || [])[i] ? ((r.coverage[i].covered) ? '<span class="badge good">covered</span>' : '<span class="badge warn">not covered</span>') : ""}</li>`).join("")}</ol>` : ""}</div>
    ${queries.length > 1 ? `<div class="tabs">${queries.map((qq, i) => `<button type="button" data-diag-tab="${i}" class="${i === 0 ? "active" : ""}">${i === 0 ? "Full question" : `Sub-question ${i}`}</button>`).join("")}</div>` : ""}
    ${queries.map((qq, i) => `<div data-diag-panel="${i}" ${i ? "hidden" : ""}><div class="faint" style="margin-bottom:6px">${esc(qq.query)} · ${Object.entries(qq.timings || {}).map(([k, v]) => `${k.replace("_seconds", "")} ${fmt(v, 3)}s`).join(" · ")}</div>
      <div class="diag-grid"><div><b>BM25</b>${rankTable(qq.bm25)}</div><div><b>Dense (FAISS)</b>${rankTable(qq.dense)}</div><div><b>RRF fusion</b>${rankTable(qq.fused)}</div><div><b>Cross-encoder rerank</b>${rankTable(qq.reranked)}</div></div></div>`).join("")}
    <div><b>Context expansion:</b> ${(ret.context_chunk_ids || []).length} neighbouring passage(s) added as context sources.</div>
    <div><b>Claim verification</b><table class="mini-table"><thead><tr><th>Status</th><th>Method</th><th>Claim</th><th>Reason</th></tr></thead><tbody>${all.map((cl) =>
      `<tr><td><span class="badge ${cl.status === "SUPPORTED" ? "good" : cl.status === "CONTRADICTED" ? "bad" : "warn"}">${esc(cl.status)}</span></td><td>${esc(cl.method)}</td><td>${esc(cl.text)} <span class="faint">${esc(cl.sources.join(", "))}</span>${cl.citation_corrected_from ? `<div class="faint">citation corrected from ${esc(cl.citation_corrected_from.join(", "))}</div>` : ""}</td><td class="faint">${esc(cl.reason)}</td></tr>`).join("") || '<tr><td colspan="4" class="faint">No claims drafted.</td></tr>'}</tbody></table></div>
    <div><b>Verifier loop (${r.verification?.attempts || 0} attempt(s), cap ${(state.system?.grounding?.max_corrective_retries ?? 1) + 1})</b>${(r.verification?.retry_log || []).map((a) => `
      <div style="margin-top:6px"><div class="faint">Attempt ${a.attempt}${a.parse_error ? " — unparsable output" : ""}: ${a.failed_claims?.length || 0} failed claim(s)</div>
      ${a.failed_claims?.length ? `<ul style="margin:4px 0">${a.failed_claims.map((f) => `<li class="faint">${esc(f.status)}: ${esc(f.text)} — ${esc(f.reason)}</li>`).join("")}</ul>` : ""}
      ${a.corrective_prompt ? `<pre class="code">${esc(a.corrective_prompt)}</pre>` : ""}</div>`).join("")}</div>
    <div><b>Confidence signals</b><pre class="code">${esc(JSON.stringify(r.confidence?.signals || {}, null, 2))}</pre></div>
    ${r.abstention ? `<div><b>Abstention reason code:</b> ${esc(r.abstention.reason_code)}</div>` : ""}
  </div></details>`;
}

function selectSource(c, r, sourceId, quote) {
  const s = r.sources.find((x) => x.source_id === sourceId);
  if (!s) return;
  state.selected = { sourceId, quote: quote || "" };
  state.viewer = { docId: s.document_id, page: s.pages[0] };
  document.querySelectorAll(".cite").forEach((b) => b.classList.toggle("active", b.dataset.cite === sourceId));
  drawViewer(c, r);
}

function drawViewer(c, r) {
  const el = $("#viewer");
  if (!el) return;
  const sources = r?.sources || [];
  const cited = new Set([...(r?.direct_answer?.sources || []), ...(r?.findings || []).flatMap((f) => f.sources)]);
  const sel = state.selected ? sources.find((s) => s.source_id === state.selected.sourceId) : null;
  if (!state.viewer) state.viewer = { docId: c.documents[0]?.document_id, page: 1 };
  const doc = c.documents.find((d) => d.document_id === state.viewer.docId) || c.documents[0];
  const page = state.viewer.page;
  const onSourcePage = sel && sel.document_id === doc.document_id && sel.pages.includes(page);

  let passage = "";
  if (sel) {
    // Join PDF line breaks inside paragraphs; keep blank-line paragraph breaks.
    const text = sel.text.replace(/[ \t]*\n(?!\n)[ \t]*/g, " ");
    passage = esc(text);
    const quote = (state.selected.quote || "").trim().replace(/^["'“]|["'”.;:,]$/g, "");
    if (quote) {
      const escapeRe = (w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const pattern = new RegExp(quote.split(/\s+/).map(escapeRe).join("\\s+"), "i");
      const m = text.match(pattern);
      if (m) passage = esc(text.slice(0, m.index)) + `<mark>${esc(m[0])}</mark>` + esc(text.slice(m.index + m[0].length));
    }
  }

  el.innerHTML = `
    ${sources.length ? `<div class="src-tabs" role="tablist" aria-label="Retrieved sources">${sources.map((s) => `<button type="button" role="tab" class="src-tab ${sel?.source_id === s.source_id ? "active" : ""} ${cited.has(s.source_id) ? "cited" : ""}" data-src="${esc(s.source_id)}" title="${esc(s.section || "")}"><b>${esc(s.source_id)}</b>${esc(sectionName(s.section).split("—")[0].trim())} · p.${s.pages.join(",")}</button>`).join("")}</div>` : ""}
    ${sel ? `<div class="src-meta">
        <div class="title">${esc(sectionName(sel.section))}</div>
        <div class="meta-row"><span>${icon("file", 13)} <b>${esc(sel.file_name)}</b></span><span>page <b>${sel.pages.join(", ")}</b></span>
          ${sel.clause_ids?.length ? `<span>clause <b>${esc(sel.clause_ids.slice(0, 4).join(", "))}</b></span>` : ""}
          ${sel.score !== null ? `<span>rerank <b>${fmt(sel.score, 2)}</b></span>` : `<span class="badge">context</span>`}
          ${sel.chunk_type === "table" ? '<span class="badge info">table</span>' : ""}${sel.extraction_method === "ocr" ? '<span class="badge warn">OCR text</span>' : ""}
          ${cited.has(sel.source_id) ? '<span class="badge good">cited</span>' : '<span class="badge">retrieved, not cited</span>'}</div></div>
      <div class="passage" aria-label="Extracted passage">${passage}</div>`
    : `<div class="src-meta"><div class="title">Evidence viewer</div><div class="faint">${sources.length ? "Select a citation or a source above." : "Ask a question. The cited page of the original PDF appears here, with the supporting passage highlighted."}</div></div>`}
    <div class="page-bar">
      <select id="v-doc" aria-label="Document">${c.documents.map((d) => `<option value="${esc(d.document_id)}" ${d.document_id === doc.document_id ? "selected" : ""}>${esc(d.file_name)}</option>`).join("")}</select>
      <button class="btn sm" id="v-prev" ${page <= 1 ? "disabled" : ""} aria-label="Previous page">${icon("left", 15)}</button>
      <span class="faint">Page <input id="v-page" type="text" inputmode="numeric" value="${page}" style="width:52px;padding:4px 6px;text-align:center" aria-label="Page number"/> / ${doc.pages || "?"}</span>
      <button class="btn sm" id="v-next" ${doc.pages && page >= doc.pages ? "disabled" : ""} aria-label="Next page">${icon("right", 15)}</button>
      <div class="spacer" style="flex:1"></div>
      ${onSourcePage ? `<span class="badge info">${icon("eye", 12)} highlighted</span>` : ""}
      <a class="btn sm ghost" href="/api/cases/${encodeURIComponent(c.id)}/documents/${encodeURIComponent(doc.document_id)}/file#page=${page}" target="_blank" rel="noopener" title="Open PDF">${icon("external", 15)}</a>
    </div>
    <div class="page-stage"><div class="page-frame" id="page-frame" style="max-width:760px">
      <img id="page-img" alt="Page ${page} of ${esc(doc.file_name)}" src="/api/cases/${encodeURIComponent(c.id)}/documents/${encodeURIComponent(doc.document_id)}/pages/${page}/image"/>
    </div></div>`;
  hydrateIcons(el);
  el.querySelectorAll("[data-src]").forEach((b) => (b.onclick = () => {
    const s = sources.find((x) => x.source_id === b.dataset.src);
    const claim = [r.direct_answer, ...(r.findings || [])].find((cl) => cl && cl.sources.includes(s.source_id));
    selectSource(c, r, s.source_id, claim?.quote || "");
  }));
  const go = (docId, p) => { state.viewer = { docId, page: Math.max(1, Math.min(p, (c.documents.find((d) => d.document_id === docId)?.pages) || p)) }; drawViewer(c, r); };
  $("#v-doc").onchange = (e) => go(e.target.value, 1);
  $("#v-prev").onclick = () => go(doc.document_id, page - 1);
  $("#v-next").onclick = () => go(doc.document_id, page + 1);
  $("#v-page").onchange = (e) => { const n = parseInt(e.target.value, 10); if (n > 0) go(doc.document_id, n); };
  if (onSourcePage) drawHighlights(c, sel, page);
}

async function drawHighlights(c, sel, page) {
  const params = new URLSearchParams({ chunk_id: sel.chunk_id });
  if (state.selected?.quote) params.set("quote", state.selected.quote);
  try {
    const h = await api(`/api/cases/${encodeURIComponent(c.id)}/documents/${encodeURIComponent(sel.document_id)}/pages/${page}/highlights?${params}`);
    const frame = $("#page-frame");
    if (!frame || state.viewer?.page !== page) return;
    const box = (r, cls) => {
      const d = document.createElement("div");
      d.className = `hl ${cls}`;
      Object.assign(d.style, { left: `${(r[0] / h.width) * 100}%`, top: `${(r[1] / h.height) * 100}%`, width: `${((r[2] - r[0]) / h.width) * 100}%`, height: `${((r[3] - r[1]) / h.height) * 100}%` });
      frame.append(d);
    };
    h.passage.rects.forEach((r) => box(r, ""));
    h.quote.rects.forEach((r) => box(r, "quote"));
    const first = h.quote.rects[0] || h.passage.rects[0];
    if (first) {
      const img = $("#page-img");
      const scroll = () => { const stage = frame.parentElement; stage.scrollTop = Math.max(0, (first[1] / h.height) * img.clientHeight - 60); };
      if (img.complete) scroll(); else img.onload = scroll;
    }
  } catch { /* highlighting is best effort; the page and passage are still shown */ }
}

// ------------------------------------------------------------------ evaluation
const MODE_LABELS = { dense: "Dense only (FAISS)", bm25: "BM25 only", hybrid: "Hybrid RRF", hybrid_rerank: "Hybrid + cross-encoder" };
const MODE_COLORS = { dense: "var(--series-1)", bm25: "var(--series-2)", hybrid: "var(--series-3)", hybrid_rerank: "var(--series-4)" };

function recallChart(variant) {
  const modes = Object.keys(MODE_LABELS);
  const ks = ["1", "3", "5", "10"];
  const W = 640, H = 260, L = 40, B = 34, T = 12, R = 8;
  const plotW = W - L - R, plotH = H - T - B;
  const groupW = plotW / ks.length;
  const barW = Math.min(26, (groupW - 24) / modes.length - 2);
  let bars = "";
  ks.forEach((k, gi) => {
    modes.forEach((m, mi) => {
      const v = variant[m]?.recall_at_k?.[k] ?? 0;
      const h = v * plotH;
      const x = L + gi * groupW + (groupW - (barW + 2) * modes.length) / 2 + mi * (barW + 2);
      const y = T + plotH - h;
      const r = Math.min(4, h / 2);
      bars += `<path class="bar" fill="${MODE_COLORS[m]}" d="M${x},${T + plotH} V${y + r} Q${x},${y} ${x + r},${y} H${x + barW - r} Q${x + barW},${y} ${x + barW},${y + r} V${T + plotH} Z" data-tip="${esc(MODE_LABELS[m])} · Recall@${k} = ${pct(v, 0)}"/>`;
      bars += `<rect x="${x - 1}" y="${T}" width="${barW + 2}" height="${plotH}" fill="transparent" data-tip="${esc(MODE_LABELS[m])} · Recall@${k} = ${pct(v, 0)}"/>`;
    });
  });
  const grid = [0, 0.25, 0.5, 0.75, 1].map((g) => `<line class="grid-line" x1="${L}" x2="${W - R}" y1="${T + plotH - g * plotH}" y2="${T + plotH - g * plotH}"/><text x="${L - 6}" y="${T + plotH - g * plotH + 4}" text-anchor="end">${g * 100}%</text>`).join("");
  const labels = ks.map((k, gi) => `<text x="${L + gi * groupW + groupW / 2}" y="${H - 12}" text-anchor="middle">Recall@${k}</text>`).join("");
  return `<div class="legend" style="margin-bottom:8px">${modes.map((m) => `<span><i style="background:${MODE_COLORS[m]}"></i>${MODE_LABELS[m]}</span>`).join("")}</div>
    <div class="chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Recall at k by retrieval configuration">${grid}<line class="axis" x1="${L}" x2="${W - R}" y1="${T + plotH}" y2="${T + plotH}"/>${bars}${labels}</svg></div>`;
}

function bindTooltips(root) {
  const tip = $("#tooltip");
  root.querySelectorAll("[data-tip]").forEach((el) => {
    el.addEventListener("mousemove", (e) => { tip.hidden = false; tip.textContent = el.dataset.tip; tip.style.left = `${e.clientX + 12}px`; tip.style.top = `${e.clientY + 12}px`; });
    el.addEventListener("mouseleave", () => { tip.hidden = true; });
  });
}

async function renderEvaluation(view) {
  const data = await api("/api/evaluation");
  const s = data.summary;
  if (!s) {
    view.innerHTML = `<div class="card card-pad empty"><div class="ico">${icon("chart", 32)}</div><h3>No evaluation results yet</h3><p>Run <code>python scripts/evaluate.py --generate</code> to produce real metrics. Nothing is shown until they exist.</p></div>`;
    return;
  }
  const variantKey = store.get("lexisync-eval-variant", "contextual_headers");
  const variant = s.retrieval[variantKey] || s.retrieval.contextual_headers;
  const hr = variant.hybrid_rerank, dn = variant.dense;
  const g = s.generation;
  const m = data.manual;
  const card = (label, value, note, cls = "") => `<div class="card kpi"><div class="label">${label}</div><div class="value ${cls}">${value}</div><div class="metric-note">${note}</div></div>`;
  const manualPending = !m.scored_correctness;

  view.innerHTML = `
    <div class="card card-pad" style="margin-bottom:16px"><div class="row">
      <div style="flex:1;min-width:260px"><b>Dataset:</b> ${data.dataset.questions} held-out questions on ${esc(data.dataset.document)}: ${data.dataset.factual} factual, ${data.dataset.multi_hop} multi-hop (two provisions on different pages), ${data.dataset.unanswerable} unanswerable.
        <div class="faint">Results generated ${esc(s.generated_at)} by <code>scripts/evaluate.py</code>. Automated metrics are computed; manual metrics are marked as such.</div></div>
      <div class="tabs" role="tablist" aria-label="Index variant">
        <button type="button" data-variant="contextual_headers" class="${variantKey === "contextual_headers" ? "active" : ""}">Contextual headers (default)</button>
        <button type="button" data-variant="plain_text" class="${variantKey === "plain_text" ? "active" : ""}">Plain chunks (ablation)</button></div></div></div>
    <div class="grid kpis" style="margin-bottom:16px">
      ${card("Recall@5 · hybrid + rerank", pct(hr.recall_at_k["5"]), `dense-only ${pct(dn.recall_at_k["5"])} · automated`)}
      ${card("Recall@1 · hybrid + rerank", pct(hr.recall_at_k["1"]), `dense-only ${pct(dn.recall_at_k["1"])} · automated`)}
      ${card("MRR · hybrid + rerank", fmt(hr.mrr, 2), `dense-only ${fmt(dn.mrr, 2)} · automated`)}
      ${g ? card("Abstention accuracy", pct(g.abstention_accuracy), `${g.evaluated} questions · automated`) : card("Abstention accuracy", "—", "run with --generate", "pending")}
      ${g ? card("False abstention rate", pct(g.false_abstention_rate), `${g.false_abstentions} answerable question(s) refused`) : ""}
      ${g ? card("Citation precision (auto proxy)", pct(g.citation_section_precision), "cited passage in an expected provision") : ""}
      ${card("Answer correctness", manualPending ? "Pending" : pct(m.answer_correctness), manualPending ? "manual scoring not yet entered" : `manual · ${m.scored_correctness} scored`, manualPending ? "pending" : "")}
      ${card("Citation precision (manual)", m.citation_precision == null ? "Pending" : pct(m.citation_precision), "manual scoring sheet", m.citation_precision == null ? "pending" : "")}
      ${g ? card("End-to-end latency", `${fmt(g.latency_total.mean, 1)} s`, `median ${fmt(g.latency_total.median, 1)} s · p95 ${fmt(g.latency_total.p95, 1)} s`) : ""}
    </div>
    <div class="grid two" style="margin-bottom:16px">
      <div class="card card-pad"><h2>Mandatory comparison: Recall@k by retrieval configuration</h2>${recallChart(variant)}</div>
      <div class="card card-pad"><h2>Retrieval ablation table</h2><div class="table-wrap"><table class="data">
        <thead><tr><th>Configuration</th><th class="num">R@1</th><th class="num">R@3</th><th class="num">R@5</th><th class="num">R@10</th><th class="num">MRR</th><th class="num">Multi-hop full R@5</th><th class="num">Latency</th></tr></thead>
        <tbody>${Object.keys(MODE_LABELS).map((k) => { const v = variant[k]; return `<tr><td><i style="display:inline-block;width:10px;height:10px;border-radius:3px;background:${MODE_COLORS[k]};margin-right:6px"></i>${MODE_LABELS[k]}</td>${["1", "3", "5", "10"].map((x) => `<td class="num">${pct(v.recall_at_k[x])}</td>`).join("")}<td class="num">${fmt(v.mrr, 2)}</td><td class="num">${pct(v.multi_hop_full_recall_at_k["5"])}</td><td class="num">${fmt(v.latency.mean * 1000, 0)} ms</td></tr>`; }).join("")}
        <tr><td>Planner multi-hop (system)</td><td colspan="5" class="faint">per-sub-question retrieval, merged evidence (~${fmt(variant.planner_multi_hop.mean_evidence_size, 1)} passages)</td><td class="num">${pct(variant.planner_multi_hop.multi_hop_full_recall)}</td><td class="num">${fmt(variant.planner_multi_hop.latency.mean * 1000, 0)} ms</td></tr>
        </tbody></table></div><div class="faint" style="margin-top:8px">Relevance = retrieved passage belongs to an expected article (word-boundary match). Recall over ${data.dataset.factual + data.dataset.multi_hop} answerable questions.</div></div>
    </div>
    ${g ? `<div class="grid two" style="margin-bottom:16px">
      <div class="card card-pad"><h2>Generation &amp; grounding</h2><dl class="kv">
        <dt>Model</dt><dd>${esc(g.model)}</dd>
        <dt>Correct abstentions (unanswerable)</dt><dd>${pct(g.correct_abstentions_on_unanswerable)}</dd>
        <dt>Unsupported answer rate</dt><dd>${pct(g.unsupported_answer_rate)}</dd>
        <dt>Expected provisions cited</dt><dd>${pct(g.expected_provisions_cited)} (multi-hop ${pct(g.multi_hop_expected_provisions_cited)})</dd>
        <dt>Citation coverage of shown claims</dt><dd>${pct(g.citation_coverage)}</dd>
        <dt>Claim verification pass rate</dt><dd>${pct(g.claim_verification_pass_rate)}</dd>
        <dt>Questions needing a corrective retry</dt><dd>${g.questions_needing_retry}</dd>
        <dt>Confidence distribution</dt><dd>${Object.entries(g.confidence_distribution).map(([k, v]) => `${k} ${v}`).join(" · ")}</dd></dl></div>
      <div class="card card-pad"><h2>Latency &amp; cost per question</h2><table class="data"><thead><tr><th>Stage</th><th class="num">Mean</th><th class="num">Median</th><th class="num">p95</th></tr></thead><tbody>
        ${[["Retrieval", g.latency_retrieval], ["Generation + verification", g.latency_generation], ["End-to-end", g.latency_total]].map(([n, l]) => `<tr><td>${n}</td><td class="num">${fmt(l.mean, 2)} s</td><td class="num">${fmt(l.median, 2)} s</td><td class="num">${fmt(l.p95, 2)} s</td></tr>`).join("")}
        </tbody></table><div class="faint" style="margin-top:8px">Mean ${fmt(g.mean_llm_calls, 1)} LLM calls, ${fmt(g.mean_prompt_tokens, 0)} prompt + ${fmt(g.mean_completion_tokens, 0)} completion tokens per question (local inference, no API cost).</div></div>
    </div>` : ""}
    ${data.generation ? `<div class="card card-pad" style="margin-bottom:16px"><h2>Per-question results</h2><div class="table-wrap"><table class="data">
      <thead><tr><th>ID</th><th>Type</th><th>Question</th><th>Outcome</th><th>Confidence</th><th class="num">Claims</th><th>Cited</th><th class="num">Time</th></tr></thead>
      <tbody>${data.generation.map((x) => `<tr><td>${esc(x.id)}</td><td><span class="badge">${esc(x.type)}</span></td><td style="max-width:360px">${esc(x.question || "")}</td>
        <td>${x.abstained === null ? '<span class="badge bad">error</span>' : x.abstained === !x.answerable ? `<span class="badge good">${x.abstained ? "correct abstention" : "answered"}</span>` : `<span class="badge bad">${x.abstained ? "false abstention" : "answered unanswerable"}</span>`}</td>
        <td><span class="conf ${esc(x.confidence)}" style="padding:2px 8px;font-size:11px">${esc(x.confidence || "—")}</span></td>
        <td class="num">${x.claims_shown ?? "—"}${x.claims_removed ? ` <span class="faint">(−${x.claims_removed})</span>` : ""}</td>
        <td class="faint">${esc((x.cited_sources || []).map((c) => `${(c.section || "").split("—")[0].trim()} p.${c.pages.join(",")}`).filter((v, i, a) => a.indexOf(v) === i).join("; "))}</td>
        <td class="num">${fmt(x.total_seconds, 1)} s</td></tr>`).join("")}</tbody></table></div></div>` : ""}
    <div class="grid two">
      <div class="card card-pad"><h2>Failure analysis</h2>${failureList(data, variantKey)}</div>
      <div class="card card-pad"><h2>Abstention gate calibration</h2>${data.calibration ? `<dl class="kv">
        <dt>Calibration set</dt><dd>${esc(data.calibration.dev_set)} (separate from the held-out set)</dd>
        <dt>Lowest answerable score</dt><dd>${fmt(data.calibration.min_answerable, 2)}</dd>
        <dt>Highest unanswerable score</dt><dd>${fmt(data.calibration.max_unanswerable, 2)}</dd>
        <dt>Configured gate</dt><dd>${fmt(s.evidence_gate.configured_threshold, 2)} (cross-encoder logit; sigmoid = 0.5)</dd>
        <dt>Held-out gate-only accuracy</dt><dd>${pct(s.evidence_gate.held_out_gate_only.abstention_accuracy)}</dd></dl>
        <div class="faint" style="margin-top:8px">Manual scoring sheet: ${m.rows} rows, ${m.scored_correctness} scored for correctness, ${m.scored_citations} for citations (evaluation/manual_scoring_template.csv).</div>` : "—"}</div>
    </div>`;
  view.querySelectorAll("[data-variant]").forEach((b) => (b.onclick = () => { store.set("lexisync-eval-variant", b.dataset.variant); router(); }));
  bindTooltips(view);
}

function failureList(data, variantKey) {
  const items = [];
  const rows = data.retrieval_rows?.[variantKey]?.hybrid_rerank || [];
  rows.filter((r) => r.answerable && r["hit@1"] === 0).forEach((r) => items.push(`<li><b>${esc(r.id)}</b>: expected provision not ranked first by hybrid + rerank (top-1 was ${esc((r.top5[0]?.section || "").split("—")[0])}); found by rank ${r.rr ? Math.round(1 / r.rr) : ">10"}.</li>`));
  (data.generation || []).forEach((x) => {
    if (x.abstained === null) items.push(`<li><b>${esc(x.id)}</b>: generation error.</li>`);
    else if (x.answerable && x.abstained) items.push(`<li><b>${esc(x.id)}</b>: false abstention — ${esc(x.abstention_reason || "")}</li>`);
    else if (!x.answerable && !x.abstained) items.push(`<li><b>${esc(x.id)}</b>: answered an unanswerable question.</li>`);
    else if (x.claims_removed) items.push(`<li><b>${esc(x.id)}</b>: ${x.claims_removed} drafted claim(s) removed by verification.</li>`);
  });
  return items.length ? `<ul style="margin:0;padding-left:18px;display:flex;flex-direction:column;gap:6px">${items.join("")}</ul>` : '<div class="faint">No failures recorded.</div>';
}

// ------------------------------------------------------------------ settings
async function renderSettings(view) {
  await refreshSystem();
  const s = state.system;
  if (!s) throw new Error("The backend is not reachable.");
  const o = s.ollama;
  const theme = document.documentElement.dataset.theme === "light" ? "light" : "dark";
  const kv = (obj) => `<dl class="kv">${Object.entries(obj).map(([k, v]) => `<dt>${esc(k.replaceAll("_", " "))}</dt><dd>${esc(v)}</dd>`).join("")}</dl>`;
  view.innerHTML = `<div class="grid two">
    <div class="card card-pad"><div class="card-head"><h2>Local LLM (Ollama)</h2><div class="spacer"></div><button class="btn sm" id="ref">${icon("refresh", 15)} Check again</button></div>
      <dl class="kv"><dt>Status</dt><dd><span class="badge ${o.connected && o.model_available ? "good" : "bad"}">${o.connected ? (o.model_available ? "Connected, model available" : "Connected, model not pulled") : "Not reachable"}</span></dd>
      <dt>Endpoint</dt><dd>${esc(o.base_url)}</dd><dt>Configured model</dt><dd>${esc(o.model)}</dd>
      <dt>Installed models</dt><dd>${esc((o.available_models || []).join(", ") || "—")}</dd>
      ${o.error ? `<dt>Error</dt><dd>${esc(o.error)}</dd>` : ""}</dl>
      ${!o.model_available ? `<div class="callout warn" style="margin-top:12px">Run <code>ollama pull ${esc(o.model)}</code> in a terminal, then check again. The model is configured with <code>OLLAMA_MODEL</code> in <code>.env</code>.</div>` : ""}</div>
    <div class="card card-pad"><h2>Models</h2>${kv(s.models)}</div>
    <div class="card card-pad"><h2>Retrieval parameters</h2>${kv(s.retrieval)}<div class="faint" style="margin-top:8px">Set in <code>.env</code> (see <code>.env.example</code>); restart to apply. Chunking changes require re-indexing.</div></div>
    <div class="card card-pad"><h2>Grounding &amp; abstention</h2>${kv(s.grounding)}<div class="faint" style="margin-top:8px">The evidence gate is a cross-encoder logit calibrated on a separate dev set (see Evaluation).</div></div>
    <div class="card card-pad"><h2>OCR</h2>${kv({ mode: s.ocr.mode, tesseract: s.ocr.tesseract_found ? "found" : "not found" })}</div>
    <div class="card card-pad"><h2>Appearance</h2><div class="tabs" role="radiogroup" aria-label="Theme">
      <button type="button" data-theme-set="dark" class="${theme === "dark" ? "active" : ""}">${icon("moon", 14)} Dark</button>
      <button type="button" data-theme-set="light" class="${theme === "light" ? "active" : ""}">${icon("sun", 14)} Light</button></div>
      <div class="faint" style="margin-top:12px">LexiSyncAI v${esc(s.version)} · local, private: documents never leave this machine.</div></div>
  </div>`;
  $("#ref").onclick = router;
  view.querySelectorAll("[data-theme-set]").forEach((b) => (b.onclick = () => { setTheme(b.dataset.themeSet); router(); }));
}

// ------------------------------------------------------------------ boot
function setTheme(theme) {
  if (theme === "light") document.documentElement.dataset.theme = "light"; else delete document.documentElement.dataset.theme;
  try { localStorage.setItem("lexisync-theme", theme); } catch { /* ignore */ }
  $("#theme-toggle").innerHTML = icon(theme === "light" ? "sun" : "moon", 18);
}

function boot() {
  hydrateIcons();
  document.querySelectorAll("#nav button").forEach((b) => (b.onclick = () => navigate(b.dataset.route)));
  $("#theme-toggle").onclick = () => setTheme(document.documentElement.dataset.theme === "light" ? "dark" : "light");
  setTheme(document.documentElement.dataset.theme === "light" ? "light" : "dark");
  const collapsed = store.get("lexisync-collapsed", false);
  $("#app").classList.toggle("collapsed", collapsed);
  $("#collapse-toggle").onclick = () => { const v = !$("#app").classList.contains("collapsed"); $("#app").classList.toggle("collapsed", v); store.set("lexisync-collapsed", v); };
  window.addEventListener("hashchange", router);
  refreshSystem();
  setInterval(refreshSystem, 30000);
  refreshCases().catch(() => {}).finally(router);
}

boot();
