import { shortText } from "../lib/format";
import type { PreviewEnvelope, RecordListItem } from "../types";

export function PreviewPane({
  preview,
  record,
  chromeless = false
}: {
  preview?: PreviewEnvelope;
  record?: RecordListItem;
  chromeless?: boolean;
}) {
  if (!preview && !record) {
    return (
      <section className="preview-pane">
        <div className="empty-block">Select an artifact or a record to preview.</div>
      </section>
    );
  }

  const title = preview?.title || record?.preview_title || record?.title || "Preview";
  const content = preview?.content || record?.preview_content || "";
  const language = preview?.language || record?.preview_language || "text";

  return (
    <section className={`preview-pane ${chromeless ? "preview-pane--chromeless" : ""}`}>
      {!chromeless && (
        <header className="panel-header">
          <div>
            <p className="eyebrow">Preview</p>
            <h3 title={title}>{shortText(title, 96) || "Preview"}</h3>
          </div>
          <span className="micro-meta">{language}</span>
        </header>
      )}
      <pre>{content || "No preview content."}</pre>
    </section>
  );
}
