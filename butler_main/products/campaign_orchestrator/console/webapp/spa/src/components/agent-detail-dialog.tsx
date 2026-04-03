import type { AgentDetailEnvelope, AgentTab } from "../types";
import { formatDate, humanize, shortText, statusTone } from "../lib/format";
import { StatusPill } from "./status-pill";

const DETAIL_TABS: AgentTab[] = ["records", "planned", "artifacts", "raw"];

export function AgentDetailDialog({
  open,
  detail,
  tab,
  onClose,
  onChangeTab
}: {
  open: boolean;
  detail?: AgentDetailEnvelope;
  tab: AgentTab;
  onClose: () => void;
  onChangeTab: (tab: AgentTab) => void;
}) {
  if (!open) {
    return null;
  }

  return (
    <div className="detail-overlay" onClick={onClose}>
      <section className="detail-dialog" onClick={(event) => event.stopPropagation()}>
        <header className="detail-header">
          <div>
            <p className="eyebrow">Agent Detail</p>
            <h2 title={detail?.title || "Loading agent detail..."}>{shortText(detail?.title || "Loading agent detail...", 120)}</h2>
            <p>{shortText(detail?.subtitle || detail?.node_id || "No subtitle", 160)}</p>
          </div>
          <button className="icon-button" onClick={onClose}>
            Close
          </button>
        </header>

        <div className="detail-summary">
          <StatusPill
            label={humanize(detail?.execution_state || detail?.status) || "Unknown"}
            tone={statusTone(detail?.execution_state || detail?.status)}
          />
          <span className="micro-meta">{detail?.role_label || detail?.role_id || "No role"}</span>
          <span className="micro-meta">{formatDate(detail?.updated_at)}</span>
        </div>

        <div className="tab-row">
          {DETAIL_TABS.map((item) => (
            <button key={item} className={tab === item ? "is-active" : ""} onClick={() => onChangeTab(item)}>
              {humanize(item)}
            </button>
          ))}
        </div>

        <div className="detail-grid">
          <aside className="detail-overview">
            {Object.entries(detail?.overview || {}).map(([key, value]) => (
              <div key={key} className="data-card">
                <h3>{humanize(key)}</h3>
                <p>{shortText(String(value ?? ""), 220) || "N/A"}</p>
              </div>
            ))}
          </aside>

          <section className="detail-main">
            {tab === "records" && <DetailRecords items={detail?.live_records || []} />}
            {tab === "planned" && <DetailObject object={detail?.planned_input || {}} />}
            {tab === "artifacts" && <DetailRecords items={detail?.artifacts || []} />}
            {tab === "raw" && <DetailRecords items={detail?.raw_records || []} />}
          </section>
        </div>
      </section>
    </div>
  );
}

function DetailRecords({ items }: { items: Array<Record<string, unknown>> }) {
  if (!items.length) {
    return <div className="empty-block">No items in this section.</div>;
  }

  return (
    <div className="detail-records">
      {items.map((item, index) => (
        <article key={`${item.id || item.record_id || index}`} className="data-card">
          <pre>{JSON.stringify(item, null, 2)}</pre>
        </article>
      ))}
    </div>
  );
}

function DetailObject({ object }: { object: Record<string, unknown> }) {
  const entries = Object.entries(object);
  if (!entries.length) {
    return <div className="empty-block">No planned input available.</div>;
  }

  return (
    <div className="detail-records">
      {entries.map(([key, value]) => (
        <article key={key} className="data-card">
          <h3>{humanize(key)}</h3>
          <pre>{JSON.stringify(value, null, 2)}</pre>
        </article>
      ))}
    </div>
  );
}
