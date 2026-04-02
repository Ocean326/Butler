import { useEffect, useMemo, useRef } from "react";

import type { ArtifactListItem, RecordListItem, TimelineItem } from "../types";
import { cx, formatDate, humanize, shortText, statusTone } from "../lib/format";

interface ActivityDockProps {
  timelineItems: TimelineItem[];
  artifacts: ArtifactListItem[];
  records: RecordListItem[];
  selectedTimelineItemId: string;
  selectedArtifactId: string;
  selectedRecordId: string;
  scrollLeft: number;
  onScrollChange: (left: number) => void;
  onSelectTimelineItem: (item: TimelineItem) => void;
  onSelectArtifact: (artifactId: string) => void;
  onSelectRecord: (recordId: string) => void;
}

export function ActivityDock({
  timelineItems,
  artifacts,
  records,
  selectedTimelineItemId,
  selectedArtifactId,
  selectedRecordId,
  scrollLeft,
  onScrollChange,
  onSelectTimelineItem,
  onSelectArtifact,
  onSelectRecord
}: ActivityDockProps) {
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const outputs = useMemo(
    () =>
      [
        ...artifacts.map((artifact) => ({
          id: artifact.artifact_id,
          kind: "artifact" as const,
          title: artifact.label,
          subtitle: artifact.ref || artifact.kind || "Artifact",
          detail: artifact.created_at || "",
          displayDetail: artifact.created_at || "No timestamp"
        })),
        ...records.map((record) => ({
          id: record.record_id,
          kind: "record" as const,
          title: record.title,
          subtitle: record.summary || record.kind || "Record",
          detail: record.created_at || "",
          displayDetail: record.created_at || "No timestamp"
        }))
      ].sort((left, right) => {
        const byTime = String(left.detail).localeCompare(String(right.detail));
        if (byTime !== 0) {
          return byTime;
        }
        return left.title.localeCompare(right.title);
      }),
    [artifacts, records]
  );

  const columnCount = Math.max(timelineItems.length, outputs.length, 1);
  const trackStyle = useMemo(
    () => ({
      gridTemplateColumns: `repeat(${columnCount}, minmax(176px, 220px))`
    }),
    [columnCount]
  );

  useEffect(() => {
    if (viewportRef.current) {
      viewportRef.current.scrollLeft = scrollLeft;
    }
  }, [scrollLeft, columnCount]);

  return (
    <section className="activity-dock">
      <div className="activity-dock__header">
        <div>
          <p className="eyebrow">Turn Ledger</p>
          <h3>Receipts, events, and outputs</h3>
        </div>
        <div className="activity-dock__meta">
          <span className="micro-meta">{timelineItems.length} ledger items</span>
          <span className="micro-meta">{outputs.length} outputs</span>
        </div>
      </div>

      <div
        ref={viewportRef}
        className="activity-dock__viewport"
        onScroll={(event) => onScrollChange(event.currentTarget.scrollLeft)}
      >
        <div className="activity-dock__canvas">
          <div className="activity-dock__row activity-dock__row--events" style={trackStyle}>
            {timelineItems.length ? (
              timelineItems.map((item) => (
                <button
                  key={item.id}
                  className={cx("activity-card", "activity-card--event", selectedTimelineItemId === item.id && "is-active")}
                  title={item.display_title || humanize(item.kind)}
                  onClick={() => onSelectTimelineItem(item)}
                >
                  <div className="activity-card__meta">
                    <span className={`timeline-dot timeline-dot--${statusTone(item.status)}`} />
                    <span>{item.display_time || formatDate(item.timestamp)}</span>
                  </div>
                  <strong>{shortText(item.display_title || humanize(item.kind), 56) || humanize(item.kind)}</strong>
                  <p>{shortText(item.display_brief || item.node_id || item.step_id || "", 92)}</p>
                </button>
              ))
            ) : (
              <div className="activity-dock__empty" style={{ gridColumn: "1 / -1" }}>
                No turn receipts or events projected yet.
              </div>
            )}
          </div>

          <div className="activity-dock__axis" style={trackStyle}>
            {Array.from({ length: columnCount }).map((_, index) => (
              <div key={index} className="activity-dock__axis-slot">
                <span className="activity-dock__axis-line" />
                <span className={`activity-dock__axis-dot ${index < timelineItems.length ? "is-active" : ""}`} />
              </div>
            ))}
          </div>

          <div className="activity-dock__row activity-dock__row--outputs" style={trackStyle}>
            {outputs.length ? (
              outputs.map((item) => (
                <button
                  key={item.id}
                  className={cx(
                    "activity-card",
                    "activity-card--output",
                    item.kind === "artifact" && selectedArtifactId === item.id && "is-active",
                    item.kind === "record" && selectedRecordId === item.id && "is-active"
                  )}
                  title={item.title}
                  onClick={() => {
                    if (item.kind === "artifact") {
                      onSelectArtifact(item.id);
                    } else {
                      onSelectRecord(item.id);
                    }
                  }}
                >
                  <div className="activity-card__meta">
                    <span className="micro-meta">{humanize(item.kind)}</span>
                    <span>{formatDate(item.displayDetail)}</span>
                  </div>
                  <strong>{shortText(item.title, 56) || item.title}</strong>
                  <p>{shortText(item.subtitle, 92)}</p>
                </button>
              ))
            ) : (
              <div className="activity-dock__empty" style={{ gridColumn: "1 / -1" }}>
                No artifacts or records available yet.
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
