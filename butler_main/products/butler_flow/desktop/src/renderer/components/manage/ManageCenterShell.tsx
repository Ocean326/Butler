import type { ManageCenterDTO } from "../../../shared/dto";

interface ManageCenterShellProps {
  payload?: ManageCenterDTO;
  selectedAssetId: string;
  onSelectAsset: (assetId: string) => void;
  surfaceTitle: string;
}

export function ManageCenterShell({ payload, selectedAssetId, onSelectAsset, surfaceTitle }: ManageCenterShellProps) {
  const items = payload?.assets.items || [];
  const active = items.find((item) => String(item.asset_id || item.id || "") === selectedAssetId) || payload?.selected_asset || {};
  const activeId = String(active.asset_id || active.id || selectedAssetId || "");

  return (
    <div className="manage-shell">
      <section className="panel-shell manage-list-panel">
        <header className="panel-header compact">
          <div>
            <p className="panel-kicker">{surfaceTitle}</p>
            <h2>Contracts, assets, and guidance</h2>
          </div>
        </header>
        <div className="manage-list">
          {items.length === 0 ? (
            <div className="empty-panel">No contract assets are available for this config.</div>
          ) : (
            items.map((item, index) => {
              const itemId = String(item.asset_id || item.id || `asset-${index}`);
              return (
                <button
                  key={itemId}
                  className={`manage-item ${itemId === activeId ? "is-active" : ""}`}
                  onClick={() => onSelectAsset(itemId)}
                  type="button"
                >
                  <span>{String(item.status || "active")}</span>
                  <strong>{String(item.title || item.name || itemId)}</strong>
                  <p>{String(item.summary || item.synopsis || "No summary")}</p>
                </button>
              );
            })
          )}
        </div>
      </section>

      <section className="panel-shell manage-detail-panel">
        <header className="panel-header compact">
          <div>
            <p className="panel-kicker">Selected Asset</p>
            <h2>{String(active.title || active.name || "No asset selected")}</h2>
          </div>
        </header>
        <div className="manage-columns">
          <div className="manage-column">
            <h3>Manager Notes</h3>
            <p>{payload?.manager_notes || "Manager notes will appear here once an asset is selected."}</p>
            <h3>Review Checklist</h3>
            <ul className="manage-list-plain">
              {(payload?.review_checklist || []).map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
          <div className="manage-column">
            <h3>Role Guidance</h3>
            <div className="drawer-stack">
              {Object.entries(payload?.role_guidance || {}).map(([key, value]) => (
                <div className="kv-row" key={key}>
                  <span>{key}</span>
                  <strong>{String(value)}</strong>
                </div>
              ))}
            </div>
            <h3>Bundle Manifest</h3>
            <pre className="runtime-pre">{JSON.stringify(payload?.bundle_manifest || {}, null, 2)}</pre>
          </div>
        </div>
      </section>
    </div>
  );
}
