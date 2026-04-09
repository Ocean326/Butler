import type { ThreadBlockDTO, ThreadHomeDTO, ThreadSummaryDTO } from "../../shared/dto";

export type ShellMessageRole = "user" | "manager";
export type ShellMessageStatus = "ready" | "streaming" | "error";

export interface ShellMessage {
  id: string;
  role: ShellMessageRole;
  body: string;
  createdAt: string;
  meta: string;
  title?: string;
  status?: ShellMessageStatus;
}

export function normalizeConfigPath(value: string): string {
  return String(value || "").trim();
}

export function formatValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.map((item) => formatValue(item)).filter(Boolean).join(" / ");
  }
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    for (const key of ["summary", "label", "title", "goal", "reason", "message", "decision", "response"]) {
      const token = String(record[key] || "").trim();
      if (token) {
        return token;
      }
    }
    return JSON.stringify(value, null, 2);
  }
  return String(value || "").trim();
}

export function shortTime(value: string): string {
  const token = String(value || "").trim();
  if (!token) {
    return "刚刚";
  }
  return token.slice(5, 16).replace(" ", " · ");
}

export function autoResizeTextarea(node: HTMLTextAreaElement | null): void {
  if (!node || typeof window === "undefined") {
    return;
  }
  const maxHeight = Math.floor(window.innerHeight / 3);
  node.style.height = "0px";
  const nextHeight = Math.max(84, Math.min(node.scrollHeight, maxHeight));
  node.style.height = `${nextHeight}px`;
  node.style.overflowY = node.scrollHeight > maxHeight ? "auto" : "hidden";
}

function isManagerSummary(summary: ThreadSummaryDTO): boolean {
  return String(summary.thread_kind || "").trim() === "manager";
}

function isSupervisorSummary(summary: ThreadSummaryDTO): boolean {
  return String(summary.thread_kind || "").trim() === "supervisor";
}

export function blockMeta(block: ThreadBlockDTO): string[] {
  return [block.kind, block.phase || "", ...(block.tags || [])].filter(Boolean);
}

export function buildManagerThreads(home: ThreadHomeDTO | undefined): ThreadSummaryDTO[] {
  const ordered: ThreadSummaryDTO[] = [];
  const seen = new Set<string>();
  const history = home?.history || [];

  function push(summary: ThreadSummaryDTO): void {
    const key = String(summary.manager_session_id || summary.thread_id || "").trim();
    if (!key || seen.has(key)) {
      return;
    }
    seen.add(key);
    ordered.push(summary);
  }

  for (const summary of history) {
    if (isManagerSummary(summary)) {
      push(summary);
    }
  }
  for (const summary of history) {
    if (isSupervisorSummary(summary) && summary.manager_session_id) {
      push({
        ...summary,
        thread_id: `manager:${summary.manager_session_id}`,
        thread_kind: "manager",
        title: summary.title || "Manager Thread",
        subtitle: summary.subtitle || "Continue with Manager"
      });
    }
  }

  const defaultManagerSessionId = String(home?.manager_entry.default_manager_session_id || "").trim();
  if (defaultManagerSessionId && !seen.has(defaultManagerSessionId)) {
    push({
      thread_id: `manager:${defaultManagerSessionId}`,
      thread_kind: "manager",
      title: String(home?.manager_entry.title || "Manager"),
      subtitle: String(home?.manager_entry.draft_summary || "Continue with Manager"),
      status: String(home?.manager_entry.status || "active"),
      created_at: "",
      updated_at: "",
      manager_session_id: defaultManagerSessionId,
      flow_id: String(home?.manager_entry.active_flow_id || ""),
      active_role_id: "",
      current_phase: "",
      badge: "manager",
      tags: ["manager"]
    });
  }

  return ordered;
}

export function isHistoricalStatus(status: string): boolean {
  return ["completed", "failed", "archived", "cancelled"].includes(String(status || "").trim().toLowerCase());
}

function normalizeMessageBody(value: unknown, fallback = ""): string {
  const token = formatValue(value);
  return token || fallback;
}

export function buildConversationMessages(blocks: ThreadBlockDTO[] = []): ShellMessage[] {
  const messages: ShellMessage[] = [];

  for (const block of blocks) {
    const instruction = normalizeMessageBody(block.payload?.instruction);
    const response =
      normalizeMessageBody(block.payload?.response) ||
      normalizeMessageBody(block.payload?.message) ||
      normalizeMessageBody(block.payload?.draft, block.summary) ||
      block.summary;
    const meta = [block.kind, ...(block.tags || [])].filter(Boolean).join(" · ") || "manager";

    if (instruction) {
      messages.push({
        id: `${block.block_id}:user`,
        role: "user",
        body: instruction,
        createdAt: block.created_at,
        meta: "request"
      });
    }

    if (response) {
      messages.push({
        id: `${block.block_id}:manager`,
        role: "manager",
        title: block.title || undefined,
        body: response,
        createdAt: block.created_at,
        meta,
        status: block.status === "attention" ? "error" : "ready"
      });
    }
  }

  return messages;
}

export function composerLabel(isNewThread: boolean): string {
  if (isNewThread) {
    return "Start with Manager";
  }
  return "Continue with Manager";
}

export function composerPlaceholder(isNewThread: boolean): string {
  if (isNewThread) {
    return "例如：/start 一个 Butler Desktop 升级 mission，先帮我收敛需求、验收和团队分工。";
  }
  return "继续和 Manager 协调 mission、追加需求、改验收、或发起下一轮工作。";
}

export function compactPathLabel(value: string, fallback: string): string {
  const token = normalizeConfigPath(value);
  if (!token) {
    return fallback;
  }
  const segments = token.split("/").filter(Boolean);
  if (segments.length <= 3) {
    return token;
  }
  return `…/${segments.slice(-3).join("/")}`;
}
