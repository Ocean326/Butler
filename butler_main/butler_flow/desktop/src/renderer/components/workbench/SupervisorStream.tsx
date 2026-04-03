import type { SupervisorViewDTO, TimelineEvent } from "../../../shared/dto";

interface SupervisorStreamProps {
  view?: SupervisorViewDTO;
}

function renderTime(value: unknown): string {
  const token = String(value ?? "").trim();
  if (!token) {
    return "pending";
  }
  return token.replace("T", " ").replace("Z", "");
}

function EventRow({ event }: { event: TimelineEvent }) {
  return (
    <article className="event-row">
      <div className="event-time">{renderTime(event.created_at)}</div>
      <div className="event-body">
        <div className="event-head">
          <span className={`event-badge event-badge-${event.family || "system"}`}>{event.kind}</span>
          <span className="event-phase">{event.phase || "runtime"}</span>
        </div>
        <div className="event-message">{event.message || event.title || "No message"}</div>
      </div>
    </article>
  );
}

export function SupervisorStream({ view }: SupervisorStreamProps) {
  const header = view?.header || {};
  const events = view?.events || [];
  const pointers = view?.pointers || {};

  return (
    <section className="panel-shell panel-supervisor">
      <header className="panel-header">
        <div>
          <p className="panel-kicker">Supervisor Stream</p>
          <h2>{String(header.goal || header.flow_id || "Focused flow")}</h2>
        </div>
        <div className="panel-stats">
          <span>{String(header.status || "unknown")}</span>
          <span>{String(header.phase || "idle")}</span>
          <span>{String(header.active_role_id || "unassigned")}</span>
        </div>
      </header>

      <div className="supervisor-pointers">
        <div>
          <span>Approval</span>
          <strong>{String(header.approval_state || "not_required")}</strong>
        </div>
        <div>
          <span>Runtime</span>
          <strong>
            {String(pointers.runtime_elapsed_seconds || 0)}s / {String(pointers.max_runtime_seconds || 0)}s
          </strong>
        </div>
        <div>
          <span>Session Mode</span>
          <strong>{String(pointers.supervisor_session_mode || "default")}</strong>
        </div>
      </div>

      <div className="event-stream">
        {events.length === 0 ? (
          <div className="empty-panel">No supervisor events yet. Once the flow emits decisions, they will land here.</div>
        ) : (
          events.map((event) => <EventRow key={event.event_id} event={event} />)
        )}
      </div>
    </section>
  );
}
