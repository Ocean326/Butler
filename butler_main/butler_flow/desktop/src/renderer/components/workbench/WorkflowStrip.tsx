import type { SingleFlowPayload, TimelineEvent } from "../../../shared/dto";

interface WorkflowStripProps {
  payload?: SingleFlowPayload;
}

function EventCell({ event }: { event: TimelineEvent }) {
  return (
    <article className="workflow-cell">
      <span className="workflow-kind">{event.kind}</span>
      <strong>{event.message || event.title || "event"}</strong>
      <span>{event.phase || "runtime"}</span>
    </article>
  );
}

export function WorkflowStrip({ payload }: WorkflowStripProps) {
  const events = payload?.workflow_view.events || [];
  const steps = (payload?.flow_console.step_history as Array<Record<string, unknown>> | undefined) || [];
  const handoff = payload?.role_strip.latest_handoff_summary || {};
  const artifacts = payload?.workflow_view.artifact_refs || [];

  return (
    <section className="panel-shell panel-workflow">
      <header className="panel-header compact">
        <div>
          <p className="panel-kicker">Workflow Surface</p>
          <h2>Execution ribbon</h2>
        </div>
        <div className="panel-stats">
          <span>{steps.length} steps</span>
          <span>{artifacts.length} artifacts</span>
        </div>
      </header>

      <div className="workflow-grid">
        <div className="workflow-column">
          <h3>Workflow Events</h3>
          <div className="workflow-row">
            {events.length === 0 ? <div className="empty-panel">Workflow events will appear here.</div> : events.map((event) => <EventCell key={event.event_id} event={event} />)}
          </div>
        </div>
        <div className="workflow-column narrow">
          <h3>Current Handoff</h3>
          <div className="callout-stack">
            <div className="callout-tile">
              <span>From</span>
              <strong>{String(handoff.from_role_id || "—")}</strong>
            </div>
            <div className="callout-tile">
              <span>To</span>
              <strong>{String(handoff.to_role_id || "—")}</strong>
            </div>
            <div className="callout-tile">
              <span>Summary</span>
              <strong>{String(handoff.summary || "No active handoff")}</strong>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
