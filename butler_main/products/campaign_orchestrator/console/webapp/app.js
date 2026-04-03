const LOCAL_STORAGE_KEYS = {
  theme: "butler-console-theme",
  timelineCollapsed: "butler-console-timeline-collapsed",
};

const STATUS_PRIORITY = ["running", "current", "next", "queued", "pending", "completed", "blocked", "failed", "unknown"];
const VIEWPORT_ANIMATION_MS = 420;

const state = {
  workspace: ".",
  autoRefresh: true,
  runtime: null,
  campaigns: [],
  drafts: [],
  skillCollections: [],
  skillDiagnostics: null,
  skillCollectionDetail: null,
  selection: { scope: "global", id: "" },
  campaignDetail: null,
  graph: null,
  board: null,
  globalBoard: null,
  events: [],
  selectedNodeId: "",
  selectedArtifactId: "",
  selectedRecordId: "",
  preview: null,
  boardMode: "graph",
  rightTab: "runtime",
  view: { scale: 1, x: 40, y: 40 },
  layout: null,
  timer: null,
  viewStateByScope: {},
  pendingViewportAction: null,
  timelineCollapsed: true,
  timelineScrollLeft: 0,
  selectedTimelineItemId: "",
  viewportAnimationTimer: null,
  timelineDragActive: false,
  pendingRefresh: false,
  agentDetailOpen: false,
  agentDetailCampaignId: "",
  agentDetailNodeId: "",
  agentDetailTab: "records",
  agentDetailScrollTop: 0,
  agentDetailData: null,
  agentDetailStale: false,
};

const elements = {
  workspaceForm: document.querySelector("#workspace-form"),
  workspaceInput: document.querySelector("#workspace-input"),
  autoRefreshInput: document.querySelector("#autorefresh-input"),
  runtimeBadge: document.querySelector("#runtime-badge"),
  refreshAllButton: document.querySelector("#refresh-all-button"),
  refreshEventsButton: document.querySelector("#refresh-events-button"),
  toggleTimelineButton: document.querySelector("#toggle-timeline-button"),
  timelineDrawer: document.querySelector("#timeline-drawer"),
  globalItem: document.querySelector("#global-item"),
  projectList: document.querySelector("#project-list"),
  agentSummary: document.querySelector("#agent-summary"),
  agentList: document.querySelector("#agent-list"),
  boardTitle: document.querySelector("#board-title"),
  boardSubtitle: document.querySelector("#board-subtitle"),
  boardModeToggle: document.querySelector("#board-mode-toggle"),
  boardGraph: document.querySelector("#board-graph"),
  boardPreview: document.querySelector("#board-preview"),
  graphEmpty: document.querySelector("#graph-empty"),
  canvas: document.querySelector("#canvas"),
  canvasTransform: document.querySelector("#canvas-transform"),
  edgeLayer: document.querySelector("#edge-layer"),
  nodeLayer: document.querySelector("#node-layer"),
  zoomOut: document.querySelector("#zoom-out"),
  zoomIn: document.querySelector("#zoom-in"),
  zoomFit: document.querySelector("#zoom-fit"),
  previewPane: document.querySelector("#preview-pane"),
  eventsList: document.querySelector("#events-list"),
  rightTabs: document.querySelector("#right-tabs"),
  tabArtifacts: document.querySelector("#tab-artifacts"),
  tabDocs: document.querySelector("#tab-docs"),
  tabSkills: document.querySelector("#tab-skills"),
  tabRuntime: document.querySelector("#tab-runtime"),
  artifactList: document.querySelector("#artifact-list"),
  docsPanel: document.querySelector("#docs-panel"),
  skillsPanel: document.querySelector("#skills-panel"),
  runtimePanel: document.querySelector("#runtime-panel"),
  themeButtons: Array.from(document.querySelectorAll(".theme-button")),
  agentDetailOverlay: document.querySelector("#agent-detail-overlay"),
  agentDetailBackdrop: document.querySelector("#agent-detail-backdrop"),
  agentDetailClose: document.querySelector("#agent-detail-close"),
  agentDetailTitle: document.querySelector("#agent-detail-title"),
  agentDetailSubtitle: document.querySelector("#agent-detail-subtitle"),
  agentDetailStatusRow: document.querySelector("#agent-detail-status-row"),
  agentDetailOverview: document.querySelector("#agent-detail-overview"),
  agentDetailTabs: document.querySelector("#agent-detail-tabs"),
  agentDetailScroll: document.querySelector("#agent-detail-scroll"),
  agentDetailRecords: document.querySelector("#agent-detail-records"),
  agentDetailPlanned: document.querySelector("#agent-detail-planned"),
  agentDetailArtifacts: document.querySelector("#agent-detail-artifacts"),
  agentDetailRaw: document.querySelector("#agent-detail-raw"),
};

function apiUrl(path, query = {}) {
  const url = new URL(path, window.location.origin);
  url.searchParams.set("workspace", state.workspace);
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  });
  return url.toString();
}

async function fetchJsonOptional(path, options = {}, query = {}) {
  try {
    const response = await fetch(apiUrl(path, query), {
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
      ...options,
    });
    if (response.status === 404) {
      return null;
    }
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      return null;
    }
    return payload;
  } catch (error) {
    return null;
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeHtmlAttr(value) {
  return escapeHtml(value).replaceAll("`", "&#96;");
}

function detailButtonIcon() {
  return `
    <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false">
      <path d="M7 3H3v4M13 3h4v4M17 13v4h-4M7 17H3v-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"></path>
    </svg>
  `;
}

function cloneData(value) {
  if (value === null || value === undefined) {
    return value;
  }
  try {
    return JSON.parse(JSON.stringify(value));
  } catch (error) {
    return value;
  }
}

function normalizeStatus(value) {
  const raw = String(value || "").toLowerCase();
  if (!raw) {
    return "unknown";
  }
  if (["running", "current", "active"].includes(raw)) {
    return raw === "current" ? "current" : "running";
  }
  if (["next", "up_next"].includes(raw)) {
    return "next";
  }
  if (["queued", "pending", "waiting"].includes(raw)) {
    return raw === "pending" ? "pending" : "queued";
  }
  if (["completed", "done", "success"].includes(raw)) {
    return "completed";
  }
  if (["blocked", "failed", "error"].includes(raw)) {
    return raw === "failed" ? "failed" : "blocked";
  }
  return raw;
}

function detailExecutionStateLabel(value) {
  const stateValue = String(value || "").toLowerCase();
  if (stateValue === "running") {
    return "Running";
  }
  if (stateValue === "pending") {
    return "Pending";
  }
  if (stateValue === "completed") {
    return "Completed";
  }
  return "Idle/Unknown";
}

function sortByStatus(items) {
  return [...items].sort((a, b) => {
    const aIndex = STATUS_PRIORITY.indexOf(normalizeStatus(a.status));
    const bIndex = STATUS_PRIORITY.indexOf(normalizeStatus(b.status));
    return (aIndex === -1 ? 99 : aIndex) - (bIndex === -1 ? 99 : bIndex);
  });
}

function defaultRightTab(scope) {
  return scope === "global" ? "runtime" : "artifacts";
}

function scopeKey(scope = state.selection.scope, id = state.selection.id) {
  return scope === "global" ? "global" : `campaign:${id || ""}`;
}

function defaultScopeState(scope = state.selection.scope) {
  return {
    boardMode: "graph",
    rightTab: defaultRightTab(scope),
    selectedNodeId: "",
    selectedArtifactId: "",
    selectedRecordId: "",
    preview: null,
    view: { scale: 1, x: 40, y: 40 },
    viewCustomized: false,
    timelineScrollLeft: 0,
    selectedTimelineItemId: "",
    initialized: false,
  };
}

function getTimelineViewport() {
  return elements.eventsList?.querySelector("[data-timeline-viewport]") || null;
}

function getScopeState(scope = state.selection.scope, id = state.selection.id) {
  const key = scopeKey(scope, id);
  if (!state.viewStateByScope[key]) {
    state.viewStateByScope[key] = defaultScopeState(scope);
  }
  return state.viewStateByScope[key];
}

function syncCurrentScopeState() {
  const slot = getScopeState();
  slot.boardMode = state.boardMode;
  slot.rightTab = state.rightTab;
  slot.selectedNodeId = state.selectedNodeId;
  slot.selectedArtifactId = state.selectedArtifactId;
  slot.selectedRecordId = state.selectedRecordId;
  slot.preview = cloneData(state.preview);
  slot.view = cloneData(state.view);
  slot.timelineScrollLeft = getTimelineViewport()?.scrollLeft ?? state.timelineScrollLeft ?? 0;
  slot.selectedTimelineItemId = state.selectedTimelineItemId;
  slot.initialized = true;
}

function markViewCustomized() {
  const slot = getScopeState();
  slot.viewCustomized = true;
  slot.view = cloneData(state.view);
}

function applyScopeState(scope, id, defaults = {}) {
  const slot = getScopeState(scope, id);
  state.boardMode = slot.boardMode || "graph";
  state.rightTab = slot.rightTab || defaultRightTab(scope);
  state.selectedNodeId = slot.selectedNodeId || defaults.selectedNodeId || "";
  state.selectedArtifactId = slot.selectedArtifactId || defaults.selectedArtifactId || "";
  state.selectedRecordId = slot.selectedRecordId || defaults.selectedRecordId || "";
  state.preview = cloneData(slot.preview) || null;
  state.view = cloneData(slot.view) || { scale: 1, x: 40, y: 40 };
  state.timelineScrollLeft = Number(slot.timelineScrollLeft || 0);
  state.selectedTimelineItemId = slot.selectedTimelineItemId || "";
}

function loadTheme() {
  const saved = localStorage.getItem(LOCAL_STORAGE_KEYS.theme) || "auto";
  setTheme(saved);
}

function setTheme(theme) {
  const safeTheme = ["auto", "day", "night"].includes(theme) ? theme : "auto";
  document.documentElement.setAttribute("data-theme", safeTheme);
  localStorage.setItem(LOCAL_STORAGE_KEYS.theme, safeTheme);
  elements.themeButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.theme === safeTheme);
  });
}

function loadTimelinePreference() {
  const saved = localStorage.getItem(LOCAL_STORAGE_KEYS.timelineCollapsed);
  state.timelineCollapsed = saved === null ? true : saved === "true";
  applyTimelineState();
}

function applyTimelineState() {
  elements.timelineDrawer.classList.toggle("collapsed", state.timelineCollapsed);
  elements.toggleTimelineButton.textContent = state.timelineCollapsed ? "▲" : "▼";
  elements.toggleTimelineButton.setAttribute("aria-expanded", String(!state.timelineCollapsed));
}

function setTimelineCollapsed(collapsed) {
  state.timelineCollapsed = Boolean(collapsed);
  localStorage.setItem(LOCAL_STORAGE_KEYS.timelineCollapsed, String(state.timelineCollapsed));
  applyTimelineState();
}

function extractGraph() {
  if (state.selection.scope === "global" && state.globalBoard?.nodes) {
    return {
      nodes: state.globalBoard.nodes || [],
      edges: state.globalBoard.edges || [],
      inspector_defaults: state.globalBoard.preview_defaults || {},
    };
  }
  if (state.board?.nodes) {
    return {
      nodes: state.board.nodes || [],
      edges: state.board.edges || [],
      inspector_defaults: state.board.preview_defaults || {},
    };
  }
  if (state.board?.graph) {
    return state.board.graph;
  }
  return state.graph;
}

function extractArtifacts() {
  const artifacts = [];
  const pushArtifact = (artifact) => {
    if (!artifact) {
      return;
    }
    const id = artifact.id || artifact.artifact_id || artifact.ref || artifact.name;
    if (!id || artifacts.find((item) => item.id === id)) {
      return;
    }
    artifacts.push({
      id,
      title: artifact.title || artifact.label || artifact.name || id,
      kind: artifact.kind || artifact.type || artifact.mime_type || "artifact",
      summary: artifact.summary || artifact.description || "",
      iteration: artifact.iteration || 0,
      phase: artifact.phase || artifact.step_id || "",
      previewable: artifact.previewable !== false,
    });
  };
  (state.board?.artifacts || []).forEach(pushArtifact);
  (state.campaignDetail?.artifacts || []).forEach(pushArtifact);
  const graph = extractGraph();
  (graph?.nodes || []).forEach((node) => {
    (node.artifact_refs || []).forEach((ref) => pushArtifact({ id: ref, title: ref }));
  });
  return artifacts;
}

function extractDocs() {
  const records = state.selection.scope === "global" ? state.globalBoard?.records : state.board?.records;
  if (Array.isArray(records) && records.length) {
    return records.map((record) => ({
      id: record.record_id,
      title: record.title,
      kind: record.kind,
      summary: record.summary,
      created_at: record.created_at,
      preview_kind: record.preview_kind,
      preview_title: record.preview_title,
      preview_language: record.preview_language,
      preview_content: record.preview_content,
      metadata: record.metadata,
    }));
  }
  const docs = [];
  const campaign = state.campaignDetail;
  if (!campaign) {
    return docs;
  }
  if (campaign.task_summary) {
    docs.push({
      id: "task_summary",
      title: "Task Summary",
      kind: "record",
      preview_kind: "json",
      preview_title: "Task Summary",
      preview_language: "json",
      preview_content: JSON.stringify(campaign.task_summary, null, 2),
      metadata: campaign.task_summary,
    });
  }
  if (campaign.governance_summary) {
    docs.push({
      id: "governance",
      title: "Governance",
      kind: "record",
      preview_kind: "json",
      preview_title: "Governance",
      preview_language: "json",
      preview_content: JSON.stringify(campaign.governance_summary, null, 2),
      metadata: campaign.governance_summary,
    });
  }
  if (campaign.evaluation_summary) {
    docs.push({
      id: "evaluation",
      title: "Evaluation",
      kind: "record",
      preview_kind: "json",
      preview_title: "Evaluation",
      preview_language: "json",
      preview_content: JSON.stringify(campaign.evaluation_summary, null, 2),
      metadata: campaign.evaluation_summary,
    });
  }
  return docs;
}

function extractQueue(source) {
  if (!source) {
    return [];
  }
  if (Array.isArray(source.running_agents) || Array.isArray(source.next_agents) || Array.isArray(source.queued_agents)) {
    return [
      ...(source.running_agents || []).map((item) => ({ ...item, status: item.status || "running" })),
      ...(source.next_agents || []).map((item) => ({ ...item, status: item.status || "next" })),
      ...(source.queued_agents || []).map((item) => ({ ...item, status: item.status || "queued" })),
    ];
  }
  if (Array.isArray(source)) {
    return source;
  }
  const items = [];
  for (const bucket of ["running", "current", "next", "queued", "pending", "completed", "blocked"]) {
    const list = source[bucket];
    if (Array.isArray(list)) {
      list.forEach((item) => items.push({ ...item, status: item.status || bucket }));
    }
  }
  return items;
}

function extractTimelineItems() {
  const source = state.selection.scope === "global" ? state.globalBoard : state.board;
  if (Array.isArray(source?.timeline_items) && source.timeline_items.length) {
    return source.timeline_items;
  }
  if (state.selection.scope !== "campaign") {
    return [];
  }
  return (state.events || []).map((event) => ({
    id: event.event_id,
    kind: "event",
    timestamp: event.created_at,
    anchor_timestamp: event.created_at,
    display_time: event.created_at,
    display_title: eventLabel(event),
    display_brief: event.event_type || "",
    campaign_id: state.selection.id,
    node_id: event.payload?.phase || "",
    step_id: event.payload?.phase || "",
    status: event.severity || "info",
    is_future: false,
    detail_available: Boolean(state.selection.id && event.payload?.phase),
    detail_campaign_id: state.selection.id,
    detail_node_id: event.payload?.phase || "",
    detail_payload: event,
  }));
}

function extractTimelineBounds(items) {
  const source = state.selection.scope === "global" ? state.globalBoard : state.board;
  const fromSource = source?.timeline_bounds;
  if (fromSource?.min_timestamp && fromSource?.max_timestamp) {
    return fromSource;
  }
  const timestamps = items.map((item) => Date.parse(item.timestamp)).filter((value) => Number.isFinite(value));
  if (!timestamps.length) {
    return null;
  }
  return {
    min_timestamp: new Date(Math.min(...timestamps)).toISOString(),
    max_timestamp: new Date(Math.max(...timestamps)).toISOString(),
    default_anchor_timestamp: new Date(Math.max(...timestamps)).toISOString(),
    timezone: "+08:00",
  };
}

function buildCampaignGraph() {
  const graph = extractGraph();
  return {
    nodes: graph?.nodes || [],
    edges: graph?.edges || [],
  };
}

function computeLayout(nodes, edges) {
  const hasExplicitLayout = nodes.some((node) => node.position && Number.isFinite(Number(node.position.x)) && Number.isFinite(Number(node.position.y)));
  if (hasExplicitLayout) {
    const positions = new Map();
    let width = 0;
    let height = 0;
    nodes.forEach((node, index) => {
      const x = Number(node.position?.x ?? 80 + (index % 3) * 280);
      const y = Number(node.position?.y ?? 96 + Math.floor(index / 3) * 180);
      const itemWidth = Number(node.size?.w ?? 220);
      const itemHeight = Number(node.size?.h ?? 132);
      positions.set(node.id, { x, y, width: itemWidth, height: itemHeight });
      width = Math.max(width, x + itemWidth + 120);
      height = Math.max(height, y + itemHeight + 120);
    });
    return {
      positions,
      width: Math.max(width, 960),
      height: Math.max(height, 420),
    };
  }
  const nodeWidth = 180;
  const nodeHeight = 150;
  const colGap = 240;
  const rowGap = 190;
  const padding = 60;
  const indegree = new Map();
  const outgoing = new Map();
  nodes.forEach((node) => {
    indegree.set(node.id, 0);
    outgoing.set(node.id, []);
  });
  edges.forEach((edge) => {
    if (!outgoing.has(edge.source)) {
      outgoing.set(edge.source, []);
    }
    outgoing.get(edge.source).push(edge.target);
    indegree.set(edge.target, (indegree.get(edge.target) || 0) + 1);
  });
  const queue = [];
  indegree.forEach((value, key) => {
    if (value === 0) {
      queue.push(key);
    }
  });
  const level = new Map();
  queue.forEach((id) => level.set(id, 0));
  while (queue.length) {
    const id = queue.shift();
    const base = level.get(id) || 0;
    (outgoing.get(id) || []).forEach((target) => {
      const current = level.get(target) ?? 0;
      const next = Math.max(current, base + 1);
      level.set(target, next);
      indegree.set(target, (indegree.get(target) || 1) - 1);
      if (indegree.get(target) === 0) {
        queue.push(target);
      }
    });
  }
  const levels = {};
  nodes.forEach((node, index) => {
    const nodeLevel = level.get(node.id) ?? 0;
    if (!levels[nodeLevel]) {
      levels[nodeLevel] = [];
    }
    levels[nodeLevel].push({ node, index });
  });
  const positions = new Map();
  const maxLevel = Math.max(0, ...Object.keys(levels).map((key) => Number(key)));
  Object.entries(levels).forEach(([levelKey, items]) => {
    const column = Number(levelKey);
    items.forEach((entry, row) => {
      positions.set(entry.node.id, {
        x: padding + column * colGap,
        y: padding + row * rowGap,
        width: nodeWidth,
        height: nodeHeight,
      });
    });
  });
  const width = padding * 2 + (maxLevel + 1) * colGap;
  const maxRows = Math.max(1, ...Object.values(levels).map((items) => items.length));
  const height = padding * 2 + maxRows * rowGap;
  return { positions, width, height };
}

function updateTransform() {
  const { scale, x, y } = state.view;
  elements.canvasTransform.style.transform = `translate(${x}px, ${y}px) scale(${scale})`;
}

function animateViewportTransform() {
  window.clearTimeout(state.viewportAnimationTimer);
  elements.canvasTransform.classList.add("viewport-animating");
  state.viewportAnimationTimer = window.setTimeout(() => {
    elements.canvasTransform.classList.remove("viewport-animating");
  }, VIEWPORT_ANIMATION_MS);
}

function fitToView() {
  if (!state.layout) {
    return;
  }
  const { width, height } = state.layout;
  const bounds = elements.canvas.getBoundingClientRect();
  const scaleX = bounds.width / (width + 80);
  const scaleY = bounds.height / (height + 80);
  const scale = Math.min(1.2, Math.max(0.4, Math.min(scaleX, scaleY)));
  state.view.scale = scale;
  state.view.x = (bounds.width - width * scale) / 2;
  state.view.y = (bounds.height - height * scale) / 2;
  animateViewportTransform();
  updateTransform();
  markViewCustomized();
}

function focusNode(nodeId, { minScale = 1.2 } = {}) {
  if (!state.layout || !nodeId) {
    return;
  }
  const position = state.layout.positions.get(nodeId);
  if (!position) {
    return;
  }
  const bounds = elements.canvas.getBoundingClientRect();
  const scale = Math.max(state.view.scale || 1, minScale);
  const nodeCenterX = position.x + position.width / 2;
  const nodeCenterY = position.y + position.height / 2;
  state.view.scale = Math.min(2.4, Math.max(0.4, scale));
  state.view.x = bounds.width / 2 - nodeCenterX * state.view.scale;
  state.view.y = bounds.height / 2 - nodeCenterY * state.view.scale;
  animateViewportTransform();
  updateTransform();
  markViewCustomized();
}

function queueViewportAction(action) {
  state.pendingViewportAction = action;
}

function applyPendingViewportAction() {
  const action = state.pendingViewportAction;
  state.pendingViewportAction = null;
  if (!action) {
    updateTransform();
    return;
  }
  if (action.type === "fit") {
    fitToView();
    return;
  }
  if (action.type === "focus" && action.nodeId) {
    focusNode(action.nodeId, { minScale: action.minScale || 1.2 });
    return;
  }
  updateTransform();
}

function selectNode(nodeId, { focus = false } = {}) {
  state.selectedNodeId = nodeId || "";
  syncCurrentScopeState();
  if (focus && state.selectedNodeId) {
    queueViewportAction({ type: "focus", nodeId: state.selectedNodeId, minScale: 1.2 });
    renderGraph();
  } else {
    renderGraph();
  }
}

function updateBoardMode(mode) {
  state.boardMode = mode;
  elements.boardModeToggle.querySelectorAll("[data-board-mode]").forEach((button) => {
    button.classList.toggle("active", button.dataset.boardMode === mode);
  });
  elements.boardGraph.classList.toggle("hidden", mode !== "graph");
  elements.boardPreview.classList.toggle("hidden", mode !== "preview");
  syncCurrentScopeState();
}

function updateRightTab(tab) {
  state.rightTab = tab;
  elements.rightTabs.querySelectorAll("[data-tab]").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === tab);
  });
  elements.tabArtifacts.classList.toggle("hidden", tab !== "artifacts");
  elements.tabDocs.classList.toggle("hidden", tab !== "docs");
  elements.tabSkills.classList.toggle("hidden", tab !== "skills");
  elements.tabRuntime.classList.toggle("hidden", tab !== "runtime");
  syncCurrentScopeState();
}

function buildRecordPreview(record) {
  if (!record) {
    return null;
  }
  return {
    id: record.id,
    title: record.preview_title || record.title,
    text: record.preview_content || "",
    mime: record.preview_kind || "text",
    meta: record.metadata || {},
    language: record.preview_language || "text",
  };
}

function buildStalePreview(kind, id) {
  return {
    id,
    title: `${kind} unavailable`,
    text: `The selected ${kind} is no longer available after refresh.`,
    mime: "text",
    meta: { stale: true, kind, id },
    language: "text",
  };
}

async function refreshArtifactPreview(artifactId) {
  if (!artifactId || state.selection.scope !== "campaign" || !state.selection.id) {
    return;
  }
  const preview = await fetchJsonOptional(
    `/console/api/campaigns/${encodeURIComponent(state.selection.id)}/artifacts/${encodeURIComponent(artifactId)}/preview`,
  );
  if (preview) {
    state.preview = {
      id: artifactId,
      title: preview.title || preview.name,
      text: preview.content || preview.text || preview.body,
      mime: preview.preview_kind || preview.mime_type || preview.content_type || "text",
      meta: preview.metadata || preview.meta || {},
      language: preview.language || "text",
    };
  } else {
    state.preview = buildStalePreview("artifact", artifactId);
  }
  syncCurrentScopeState();
}

async function syncPreviewWithCurrentSelection() {
  if (state.boardMode !== "preview") {
    return;
  }
  if (state.rightTab === "docs") {
    const record = extractDocs().find((item) => item.id === state.selectedRecordId);
    state.preview = record ? buildRecordPreview(record) : buildStalePreview("record", state.selectedRecordId || "unknown");
    syncCurrentScopeState();
    return;
  }
  if (state.rightTab === "artifacts") {
    const artifact = extractArtifacts().find((item) => item.id === state.selectedArtifactId);
    if (!artifact) {
      state.preview = buildStalePreview("artifact", state.selectedArtifactId || "unknown");
      syncCurrentScopeState();
      return;
    }
    await refreshArtifactPreview(artifact.id);
  }
}

function reconcileSelectionAfterDataLoad() {
  const graph = extractGraph();
  const graphDefaults = graph?.inspector_defaults || {};
  const nodes = graph?.nodes || [];
  const nodeIds = new Set(nodes.map((node) => node.id));
  const previousNodeId = state.selectedNodeId;
  if (!state.selectedNodeId || !nodeIds.has(state.selectedNodeId)) {
    state.selectedNodeId = graphDefaults.selected_node_id || nodes[0]?.id || "";
    if (previousNodeId && state.selectedNodeId && previousNodeId !== state.selectedNodeId) {
      queueViewportAction({ type: "focus", nodeId: state.selectedNodeId, minScale: 1.2 });
    }
  }

  const artifacts = extractArtifacts();
  const artifactIds = new Set(artifacts.map((item) => item.id));
  if (state.selectedArtifactId && !artifactIds.has(state.selectedArtifactId)) {
    if (state.rightTab === "artifacts" && state.boardMode === "preview") {
      state.preview = buildStalePreview("artifact", state.selectedArtifactId);
    }
  }
  if (!state.selectedArtifactId) {
    state.selectedArtifactId = state.board?.preview_defaults?.preview_artifact_id || artifacts[0]?.id || "";
  }

  const docs = extractDocs();
  const recordIds = new Set(docs.map((item) => item.id));
  if (state.selectedRecordId && !recordIds.has(state.selectedRecordId) && state.rightTab === "docs" && state.boardMode === "preview") {
    state.preview = buildStalePreview("record", state.selectedRecordId);
  }
}

function renderRuntimeBadge() {
  const runtime = state.runtime || {};
  const status = runtime.process_state || "unknown";
  const runState = runtime.run_state || "unknown";
  elements.runtimeBadge.textContent = `Runtime ${status} · ${runState} · ${runtime.updated_at || "no timestamp"}`;
}

function renderGlobalItem() {
  elements.globalItem.classList.toggle("active", state.selection.scope === "global");
}

function renderProjectList() {
  const campaigns = state.campaigns || [];
  if (!campaigns.length) {
    elements.projectList.innerHTML = `<div class="empty-state">No campaigns yet.</div>`;
    return;
  }
  elements.projectList.innerHTML = campaigns
    .map((item) => {
      const view = item.campaign_view || item;
      const campaignId = view.campaign_id || view.id || "";
      const isActive = state.selection.scope === "campaign" && campaignId === state.selection.id;
      return `
        <button class="list-card ${isActive ? "active" : ""}" data-campaign-id="${escapeHtmlAttr(campaignId)}">
          <strong>${escapeHtml(view.campaign_title || view.title || campaignId || "Untitled campaign")}</strong>
          <div class="muted">${escapeHtml(view.status || "unknown")} · ${escapeHtml(view.workflow_id || "workflow n/a")}</div>
          <div class="meta-row">
            <span class="pill">${escapeHtml(view.current_phase || "phase n/a")}</span>
            <span class="pill">${escapeHtml(String(view.artifact_count ?? 0))} artifacts</span>
          </div>
        </button>
      `;
    })
    .join("");
  elements.projectList.querySelectorAll("[data-campaign-id]").forEach((button) => {
    button.addEventListener("click", () => activateCampaign(button.dataset.campaignId || ""));
  });
}

function renderAgentList() {
  if (state.selection.scope === "global") {
    const queue = extractQueue(state.globalBoard);
    if (!queue.length) {
      elements.agentSummary.textContent = "No queued agents.";
      elements.agentList.innerHTML = `<div class="empty-state">${escapeHtml(
        state.globalBoard?.idle_reason || "Waiting for queue data.",
      )}</div>`;
      return;
    }
    elements.agentSummary.textContent = `Running ${state.globalBoard?.running_agents?.length || 0} · Next ${state.globalBoard?.next_agents?.length || 0} · Queued ${state.globalBoard?.queued_agents?.length || 0}`;
    elements.agentList.innerHTML = sortByStatus(queue)
      .map((item) => {
        const status = normalizeStatus(item.status);
        const campaignId = item.metadata?.campaign_id || item.campaign_id || "";
        const focusNodeId = campaignId ? `campaign:${campaignId}` : item.id || "";
        const detailNodeId = item.step_id || item.phase || "";
        const detailAvailable = Boolean(campaignId && detailNodeId);
        return `
          <article class="agent-card-shell">
            <button class="agent-card" data-node-id="${escapeHtmlAttr(focusNodeId)}" type="button">
              <strong>${escapeHtml(item.title || item.role_id || "Agent")}</strong>
              <div class="muted">${escapeHtml(item.campaign_id || "global")} · ${escapeHtml(item.role_id || "role n/a")}</div>
              ${item.summary ? `<div class="agent-brief">${escapeHtml(item.summary)}</div>` : ""}
              <div class="meta-row">
                <span class="pill status-pill ${escapeHtmlAttr(status)}">${escapeHtml(status)}</span>
                ${item.phase ? `<span class="pill">${escapeHtml(item.phase)}</span>` : ""}
              </div>
            </button>
            ${
              detailAvailable
                ? `<button class="detail-button" type="button" aria-label="Open agent detail" title="Open agent detail" data-detail-campaign-id="${escapeHtmlAttr(campaignId)}" data-detail-node-id="${escapeHtmlAttr(detailNodeId)}">${detailButtonIcon()}</button>`
                : ""
            }
          </article>
        `;
      })
      .join("");
  } else {
    const graph = extractGraph();
    const nodes = graph?.nodes || [];
    if (!nodes.length) {
      elements.agentSummary.textContent = "No agents.";
      elements.agentList.innerHTML = `<div class="empty-state">Select a project to load agents.</div>`;
      return;
    }
    elements.agentSummary.textContent = `${nodes.length} agents`;
    elements.agentList.innerHTML = nodes
      .map((node) => {
        const status = normalizeStatus(node.status);
        const isSelected = node.id === state.selectedNodeId;
        return `
          <article class="agent-card-shell ${isSelected ? "active" : ""}">
            <button class="agent-card ${isSelected ? "active" : ""}" data-node-id="${escapeHtmlAttr(node.id || "")}" type="button">
              <strong>${escapeHtml(node.display_title || node.title || node.id || "Agent")}</strong>
              <div class="muted">${escapeHtml(node.role_label || node.role_id || "role n/a")}</div>
              ${node.display_brief ? `<div class="agent-brief">${escapeHtml(node.display_brief)}</div>` : ""}
              <div class="meta-row">
                <span class="pill status-pill ${escapeHtmlAttr(status)}">${escapeHtml(status)}</span>
                ${node.phase ? `<span class="pill">${escapeHtml(node.phase)}</span>` : ""}
              </div>
            </button>
            ${
              node.detail_available
                ? `<button class="detail-button" type="button" aria-label="Open agent detail" title="Open agent detail" data-detail-campaign-id="${escapeHtmlAttr(node.detail_campaign_id || state.selection.id || "")}" data-detail-node-id="${escapeHtmlAttr(node.detail_node_id || node.id || "")}">${detailButtonIcon()}</button>`
                : ""
            }
          </article>
        `;
      })
      .join("");
  }
  elements.agentList.querySelectorAll("[data-node-id]").forEach((button) => {
    button.addEventListener("click", () => selectNode(button.dataset.nodeId || "", { focus: true }));
  });
  elements.agentList.querySelectorAll("[data-detail-node-id]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      openAgentDetail(button.dataset.detailCampaignId || "", button.dataset.detailNodeId || "");
    });
  });
}

function renderBoardHeading() {
  if (state.selection.scope === "global") {
    elements.boardTitle.textContent = "Global Scheduler";
    elements.boardSubtitle.textContent = state.globalBoard?.idle_reason || state.globalBoard?.summary || "Queue view across active campaigns.";
    return;
  }
  const campaign = state.campaignDetail?.campaign_view || {};
  elements.boardTitle.textContent = state.board?.title || campaign.title || campaign.campaign_title || state.selection.id || "Campaign";
  elements.boardSubtitle.textContent =
    state.board?.idle_reason || state.board?.summary || (campaign.workflow_id ? `Workflow ${campaign.workflow_id}` : "Campaign workflow graph");
}

function renderGraph() {
  const graphData = buildCampaignGraph();
  const nodes = graphData.nodes || [];
  const edges = graphData.edges || [];
  if (!nodes.length) {
    const idleReason =
      (state.selection.scope === "global" ? state.globalBoard?.idle_reason : state.board?.idle_reason) ||
      "No graph data yet.";
    elements.graphEmpty.style.display = "flex";
    elements.graphEmpty.textContent = idleReason;
    elements.nodeLayer.innerHTML = "";
    elements.edgeLayer.innerHTML = "";
    state.layout = null;
    return;
  }

  elements.graphEmpty.style.display = "none";
  const layout = computeLayout(nodes, edges);
  state.layout = layout;
  elements.canvasTransform.style.width = `${layout.width}px`;
  elements.canvasTransform.style.height = `${layout.height}px`;
  elements.nodeLayer.style.width = `${layout.width}px`;
  elements.nodeLayer.style.height = `${layout.height}px`;
  elements.edgeLayer.setAttribute("width", layout.width);
  elements.edgeLayer.setAttribute("height", layout.height);
  elements.edgeLayer.setAttribute("viewBox", `0 0 ${layout.width} ${layout.height}`);
  elements.edgeLayer.innerHTML = `
    <defs>
      <marker id="arrow" markerWidth="10" markerHeight="10" refX="7" refY="5" orient="auto">
        <path d="M0,0 L10,5 L0,10 Z" fill="rgba(186, 93, 42, 0.62)"></path>
      </marker>
    </defs>
    ${edges
      .map((edge) => {
        const source = layout.positions.get(edge.source);
        const target = layout.positions.get(edge.target);
        if (!source || !target) {
          return "";
        }
        const x1 = source.x + source.width / 2;
        const y1 = source.y + source.height / 2;
        const x2 = target.x + target.width / 2;
        const y2 = target.y + target.height / 2;
        const dx = Math.max(120, Math.abs(x2 - x1) * 0.42);
        const dy = Math.max(48, Math.abs(y2 - y1) * 0.28);
        const control1X = edge.is_back_edge ? x1 + dx : x1 + Math.sign(x2 - x1 || 1) * dx;
        const control1Y = edge.is_back_edge ? y1 + dy : y1;
        const control2X = edge.is_back_edge ? x2 - dx : x2 - Math.sign(x2 - x1 || 1) * dx;
        const control2Y = edge.is_back_edge ? y2 - dy : y2;
        const strokeClass = edge.visual_kind || "flow";
        const emphasis = edge.emphasis || "normal";
        return `<path class="edge-path ${escapeHtmlAttr(strokeClass)} ${escapeHtmlAttr(emphasis)}" d="M${x1} ${y1} C${control1X} ${control1Y}, ${control2X} ${control2Y}, ${x2} ${y2}" marker-end="url(#arrow)"></path>`;
      })
      .join("")}
  `;
  elements.nodeLayer.innerHTML = nodes
    .map((node) => {
      const status = normalizeStatus(node.status || node.state);
      const position = layout.positions.get(node.id);
      if (!position) {
        return "";
      }
      const isSelected = node.id === state.selectedNodeId;
      const subtitle = node.role_label || node.subtitle || `${node.id || ""} · ${node.role_id || "role n/a"}`;
      const brief = node.display_brief || node.subtitle || node.phase || "";
      const chips = (node.badges || []).filter(Boolean).slice(0, 2);
      return `
        <article class="node-card status-${escapeHtmlAttr(status)} ${isSelected ? "selected" : ""}" data-node-id="${escapeHtmlAttr(node.id || "")}"
          style="left:${position.x}px; top:${position.y}px; width:${position.width}px; min-height:${position.height}px;">
          <div class="node-head">
            <div class="node-title-wrap">
              <div class="node-title">${escapeHtml(node.display_title || node.title || node.id || "Agent")}</div>
              <div class="node-role">${escapeHtml(subtitle)}</div>
            </div>
            <div class="node-head-actions">
              <span class="pill status-pill ${escapeHtmlAttr(status)}">${escapeHtml(status)}</span>
              ${
                node.detail_available
                  ? `<button class="detail-button detail-button-node" type="button" aria-label="Open agent detail" title="Open agent detail" data-detail-campaign-id="${escapeHtmlAttr(node.detail_campaign_id || state.selection.id || "")}" data-detail-node-id="${escapeHtmlAttr(node.detail_node_id || node.id || "")}">${detailButtonIcon()}</button>`
                  : ""
              }
            </div>
          </div>
          <div class="node-brief">${escapeHtml(brief)}</div>
          <div class="node-footer">
            <div class="node-foot-meta">
              ${node.iteration_label ? `<span>${escapeHtml(node.iteration_label)}</span>` : ""}
              ${node.phase ? `<span>${escapeHtml(node.phase)}</span>` : ""}
              ${node.updated_at_label ? `<span>${escapeHtml(node.updated_at_label)}</span>` : ""}
            </div>
            <div class="node-chip-row">
              ${chips
                .map((badge) => `<span class="pill node-pill">${escapeHtml(badge)}</span>`)
              .join("")}
            </div>
          </div>
        </article>
      `;
    })
    .join("");

  elements.nodeLayer.querySelectorAll("[data-node-id]").forEach((card) => {
    card.addEventListener("click", (event) => {
      if (event.target.closest(".detail-button")) {
        return;
      }
      event.stopPropagation();
      selectNode(card.dataset.nodeId || "", { focus: true });
    });
  });
  elements.nodeLayer.querySelectorAll("[data-detail-node-id]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      openAgentDetail(button.dataset.detailCampaignId || "", button.dataset.detailNodeId || "");
    });
  });

  applyPendingViewportAction();
}

function renderArtifacts() {
  const artifacts = extractArtifacts();
  if (!artifacts.length) {
    elements.artifactList.innerHTML = `<div class="empty-state">No artifacts yet.</div>`;
    return;
  }
  elements.artifactList.innerHTML = artifacts
    .map((artifact) => {
      const isActive = artifact.id === state.selectedArtifactId;
      return `
        <button class="artifact-card ${isActive ? "active" : ""}" data-artifact-id="${escapeHtmlAttr(artifact.id)}" type="button">
          <strong>${escapeHtml(artifact.title)}</strong>
          <div class="muted">${escapeHtml(artifact.kind || "artifact")} · ${escapeHtml(artifact.phase || "phase n/a")}</div>
          <div class="muted">iteration ${escapeHtml(String(artifact.iteration || 0))}</div>
          ${artifact.summary ? `<div class="muted">${escapeHtml(artifact.summary)}</div>` : ""}
        </button>
      `;
    })
    .join("");
  elements.artifactList.querySelectorAll("[data-artifact-id]").forEach((button) => {
    button.addEventListener("click", () => selectArtifact(button.dataset.artifactId || ""));
  });
}

function renderDocs() {
  const docs = extractDocs();
  if (!docs.length) {
    elements.docsPanel.innerHTML = `<div class="empty-state">No docs yet.</div>`;
    return;
  }
  elements.docsPanel.innerHTML = docs
    .map((doc) => {
      const isActive = doc.id === state.selectedRecordId;
      return `
        <button class="doc-card ${isActive ? "active" : ""}" data-record-id="${escapeHtmlAttr(doc.id || doc.title)}" type="button">
          <strong>${escapeHtml(doc.title)}</strong>
          <div class="muted">${escapeHtml(doc.kind || "record")} · ${escapeHtml(doc.created_at || "")}</div>
          <div class="muted">${escapeHtml(doc.summary || "Open in preview")}</div>
        </button>
      `;
    })
    .join("");
  elements.docsPanel.querySelectorAll("[data-record-id]").forEach((button) => {
    button.addEventListener("click", () => selectRecord(button.dataset.recordId || ""));
  });
}

function renderSkillsPanel() {
  if (state.selection.scope === "global") {
    const diagnostics = state.skillDiagnostics || {};
    const summary = diagnostics.summary || {};
    const collections = state.skillCollections || [];
    const issues = diagnostics.issues || [];
    elements.skillsPanel.innerHTML = `
      <div class="runtime-card">
        <strong>Skill registry</strong>
        <div class="muted">${escapeHtml(String(summary.collection_count ?? collections.length))} collections · ${escapeHtml(String(summary.issue_count ?? 0))} issues</div>
        <div class="muted">${escapeHtml(String(summary.error_count ?? 0))} errors · ${escapeHtml(String(summary.warning_count ?? 0))} warnings</div>
      </div>
      ${
        collections.length
          ? collections
              .map(
                (item) => `
                  <div class="runtime-card">
                    <strong>${escapeHtml(item.collection_id || "collection")}</strong>
                    <div class="muted">${escapeHtml(item.description || "No description")}</div>
                    <div class="muted">${escapeHtml(String(item.skill_count ?? 0))} skills · ${escapeHtml(String(item.family_count ?? 0))} families</div>
                    <div class="muted">${escapeHtml(item.default_injection_mode || "shortlist")} · ${escapeHtml(item.status || "active")} · diagnostics ${escapeHtml(String(item.diagnostic_count ?? 0))}</div>
                  </div>
                `,
              )
              .join("")
          : `<div class="empty-state">No skill collections found.</div>`
      }
      ${
        issues.length
          ? `<div class="runtime-card">
              <strong>Top diagnostics</strong>
              <div class="stack">
                ${issues
                  .slice(0, 8)
                  .map(
                    (item) =>
                      `<div class="muted">${escapeHtml(item.level || "info")} · ${escapeHtml(item.collection_id || "collection")} · ${escapeHtml(item.message || "")}</div>`,
                  )
                  .join("")}
              </div>
            </div>`
          : ""
      }
    `;
    return;
  }
  const observation = state.campaignDetail?.skill_exposure_observation || null;
  const collection = state.skillCollectionDetail || {};
  if (!observation || !observation.collection_id) {
    elements.skillsPanel.innerHTML = `<div class="empty-state">No skill exposure recorded for this campaign yet.</div>`;
    return;
  }
  elements.skillsPanel.innerHTML = `
    <div class="runtime-card">
      <strong>Active skill exposure</strong>
      <div class="muted">${escapeHtml(observation.collection_id || "n/a")} · ${escapeHtml(observation.injection_mode || "shortlist")} · ${escapeHtml(observation.materialization_mode || "prompt_block")}</div>
      <div class="muted">Families ${escapeHtml(String(observation.collection_family_count ?? 0))} · Skills ${escapeHtml(String(observation.collection_skill_count ?? 0))}</div>
      <div class="muted">Selected families: ${escapeHtml((observation.selected_family_labels || []).join(", ") || "none")}</div>
      <div class="muted">Direct skills: ${escapeHtml((observation.selected_skill_names || observation.direct_skill_names || []).join(", ") || "none")}</div>
    </div>
    ${
      collection.collection_id
        ? `<div class="runtime-card">
            <strong>Collection detail</strong>
            <div class="muted">${escapeHtml(collection.description || "No description")}</div>
            <div class="muted">${escapeHtml(String((collection.skills || []).length))} skills · ${escapeHtml(String((collection.families || []).length))} families</div>
            <div class="stack">
              ${(collection.families || [])
                .slice(0, 8)
                .map(
                  (item) =>
                    `<div class="muted">${escapeHtml(item.label || item.family_id || "family")} · ${escapeHtml(item.risk_level || "unknown")} · ${escapeHtml(String(item.member_count ?? 0))} skills</div>`,
                )
                .join("")}
            </div>
          </div>`
        : ""
    }
  `;
}

function renderRuntimePanel() {
  const runtime = state.runtime || {};
  const activeBoard = state.selection.scope === "global" ? state.globalBoard : state.board;
  const queue = extractQueue(activeBoard);
  const running = queue.filter((item) => ["running", "current", "active"].includes(normalizeStatus(item.status)));
  const next = queue.filter((item) => normalizeStatus(item.status) === "next");
  const queued = queue.filter((item) => ["queued", "pending"].includes(normalizeStatus(item.status)));
  const access = state.globalBoard?.metadata?.access || {};
  const renderQueue = (title, items) => {
    if (!items.length) {
      return `<div class="runtime-card"><strong>${escapeHtml(title)}</strong><div class="muted">None</div></div>`;
    }
    return `
      <div class="runtime-card">
        <strong>${escapeHtml(title)}</strong>
        <div class="stack">
          ${items
            .slice(0, 6)
            .map(
              (item) =>
                `<div class="muted">${escapeHtml(item.title || item.role_id || "Agent")} · ${escapeHtml(
                  item.campaign_id || state.selection.id || "global",
                )}</div>`,
            )
            .join("")}
        </div>
      </div>
    `;
  };
  elements.runtimePanel.innerHTML = `
    <div class="runtime-card">
      <strong>Runtime</strong>
      <div class="muted">${escapeHtml(runtime.process_state || "unknown")} · ${escapeHtml(runtime.run_state || "unknown")}</div>
      <div class="muted">${escapeHtml(runtime.phase || "phase n/a")} · ${escapeHtml(runtime.updated_at || "no timestamp")}</div>
      <div class="muted">${escapeHtml(activeBoard?.idle_reason || runtime.note || "No telemetry")}</div>
    </div>
    ${renderQueue("Running", running)}
    ${renderQueue("Next", next)}
    ${renderQueue("Queued", queued)}
    ${
      access.listen_host
        ? `<div class="runtime-card">
            <strong>Visual console access</strong>
            <div class="muted">${escapeHtml(access.note || "")}</div>
            ${(access.local_urls || []).map((item) => `<div class="muted">${escapeHtml(item)}</div>`).join("")}
            ${(access.lan_urls || []).map((item) => `<div class="muted">${escapeHtml(item)}</div>`).join("")}
          </div>`
        : ""
    }
  `;
}

function renderPreview() {
  if (!state.preview) {
    elements.previewPane.innerHTML = `<div class="preview-empty">Select an artifact or record to preview.</div>`;
    return;
  }
  const title = state.preview.title || state.preview.id || "Preview";
  const meta = state.preview.meta ? JSON.stringify(state.preview.meta, null, 2) : "";
  const body = state.preview.text || state.preview.content || "";
  elements.previewPane.innerHTML = `
    <h3>${escapeHtml(title)}</h3>
    ${state.preview.mime ? `<div class="muted">${escapeHtml(state.preview.mime)}${state.preview.language ? ` · ${escapeHtml(state.preview.language)}` : ""}</div>` : ""}
    ${body ? `<pre>${escapeHtml(body)}</pre>` : `<div class="muted">No preview content.</div>`}
    ${meta ? `<pre>${escapeHtml(meta)}</pre>` : ""}
  `;
}

function buildStaleAgentDetail(campaignId, nodeId) {
  return {
    campaign_id: campaignId,
    node_id: nodeId,
    title: nodeId || "Unknown agent",
    status: "stale",
    execution_state: "idle_unknown",
    role_label: "",
    subtitle: "The selected agent is no longer present in the latest refresh.",
    updated_at: "",
    overview: {
      campaign_id: campaignId,
      node_id: nodeId,
      note: "This detail view is preserved as a stale placeholder instead of closing automatically.",
    },
    planned_input: {},
    live_records: [],
    artifacts: [],
    raw_records: [],
  };
}

function renderDetailValue(value) {
  if (Array.isArray(value)) {
    if (!value.length) {
      return `<span class="muted">None</span>`;
    }
    return `<div class="detail-list">${value.map((item) => `<span>${escapeHtml(String(item))}</span>`).join("")}</div>`;
  }
  if (value && typeof value === "object") {
    return `<pre>${escapeHtml(JSON.stringify(value, null, 2))}</pre>`;
  }
  const text = String(value ?? "").trim();
  return text ? `<strong>${escapeHtml(text)}</strong>` : `<span class="muted">None</span>`;
}

function renderAgentDetail() {
  const isOpen = state.agentDetailOpen;
  elements.agentDetailOverlay.classList.toggle("hidden", !isOpen);
  elements.agentDetailOverlay.setAttribute("aria-hidden", String(!isOpen));
  if (!isOpen) {
    return;
  }
  const detail = state.agentDetailData || buildStaleAgentDetail(state.agentDetailCampaignId, state.agentDetailNodeId);
  const executionState = String(detail.execution_state || detail.status || "").toLowerCase();
  const statusTone = normalizeStatus(executionState === "idle_unknown" ? detail.status : executionState);
  elements.agentDetailTitle.textContent = detail.title || detail.node_id || "Agent Detail";
  elements.agentDetailSubtitle.textContent =
    detail.subtitle || `${detail.role_label || detail.role_id || "role n/a"} · ${detail.updated_at || "no timestamp"}`;
  elements.agentDetailStatusRow.innerHTML = `
    <span class="pill status-pill ${escapeHtmlAttr(statusTone)}">${escapeHtml(detailExecutionStateLabel(executionState))}</span>
    ${detail.role_label ? `<span class="pill subtle">${escapeHtml(detail.role_label)}</span>` : ""}
    ${detail.updated_at ? `<span class="pill subtle">${escapeHtml(detail.updated_at)}</span>` : ""}
    ${state.agentDetailStale ? `<span class="pill subtle">Stale snapshot</span>` : ""}
  `;

  const overview = detail.overview || {};
  const overviewEntries = [
    ["Campaign", overview.campaign_title || detail.campaign_id],
    ["Node", detail.node_id],
    ["Campaign Status", overview.campaign_status || ""],
    ["Execution", overview.execution_state || ""],
    ["Closure", overview.closure_state || ""],
    ["Phase", overview.phase || overview.current_phase || ""],
    ["Session", overview.workflow_session_id || ""],
    ["Runtime", overview.runtime_mode || ""],
    ["Bundle", overview.bundle_root || ""],
    ["Progress", overview.progress_reason || ""],
    ["Closure Reason", overview.closure_reason || ""],
    ["Acceptance", overview.latest_acceptance_decision || ""],
    ["Not Done", overview.not_done_reason || ""],
    ["Artifacts", overview.artifact_count],
    ["Events", overview.session_event_count],
  ].filter(([, value]) => value !== undefined && value !== null && String(value).trim() !== "");
  elements.agentDetailOverview.innerHTML = overviewEntries.length
    ? overviewEntries
        .map(
          ([label, value]) => `
            <div class="detail-kv-card">
              <span>${escapeHtml(label)}</span>
              ${renderDetailValue(value)}
            </div>
          `,
        )
        .join("")
    : `<div class="empty-state">No overview data.</div>`;

  const liveRecords = Array.isArray(detail.live_records) ? detail.live_records : [];
  elements.agentDetailRecords.innerHTML = liveRecords.length
    ? liveRecords
        .map((record) => {
          const title = record.title || record.event_type || record.kind || "Record";
          const summary = record.summary || record.message || record.text || "";
          const createdAt = record.created_at || record.updated_at || "";
          const body =
            summary ||
            (record.payload ? JSON.stringify(record.payload, null, 2) : JSON.stringify(record, null, 2));
          return `
            <article class="detail-record-card">
              <div class="detail-record-head">
                <strong>${escapeHtml(title)}</strong>
                ${createdAt ? `<span class="muted">${escapeHtml(createdAt)}</span>` : ""}
              </div>
              <pre>${escapeHtml(body)}</pre>
            </article>
          `;
        })
        .join("")
    : `<div class="empty-state">No run records for this agent yet.</div>`;

  const plannedInput = detail.planned_input || {};
  const plannedEntries = [
    ["Goal", plannedInput.goal],
    ["Acceptance", plannedInput.acceptance],
    ["Materials", plannedInput.materials],
    ["Hard Constraints", plannedInput.hard_constraints],
    ["Pending Checks", plannedInput.pending_checks],
    ["Operational Checks", plannedInput.operational_checks_pending],
    ["Closure Checks", plannedInput.closure_checks_pending],
    ["Resolved Checks", plannedInput.resolved_checks],
    ["Waived Checks", plannedInput.waived_checks],
    ["Plan Ref", plannedInput.plan_ref],
    ["Spec Ref", plannedInput.spec_ref],
    ["Progress Ref", plannedInput.progress_ref],
    ["Bundle Root", plannedInput.bundle_root],
  ].filter(([, value]) => {
    if (Array.isArray(value)) {
      return value.length > 0;
    }
    return value !== undefined && value !== null && String(value).trim() !== "";
  });
  elements.agentDetailPlanned.innerHTML = plannedEntries.length
    ? plannedEntries
        .map(
          ([label, value]) => `
            <div class="detail-kv-card">
              <span>${escapeHtml(label)}</span>
              ${renderDetailValue(value)}
            </div>
          `,
        )
        .join("")
    : `<div class="empty-state">No planned input is available for this agent.</div>`;

  const artifacts = Array.isArray(detail.artifacts) ? detail.artifacts : [];
  elements.agentDetailArtifacts.innerHTML = artifacts.length
    ? artifacts
        .map(
          (artifact) => `
            <article class="detail-record-card">
              <div class="detail-record-head">
                <strong>${escapeHtml(artifact.label || artifact.artifact_id || artifact.ref || "Artifact")}</strong>
                <span class="muted">${escapeHtml(artifact.created_at || artifact.kind || "")}</span>
              </div>
              <div class="muted">${escapeHtml(artifact.kind || "artifact")} · ${escapeHtml(artifact.phase || "phase n/a")}</div>
              ${artifact.ref ? `<div class="muted">${escapeHtml(artifact.ref)}</div>` : ""}
            </article>
          `,
        )
        .join("")
    : `<div class="empty-state">No artifacts are linked to this agent.</div>`;

  const rawRecords = Array.isArray(detail.raw_records) ? detail.raw_records : [];
  elements.agentDetailRaw.innerHTML = rawRecords.length
    ? rawRecords
        .map(
          (record, index) => `
            <article class="detail-record-card">
              <div class="detail-record-head">
                <strong>${escapeHtml(record.title || record.event_type || `Raw ${index + 1}`)}</strong>
              </div>
              <pre>${escapeHtml(JSON.stringify(record, null, 2))}</pre>
            </article>
          `,
        )
        .join("")
    : `<div class="empty-state">No raw records are available for this agent.</div>`;

  const panels = {
    records: elements.agentDetailRecords,
    planned: elements.agentDetailPlanned,
    artifacts: elements.agentDetailArtifacts,
    raw: elements.agentDetailRaw,
  };
  Object.entries(panels).forEach(([tab, element]) => {
    element.classList.toggle("hidden", tab !== state.agentDetailTab);
  });
  elements.agentDetailTabs.querySelectorAll("[data-agent-tab]").forEach((button) => {
    button.classList.toggle("active", button.dataset.agentTab === state.agentDetailTab);
  });
  elements.agentDetailScroll.scrollTop = state.agentDetailScrollTop || 0;
}

function updateAgentDetailTab(tab) {
  state.agentDetailTab = tab || "records";
  renderAgentDetail();
}

async function refreshAgentDetail() {
  if (!state.agentDetailOpen || !state.agentDetailCampaignId || !state.agentDetailNodeId) {
    return;
  }
  const payload = await fetchJsonOptional(
    `/console/api/campaigns/${encodeURIComponent(state.agentDetailCampaignId)}/agents/${encodeURIComponent(state.agentDetailNodeId)}/detail`,
  );
  if (payload) {
    state.agentDetailData = payload;
    state.agentDetailStale = false;
  } else {
    state.agentDetailData = state.agentDetailData || buildStaleAgentDetail(state.agentDetailCampaignId, state.agentDetailNodeId);
    state.agentDetailStale = true;
  }
  renderAgentDetail();
}

async function openAgentDetail(campaignId, nodeId) {
  if (!campaignId || !nodeId) {
    return;
  }
  const changed = campaignId !== state.agentDetailCampaignId || nodeId !== state.agentDetailNodeId;
  state.agentDetailOpen = true;
  state.agentDetailCampaignId = campaignId;
  state.agentDetailNodeId = nodeId;
  if (changed) {
    state.agentDetailTab = "records";
    state.agentDetailScrollTop = 0;
    state.agentDetailData = null;
    state.agentDetailStale = false;
  }
  renderAgentDetail();
  await refreshAgentDetail();
}

function closeAgentDetail() {
  state.agentDetailOpen = false;
  renderAgentDetail();
}

function eventLabel(event) {
  return event.payload?.phase || event.event_type || "event";
}

function eventDetails(event) {
  const parts = [];
  if (event.event_type) {
    parts.push(`event_type: ${event.event_type}`);
  }
  if (event.created_at) {
    parts.push(`created_at: ${event.created_at}`);
  }
  if (event.payload?.phase) {
    parts.push(`phase: ${event.payload.phase}`);
  }
  if (event.payload?.iteration !== undefined) {
    parts.push(`iteration: ${event.payload.iteration}`);
  }
  const payloadEntries = Object.entries(event.payload || {}).slice(0, 6);
  if (payloadEntries.length) {
    parts.push(
      payloadEntries
        .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(", ") : String(value)}`)
        .join("\n"),
    );
  }
  return parts.join("\n");
}

function renderTimeline() {
  const items = extractTimelineItems();
  if (state.selection.scope !== "campaign") {
    if (!items.length) {
      elements.eventsList.className = "timeline empty-state";
      elements.eventsList.textContent = "Select a project to inspect its timeline.";
      return;
    }
  }
  if (!items.length) {
    elements.eventsList.className = "timeline empty-state";
    elements.eventsList.textContent = "No campaign events yet.";
    return;
  }
  const ordered = [...items].sort((a, b) =>
    String(a.anchor_timestamp || a.timestamp || "").localeCompare(String(b.anchor_timestamp || b.timestamp || "")),
  );
  const bounds = extractTimelineBounds(ordered) || {};
  const minTs = Date.parse(bounds.min_timestamp || ordered[0]?.anchor_timestamp || ordered[0]?.timestamp || "");
  const maxTs = Date.parse(bounds.max_timestamp || ordered[ordered.length - 1]?.anchor_timestamp || ordered[ordered.length - 1]?.timestamp || "");
  const span = Math.max(1, maxTs - minTs);
  const cardWidth = Number(bounds.card_width || 142);
  const cardGap = Number(bounds.card_gap || 18);
  let fallbackLeft = 48 - cardGap;
  const stageWidth = Math.max(
    860,
    Number(bounds.stage_width || 0),
    ordered.reduce((width, item, index) => {
      const parsed = Date.parse(item.anchor_timestamp || item.timestamp || "");
      const ratio = Number.isFinite(parsed) ? (parsed - minTs) / span : index / Math.max(1, ordered.length - 1);
      const anchorX = Number.isFinite(Number(item.anchor_x)) ? Number(item.anchor_x) : 48 + ratio * Math.max(1, 860 - 96);
      const layoutX =
        Number.isFinite(Number(item.layout_x)) && Number(item.layout_x) > 0
          ? Number(item.layout_x)
          : Math.max(48, anchorX - cardWidth / 2, fallbackLeft + cardGap);
      fallbackLeft = layoutX + cardWidth;
      return Math.max(width, layoutX + cardWidth + 48);
    }, 860),
  );
  const tickCount = Math.min(8, Math.max(4, ordered.length + 1));
  const ticks = Array.from({ length: tickCount }, (_, index) => {
    const ratio = tickCount === 1 ? 0 : index / (tickCount - 1);
    const ts = minTs + span * ratio;
    return {
      left: `${ratio * 100}%`,
      label: new Date(ts).toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
        timeZone: "Asia/Shanghai",
      }).replace(",", ""),
    };
  });
  const layoutCache = [];
  let previousRight = 48 - cardGap;
  ordered.forEach((item, index) => {
    const parsed = Date.parse(item.anchor_timestamp || item.timestamp || "");
    const ratio = Number.isFinite(parsed) ? (parsed - minTs) / span : index / Math.max(1, ordered.length - 1);
    const anchorX = Number.isFinite(Number(item.anchor_x)) ? Number(item.anchor_x) : 48 + ratio * Math.max(1, stageWidth - 96);
    const layoutX =
      Number.isFinite(Number(item.layout_x)) && Number(item.layout_x) > 0
        ? Number(item.layout_x)
        : Math.max(48, anchorX - cardWidth / 2, previousRight + cardGap);
    previousRight = layoutX + cardWidth;
    layoutCache.push({ item, anchorX, layoutX });
  });
  elements.eventsList.className = "timeline";
  elements.eventsList.innerHTML = `
    <div class="timeline-viewport" data-timeline-viewport="true">
      <div class="timeline-stage" style="width:${stageWidth}px">
        <div class="timeline-lane">
          <svg class="timeline-guides" viewBox="0 0 ${stageWidth} 110" preserveAspectRatio="none" aria-hidden="true">
            <line class="timeline-baseline" x1="0" y1="84" x2="${stageWidth}" y2="84"></line>
            ${layoutCache
              .map(({ anchorX, layoutX }) => {
                const cardCenterX = layoutX + cardWidth / 2;
                return `
                  <path class="timeline-guide-path" d="M ${cardCenterX} 58 C ${cardCenterX} 70, ${anchorX} 68, ${anchorX} 84"></path>
                  <circle class="timeline-guide-dot" cx="${anchorX}" cy="84" r="4.5"></circle>
                `;
              })
              .join("")}
          </svg>
          ${layoutCache
            .map(({ item, layoutX }) => {
              const detail = JSON.stringify(item.detail_payload || item, null, 2);
              const tone = item.is_future ? "future" : normalizeStatus(item.status || item.kind || "info");
              const isSelected = item.id === state.selectedTimelineItemId;
              return `
                <button class="timeline-item ${escapeHtmlAttr(tone)} ${isSelected ? "active" : ""}" type="button" data-timeline-item-id="${escapeHtmlAttr(item.id)}" data-node-id="${escapeHtmlAttr(item.node_id || item.step_id || "")}" style="left:${layoutX}px; width:${cardWidth}px;">
                  <div class="timeline-item-topline">
                    <span class="timeline-dot"></span>
                    <span class="timeline-time">${escapeHtml(item.display_time || item.timestamp || "")}</span>
                  </div>
                  <strong>${escapeHtml(item.display_title || item.kind || "item")}</strong>
                  <div class="timeline-popover">
                    <strong>${escapeHtml(item.display_title || item.kind || "item")}</strong>
                    <div class="muted">${escapeHtml(item.display_time || item.timestamp || "")}</div>
                    ${item.display_brief ? `<div class="muted">${escapeHtml(item.display_brief)}</div>` : ""}
                    <pre>${escapeHtml(detail)}</pre>
                  </div>
                </button>
              `;
            })
            .join("")}
        </div>
      </div>
    </div>
    <div class="timeline-ruler-shell">
      <div class="timeline-ruler-track" data-timeline-track="true">
        ${ticks
          .map(
            (tick) => `
              <div class="timeline-tick" style="left:${tick.left};">
                <span class="timeline-tick-mark"></span>
                <span class="timeline-tick-label">${escapeHtml(tick.label)}</span>
              </div>
            `,
          )
          .join("")}
        <button class="timeline-thumb" type="button" data-timeline-thumb="true" aria-label="Drag timeline viewport"></button>
      </div>
    </div>
  `;
  const viewport = getTimelineViewport();
  const track = elements.eventsList.querySelector("[data-timeline-track]");
  const thumb = elements.eventsList.querySelector("[data-timeline-thumb]");
  if (!viewport || !track || !thumb) {
    return;
  }
  const syncThumb = () => {
    const maxScroll = Math.max(0, viewport.scrollWidth - viewport.clientWidth);
    const trackWidth = track.clientWidth;
    const thumbWidth = maxScroll <= 0 ? trackWidth : Math.max(52, (viewport.clientWidth / viewport.scrollWidth) * trackWidth);
    const travel = Math.max(0, trackWidth - thumbWidth);
    const left = maxScroll <= 0 ? 0 : (viewport.scrollLeft / maxScroll) * travel;
    thumb.style.width = `${thumbWidth}px`;
    thumb.style.transform = `translateX(${left}px)`;
  };
  const maxScroll = Math.max(0, viewport.scrollWidth - viewport.clientWidth);
  viewport.scrollLeft = Math.min(state.timelineScrollLeft || 0, maxScroll);
  viewport.onscroll = () => {
    state.timelineScrollLeft = viewport.scrollLeft;
    syncCurrentScopeState();
    syncThumb();
  };
  syncThumb();
  thumb.onmousedown = (event) => {
    if (event.button !== 0) {
      return;
    }
    event.preventDefault();
    const startX = event.clientX;
    const startScroll = viewport.scrollLeft;
    const thumbWidth = thumb.getBoundingClientRect().width;
    const travel = Math.max(1, track.clientWidth - thumbWidth);
    const maxTrackScroll = Math.max(1, viewport.scrollWidth - viewport.clientWidth);
    state.timelineDragActive = true;
    elements.eventsList.classList.add("dragging");
    const onMove = (moveEvent) => {
      const deltaRatio = (moveEvent.clientX - startX) / travel;
      viewport.scrollLeft = Math.max(0, Math.min(maxTrackScroll, startScroll + deltaRatio * maxTrackScroll));
    };
    const onUp = () => {
      state.timelineDragActive = false;
      elements.eventsList.classList.remove("dragging");
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      if (state.pendingRefresh) {
        state.pendingRefresh = false;
        refreshCurrentScope();
      }
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };
  track.onclick = (event) => {
    if (event.target.closest("[data-timeline-thumb]")) {
      return;
    }
    const rect = track.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / Math.max(1, rect.width)));
    viewport.scrollLeft = ratio * Math.max(0, viewport.scrollWidth - viewport.clientWidth);
  };
  elements.eventsList.querySelectorAll("[data-timeline-item-id]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedTimelineItemId = button.dataset.timelineItemId || "";
      const nodeId = button.dataset.nodeId || "";
      if (nodeId) {
        selectNode(nodeId, { focus: true });
      }
      syncCurrentScopeState();
      renderTimeline();
    });
  });
}

function renderAll() {
  renderRuntimeBadge();
  renderGlobalItem();
  renderProjectList();
  renderAgentList();
  renderBoardHeading();
  renderGraph();
  renderArtifacts();
  renderDocs();
  renderSkillsPanel();
  renderRuntimePanel();
  renderPreview();
  renderTimeline();
  renderAgentDetail();
  updateBoardMode(state.boardMode);
  updateRightTab(state.rightTab);
  applyTimelineState();
}

async function loadOverview() {
  state.runtime = await fetchJsonOptional("/console/api/runtime");
  state.campaigns = (await fetchJsonOptional("/console/api/campaigns", {}, { limit: 50 })) || [];
  state.drafts = (await fetchJsonOptional("/console/api/drafts", {}, { limit: 20 })) || [];
  state.skillCollections = (await fetchJsonOptional("/console/api/skills/collections")) || [];
  state.skillDiagnostics = await fetchJsonOptional("/console/api/skills/diagnostics");
}

async function loadScopeData(scope, id) {
  if (scope === "global") {
    state.globalBoard = await fetchJsonOptional("/console/api/global/board");
    state.board = null;
    state.graph = null;
    state.campaignDetail = null;
    state.skillCollectionDetail = null;
    state.events = [];
    return;
  }
  state.campaignDetail = await fetchJsonOptional(`/console/api/campaigns/${encodeURIComponent(id)}`);
  state.graph = await fetchJsonOptional(`/console/api/campaigns/${encodeURIComponent(id)}/graph`);
  state.board = await fetchJsonOptional(`/console/api/campaigns/${encodeURIComponent(id)}/board`);
  state.events = (await fetchJsonOptional(`/console/api/campaigns/${encodeURIComponent(id)}/events`, {}, { limit: 24 })) || [];
  const collectionId = state.campaignDetail?.skill_exposure_observation?.collection_id || "";
  state.skillCollectionDetail = collectionId
    ? await fetchJsonOptional(`/console/api/skills/collections/${encodeURIComponent(collectionId)}`)
    : null;
  state.globalBoard = state.globalBoard || null;
}

async function activateGlobal() {
  syncCurrentScopeState();
  state.selection = { scope: "global", id: "" };
  await loadOverview();
  await loadScopeData("global", "");
  applyScopeState("global", "", {});
  const slot = getScopeState("global", "");
  if (!slot.initialized) {
    state.rightTab = "runtime";
    state.boardMode = "graph";
    state.preview = null;
    queueViewportAction({ type: "fit" });
  }
  reconcileSelectionAfterDataLoad();
  await syncPreviewWithCurrentSelection();
  await refreshAgentDetail();
  renderAll();
  syncCurrentScopeState();
}

async function activateCampaign(campaignId) {
  if (!campaignId) {
    return;
  }
  syncCurrentScopeState();
  state.selection = { scope: "campaign", id: campaignId };
  await loadOverview();
  await loadScopeData("campaign", campaignId);
  const graph = extractGraph();
  const defaults = {
    selectedNodeId: graph?.inspector_defaults?.selected_node_id || graph?.nodes?.[0]?.id || "",
    selectedArtifactId: state.board?.preview_defaults?.preview_artifact_id || "",
  };
  applyScopeState("campaign", campaignId, defaults);
  const slot = getScopeState("campaign", campaignId);
  if (!slot.initialized) {
    state.rightTab = "artifacts";
    state.boardMode = "graph";
    state.preview = null;
    state.selectedRecordId = "";
    queueViewportAction({ type: "fit" });
  }
  reconcileSelectionAfterDataLoad();
  await syncPreviewWithCurrentSelection();
  await refreshAgentDetail();
  renderAll();
  syncCurrentScopeState();
}

async function refreshCurrentScope() {
  if (state.timelineDragActive) {
    state.pendingRefresh = true;
    return;
  }
  syncCurrentScopeState();
  const currentScope = state.selection.scope;
  const currentId = state.selection.id;
  await loadOverview();
  await loadScopeData(currentScope, currentId);
  applyScopeState(currentScope, currentId, {});
  reconcileSelectionAfterDataLoad();
  await syncPreviewWithCurrentSelection();
  await refreshAgentDetail();
  renderAll();
  syncCurrentScopeState();
}

async function selectArtifact(artifactId) {
  if (!artifactId || state.selection.scope !== "campaign") {
    return;
  }
  state.selectedArtifactId = artifactId;
  state.selectedRecordId = "";
  await refreshArtifactPreview(artifactId);
  updateRightTab("artifacts");
  updateBoardMode("preview");
  renderArtifacts();
  renderPreview();
}

function selectRecord(recordId) {
  const record = extractDocs().find((item) => item.id === recordId);
  if (!record) {
    return;
  }
  state.selectedRecordId = recordId;
  state.selectedArtifactId = "";
  state.preview = buildRecordPreview(record);
  updateRightTab("docs");
  updateBoardMode("preview");
  syncCurrentScopeState();
  renderDocs();
  renderPreview();
}

function initCanvasControls() {
  let isPanning = false;
  let startX = 0;
  let startY = 0;
  let originX = 0;
  let originY = 0;
  elements.canvas.addEventListener("mousedown", (event) => {
    if (event.button !== 0 || event.target.closest(".node-card")) {
      return;
    }
    isPanning = true;
    startX = event.clientX;
    startY = event.clientY;
    originX = state.view.x;
    originY = state.view.y;
  });
  window.addEventListener("mousemove", (event) => {
    if (!isPanning) {
      return;
    }
    const dx = event.clientX - startX;
    const dy = event.clientY - startY;
    state.view.x = originX + dx;
    state.view.y = originY + dy;
    updateTransform();
    markViewCustomized();
  });
  window.addEventListener("mouseup", () => {
    isPanning = false;
  });
  elements.canvas.addEventListener("wheel", (event) => {
    if (!event.ctrlKey && !event.metaKey) {
      return;
    }
    event.preventDefault();
    const delta = event.deltaY < 0 ? 0.08 : -0.08;
    state.view.scale = Math.min(2.4, Math.max(0.4, state.view.scale + delta));
    updateTransform();
    markViewCustomized();
  });
}

elements.workspaceForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  state.workspace = elements.workspaceInput.value.trim() || ".";
  state.viewStateByScope = {};
  await refreshCurrentScope();
  scheduleRefresh();
});

elements.autoRefreshInput.addEventListener("change", () => {
  state.autoRefresh = elements.autoRefreshInput.checked;
  scheduleRefresh();
});

elements.refreshAllButton.addEventListener("click", refreshCurrentScope);
elements.refreshEventsButton.addEventListener("click", refreshCurrentScope);

elements.toggleTimelineButton.addEventListener("click", () => {
  setTimelineCollapsed(!state.timelineCollapsed);
});

elements.globalItem.addEventListener("click", activateGlobal);
elements.boardModeToggle.querySelectorAll("[data-board-mode]").forEach((button) => {
  button.addEventListener("click", () => updateBoardMode(button.dataset.boardMode || "graph"));
});

elements.rightTabs.querySelectorAll("[data-tab]").forEach((button) => {
  button.addEventListener("click", () => updateRightTab(button.dataset.tab || defaultRightTab(state.selection.scope)));
});

elements.zoomIn.addEventListener("click", () => {
  state.view.scale = Math.min(2.4, state.view.scale + 0.1);
  updateTransform();
  markViewCustomized();
});

elements.zoomOut.addEventListener("click", () => {
  state.view.scale = Math.max(0.4, state.view.scale - 0.1);
  updateTransform();
  markViewCustomized();
});

elements.zoomFit.addEventListener("click", () => {
  queueViewportAction({ type: "fit" });
  renderGraph();
});

elements.themeButtons.forEach((button) => {
  button.addEventListener("click", () => setTheme(button.dataset.theme || "auto"));
});

elements.agentDetailClose.addEventListener("click", closeAgentDetail);
elements.agentDetailBackdrop.addEventListener("click", closeAgentDetail);
elements.agentDetailTabs.querySelectorAll("[data-agent-tab]").forEach((button) => {
  button.addEventListener("click", () => updateAgentDetailTab(button.dataset.agentTab || "records"));
});
elements.agentDetailScroll.addEventListener("scroll", () => {
  state.agentDetailScrollTop = elements.agentDetailScroll.scrollTop;
});
window.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && state.agentDetailOpen) {
    closeAgentDetail();
  }
});

function scheduleRefresh() {
  window.clearInterval(state.timer);
  if (!state.autoRefresh) {
    return;
  }
  state.timer = window.setInterval(() => {
    refreshCurrentScope();
  }, 10000);
}

state.workspace = elements.workspaceInput.value.trim() || ".";
state.autoRefresh = elements.autoRefreshInput.checked;
loadTheme();
loadTimelinePreference();
initCanvasControls();
activateGlobal();
scheduleRefresh();
