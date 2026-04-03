export function cx(...values: Array<string | false | null | undefined>): string {
  return values.filter(Boolean).join(" ");
}

export function humanize(value: string | null | undefined): string {
  return String(value ?? "")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (part) => part.toUpperCase());
}

export function shortText(value: string | null | undefined, limit = 120): string {
  const text = String(value ?? "").trim();
  if (text.length <= limit) {
    return text;
  }
  return `${text.slice(0, Math.max(0, limit - 1)).trimEnd()}…`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "No timestamp";
  }
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}

export function statusTone(value: string | null | undefined): string {
  const normalized = String(value ?? "").toLowerCase();
  if (["running", "current", "active"].includes(normalized)) {
    return "running";
  }
  if (["next", "pending", "queued", "waiting"].includes(normalized)) {
    return "queued";
  }
  if (["blocked", "failed", "error"].includes(normalized)) {
    return "danger";
  }
  if (["completed", "done", "success"].includes(normalized)) {
    return "success";
  }
  return "muted";
}
