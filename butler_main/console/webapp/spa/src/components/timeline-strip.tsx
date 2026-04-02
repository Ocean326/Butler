import { useEffect, useRef } from "react";

import type { TimelineItem } from "../types";
import { cx, formatDate, humanize, shortText, statusTone } from "../lib/format";

interface TimelineStripProps {
  scopeKey: string;
  items: TimelineItem[];
  selectedItemId: string;
  scrollLeft: number;
  onSelect: (item: TimelineItem) => void;
  onScrollChange: (left: number) => void;
}

export function TimelineStrip({
  items,
  selectedItemId,
  scrollLeft,
  onSelect,
  onScrollChange
}: TimelineStripProps) {
  const viewportRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (viewportRef.current) {
      viewportRef.current.scrollLeft = scrollLeft;
    }
  }, [scrollLeft, items.length]);

  if (!items.length) {
    return <div className="timeline-empty">No timeline items available.</div>;
  }

  return (
    <div
      className="timeline-strip"
      ref={viewportRef}
      onScroll={(event) => onScrollChange(event.currentTarget.scrollLeft)}
    >
      <div className="timeline-row">
        {items.map((item) => (
          <button
            key={item.id}
            className={cx("timeline-card", selectedItemId === item.id && "is-active")}
            onClick={() => onSelect(item)}
            title={item.display_title || humanize(item.kind)}
          >
            <div className="timeline-topline">
              <span className={`timeline-dot timeline-dot--${statusTone(item.status)}`} />
              <span>{item.display_time || formatDate(item.timestamp)}</span>
            </div>
            <strong>{shortText(item.display_title || humanize(item.kind), 52) || humanize(item.kind)}</strong>
            <p>{shortText(item.display_brief || item.node_id || item.step_id || "", 80)}</p>
          </button>
        ))}
      </div>
    </div>
  );
}
