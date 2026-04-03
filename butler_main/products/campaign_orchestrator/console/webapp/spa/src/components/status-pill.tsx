import { cx } from "../lib/format";

export function StatusPill({ label, tone }: { label: string; tone: string }) {
  return <span className={cx("status-pill", `status-pill--${tone}`)}>{label}</span>;
}
