import { useEffect, useMemo } from "react";
import {
  Background,
  Controls,
  MiniMap,
  Position,
  ReactFlow,
  useReactFlow
} from "@xyflow/react";
import type { Edge, Node, Viewport } from "@xyflow/react";

import type { BoardNodeView, BoardSnapshot } from "../types";
import { cx, humanize, shortText, statusTone } from "../lib/format";

interface GraphCanvasProps {
  board?: BoardSnapshot;
  selectedNodeId: string;
  onSelectNode: (nodeId: string) => void;
  onOpenDetail: (campaignId: string, nodeId: string) => void;
  viewport?: Viewport;
  onViewportChange: (viewport: Viewport) => void;
}

export function GraphCanvas({
  board,
  selectedNodeId,
  onSelectNode,
  onOpenDetail,
  viewport,
  onViewportChange
}: GraphCanvasProps) {
  const graph = board?.nodes ?? [];
  const initialNodes = useMemo<Node[]>(
    () =>
      graph.map((node, index) => buildFlowNode(node, index, selectedNodeId)),
    [graph, selectedNodeId]
  );

  const initialEdges = useMemo<Edge[]>(
    () =>
      (board?.edges ?? []).map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        animated: Boolean(edge.active),
        className: cx("flow-edge", edge.active && "flow-edge--active"),
        label: edge.label
      })),
    [board?.edges]
  );

  const reactFlow = useReactFlow();

  useEffect(() => {
    if (!graph.length) {
      return;
    }
    const frame = window.requestAnimationFrame(() => {
      if (!viewport) {
        reactFlow.fitView({ duration: 250, padding: graph.length > 4 ? 0.12 : 0.18 });
        return;
      }
      reactFlow.setViewport(viewport, { duration: 250 });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [graph.length, reactFlow, viewport, board?.snapshot_id]);

  if (!board || !graph.length) {
    return (
      <div className="graph-stage graph-stage--empty">
        <div className="graph-empty">
          <strong>No graph nodes yet.</strong>
          <p>Once the workspace publishes nodes, the graph surface will render here.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="graph-stage">
      <ReactFlow
        nodes={initialNodes}
        edges={initialEdges}
        fitView
        fitViewOptions={{ padding: graph.length > 4 ? 0.12 : 0.18 }}
        minZoom={0.4}
        maxZoom={1.6}
        nodesDraggable={false}
        nodesConnectable={false}
        onMoveEnd={(_, nextViewport) => onViewportChange(nextViewport)}
        onNodeClick={(_, node) => onSelectNode(node.id)}
        onNodeDoubleClick={(_, node) => {
          const matched = graph.find((item) => item.id === node.id);
          if (!matched?.detail_available) {
            return;
          }
          onOpenDetail(matched.detail_campaign_id || board.scope_id, matched.detail_node_id || matched.id);
        }}
        nodeOrigin={[0, 0]}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={28} size={1} />
        <MiniMap pannable zoomable />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

function buildFlowNode(node: BoardNodeView, index: number, selectedNodeId: string): Node {
  const position = resolveNodePosition(node, index);
  const width = clamp(node.size?.w ?? 256, 208, 280);
  const minHeight = clamp(node.size?.h ?? 156, 136, 184);
  const detail =
    shortText(
      node.display_brief ||
        node.subtitle ||
        [humanize(node.phase || node.step_id || node.id), node.role_label].filter(Boolean).join(" · "),
      100
    ) || "No additional detail.";

  return {
    id: node.id,
    position,
    draggable: false,
    selectable: true,
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      label: (
        <article className="flow-node-card" title={node.display_title || node.title}>
          <div className="flow-node-card__top">
            <span className="flow-node-card__step">
              {humanize(node.phase || node.step_id || node.id) || "Node"}
            </span>
            <span className={`chip-tone chip-tone--${statusTone(node.status)}`}>
              {humanize(node.status) || "Unknown"}
            </span>
          </div>
          <strong>{shortText(node.display_title || node.title || node.id, 60) || node.id}</strong>
          <p>{detail}</p>
          <div className="flow-node-card__meta">
            {node.role_label && <span className="chip-detail">{node.role_label}</span>}
            {node.iteration_label && <span className="chip-detail">{node.iteration_label}</span>}
          </div>
        </article>
      )
    },
    style: {
      width,
      minHeight
    },
    className: cx("flow-node", selectedNodeId === node.id && "flow-node--selected")
  };
}

function resolveNodePosition(node: BoardNodeView, index: number): { x: number; y: number } {
  if (typeof node.position?.x === "number" && typeof node.position?.y === "number") {
    return {
      x: node.position.x,
      y: node.position.y
    };
  }

  return {
    x: 120 + (index % 2) * 340,
    y: 100 + Math.floor(index / 2) * 190
  };
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}
