import type { ReactNode } from "react";
import { useState } from "react";

import type { AccessDiagnostics, CampaignSummary, FrontdoorDraftView, RuntimeStatus, ScopeMode } from "../types";
import { formatDate, humanize, shortText, statusTone } from "../lib/format";
import { StatusPill } from "./status-pill";

type ThemeMode = "light" | "dark";

const MAX_VISIBLE_CAMPAIGNS = 5;
const MAX_VISIBLE_DRAFTS = 4;

interface CommandRailProps {
  workspace: string;
  runtime?: RuntimeStatus;
  access?: AccessDiagnostics;
  campaigns: CampaignSummary[];
  drafts: FrontdoorDraftView[];
  scope: ScopeMode;
  selectedCampaignId: string;
  selectedDraftId: string;
  theme: ThemeMode;
  collapsed: boolean;
  controlsEnabled: boolean;
  onWorkspaceChange: (workspace: string) => void;
  onActivateGlobal: () => void;
  onActivateCampaign: (campaignId: string) => void;
  onActivateDrafts: () => void;
  onSelectDraft: (draftId: string) => void;
  onOpenControls: () => void;
  onToggleTheme: () => void;
  onToggleCollapsed: () => void;
}

export function CommandRail({
  workspace,
  runtime,
  access,
  campaigns,
  drafts,
  scope,
  selectedCampaignId,
  selectedDraftId,
  theme,
  collapsed,
  controlsEnabled,
  onWorkspaceChange,
  onActivateGlobal,
  onActivateCampaign,
  onActivateDrafts,
  onSelectDraft,
  onOpenControls,
  onToggleTheme,
  onToggleCollapsed
}: CommandRailProps) {
  const [sections, setSections] = useState({
    scopes: true,
    campaigns: true,
    drafts: false,
    access: false
  });
  const [expandedLists, setExpandedLists] = useState({
    campaigns: false,
    drafts: false
  });
  const runtimeState = humanize(runtime?.process_state as string) || "Unknown";
  const visibleCampaigns = expandedLists.campaigns ? campaigns : campaigns.slice(0, MAX_VISIBLE_CAMPAIGNS);
  const visibleDrafts = expandedLists.drafts ? drafts : drafts.slice(0, MAX_VISIBLE_DRAFTS);

  if (collapsed) {
    return (
      <aside className="command-rail command-rail--collapsed">
        <button className="rail-icon-button" onClick={onToggleCollapsed} title="Expand sidebar">
          Rail
        </button>
        <button className="rail-icon-button" onClick={onToggleTheme} title={`Switch to ${theme === "light" ? "dark" : "light"} mode`}>
          Theme
        </button>
        {controlsEnabled && (
          <button className="rail-icon-button" onClick={onOpenControls} title="Open controls">
            Ctrl
          </button>
        )}
        <button className={`rail-icon-button ${scope === "global" ? "is-active" : ""}`} onClick={onActivateGlobal} title="Global queue">
          G
        </button>
        <button className={`rail-icon-button ${scope === "drafts" ? "is-active" : ""}`} onClick={onActivateDrafts} title="Draft studio">
          D
        </button>
        {campaigns.slice(0, 4).map((campaign) => (
          <button
            key={campaign.campaign_id}
            className={`rail-icon-button ${scope === "campaign" && selectedCampaignId === campaign.campaign_id ? "is-active" : ""}`}
            onClick={() => onActivateCampaign(campaign.campaign_id)}
            title={campaign.title || campaign.campaign_id}
          >
            {shortText(humanize(campaign.current_phase || campaign.status || "campaign"), 1) || "C"}
          </button>
        ))}
      </aside>
    );
  }

  return (
    <aside className="command-rail">
      <header className="rail-toolbar">
        <div>
          <p className="eyebrow">Butler Console</p>
          <strong>Operator Rail</strong>
        </div>
        <div className="rail-toolbar__actions">
          <button className="rail-tool-button" onClick={onToggleTheme}>
            {theme === "light" ? "Dark mode" : "Light mode"}
          </button>
          {controlsEnabled && (
            <button className="rail-tool-button" onClick={onOpenControls}>
              Controls
            </button>
          )}
          <button className="rail-tool-button" onClick={onToggleCollapsed}>
            Collapse
          </button>
        </div>
      </header>

      <section className="rail-panel rail-panel--hero">
        <h1>Console</h1>
        <p className="rail-copy">Campaign-first operator harness with one-turn supervision, natural-language progress, and durable recovery anchors.</p>
        <div className="rail-kpi-grid">
          <div className="rail-kpi">
            <span>Campaigns</span>
            <strong>{campaigns.length}</strong>
          </div>
          <div className="rail-kpi">
            <span>Drafts</span>
            <strong>{drafts.length}</strong>
          </div>
          <div className="rail-kpi">
            <span>State</span>
            <strong>{runtimeState}</strong>
          </div>
        </div>
        <div className="workspace-box">
          <label htmlFor="workspace">Workspace</label>
          <input
            id="workspace"
            value={workspace}
            spellCheck={false}
            onChange={(event) => onWorkspaceChange(event.currentTarget.value)}
          />
        </div>
        <div className="runtime-stack">
          <StatusPill
            label={humanize(runtime?.phase as string) || humanize(runtime?.run_state as string) || "Runtime"}
            tone={statusTone(runtime?.process_state as string)}
          />
          <span className="runtime-note">{shortText((runtime?.note as string) || "No runtime note available.", 96) || "No runtime note available."}</span>
        </div>
      </section>

      <RailDisclosure
        title="Scopes"
        meta={scope === "drafts" ? "Draft" : scope === "campaign" ? "Campaign" : "Global"}
        open={sections.scopes}
        onToggle={() => setSections((current) => ({ ...current, scopes: !current.scopes }))}
      >
        <button className={`nav-tile ${scope === "global" ? "is-active" : ""}`} onClick={onActivateGlobal}>
          <div>
            <strong>Global Queue</strong>
            <p>Runtime health and live campaign routing.</p>
          </div>
        </button>
        <button className={`nav-tile ${scope === "drafts" ? "is-active" : ""}`} onClick={onActivateDrafts}>
          <div>
            <strong>Draft Studio</strong>
            <p>Draft editing and launch preparation.</p>
          </div>
          <span className="meta-chip">{drafts.length}</span>
        </button>
      </RailDisclosure>

      <RailDisclosure
        title="Campaigns"
        meta={String(campaigns.length)}
        open={sections.campaigns}
        onToggle={() => setSections((current) => ({ ...current, campaigns: !current.campaigns }))}
      >
        <div className="nav-list">
          {visibleCampaigns.map((campaign) => (
            <button
              key={campaign.campaign_id}
              className={`nav-list-item ${scope === "campaign" && selectedCampaignId === campaign.campaign_id ? "is-active" : ""}`}
              onClick={() => onActivateCampaign(campaign.campaign_id)}
              title={campaign.title || campaign.campaign_id}
            >
              <div>
                <strong>{shortText(campaign.title || campaign.campaign_id, 54) || campaign.campaign_id}</strong>
                <p>
                  {shortText(
                    String(
                      (campaign.task_summary as Record<string, unknown> | undefined)?.next_action ||
                        ((campaign.task_summary as Record<string, unknown> | undefined)?.progress as Record<string, unknown> | undefined)?.latest_summary ||
                        campaign.bundle_root ||
                        campaign.mode_id ||
                        "No current summary."
                    ),
                    68
                  )}
                </p>
                {Boolean(campaign.canonical_session_id) && (
                  <span className="micro-meta">{shortText(campaign.canonical_session_id, 44)}</span>
                )}
              </div>
              <StatusPill label={humanize(campaign.status) || "Unknown"} tone={statusTone(campaign.status)} />
            </button>
          ))}
          {campaigns.length > MAX_VISIBLE_CAMPAIGNS && (
            <button
              className="nav-list-more"
              onClick={() =>
                setExpandedLists((current) => ({
                  ...current,
                  campaigns: !current.campaigns
                }))
              }
            >
              {expandedLists.campaigns ? "Show fewer campaigns" : `Show ${campaigns.length - MAX_VISIBLE_CAMPAIGNS} more campaigns`}
            </button>
          )}
          {!campaigns.length && <div className="empty-block">No campaigns yet.</div>}
        </div>
      </RailDisclosure>

      <RailDisclosure
        title="Drafts"
        meta={String(drafts.length)}
        open={sections.drafts}
        onToggle={() => setSections((current) => ({ ...current, drafts: !current.drafts }))}
      >
        <div className="nav-list">
          {visibleDrafts.map((draft) => (
            <button
              key={draft.draft_id}
              className={`nav-list-item ${selectedDraftId === draft.draft_id ? "is-active" : ""}`}
              onClick={() => onSelectDraft(draft.draft_id)}
              title={draft.goal || draft.draft_id}
            >
              <div>
                <strong>{shortText(draft.goal || draft.draft_id, 62) || draft.draft_id}</strong>
                <p>{shortText(draft.selected_template_id || draft.mode_id || "Unshaped draft", 48)}</p>
              </div>
              <span className="micro-meta">{draft.linked_campaign_id ? "Launched" : "Draft"}</span>
            </button>
          ))}
          {drafts.length > MAX_VISIBLE_DRAFTS && (
            <button
              className="nav-list-more"
              onClick={() =>
                setExpandedLists((current) => ({
                  ...current,
                  drafts: !current.drafts
                }))
              }
            >
              {expandedLists.drafts ? "Show fewer drafts" : `Show ${drafts.length - MAX_VISIBLE_DRAFTS} more drafts`}
            </button>
          )}
          {!drafts.length && <div className="empty-block">No drafts yet.</div>}
        </div>
      </RailDisclosure>

      <RailDisclosure
        title="Access"
        meta={`${access?.listen_host || "127.0.0.1"}:${access?.port || 8765}`}
        open={sections.access}
        onToggle={() => setSections((current) => ({ ...current, access: !current.access }))}
      >
        <p>{shortText(access?.note || "Console access endpoints and last runtime refresh.", 128)}</p>
        <div className="link-stack">
          {(access?.local_urls || []).slice(0, 2).map((url) => (
            <a key={url} href={url} target="_blank" rel="noreferrer">
              {url}
            </a>
          ))}
        </div>
        <span className="micro-meta">Updated {formatDate(runtime?.updated_at as string)}</span>
      </RailDisclosure>
    </aside>
  );
}

function RailDisclosure({
  title,
  meta,
  open,
  onToggle,
  children
}: {
  title: string;
  meta?: string;
  open: boolean;
  onToggle: () => void;
  children: ReactNode;
}) {
  return (
    <section className={`rail-panel rail-disclosure ${open ? "is-open" : ""}`}>
      <button className="rail-disclosure__toggle" onClick={onToggle}>
        <div>
          <strong>{title}</strong>
          {meta && <span className="micro-meta">{meta}</span>}
        </div>
        <span className="rail-disclosure__state">{open ? "Hide" : "Show"}</span>
      </button>
      {open && <div className="rail-disclosure__body">{children}</div>}
    </section>
  );
}
