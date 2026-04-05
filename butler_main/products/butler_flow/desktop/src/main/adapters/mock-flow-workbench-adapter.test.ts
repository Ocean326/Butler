import { describe, expect, it } from "vitest";
import { MockFlowWorkbenchAdapter } from "./mock-flow-workbench-adapter";

describe("MockFlowWorkbenchAdapter", () => {
  it("keeps alternate-flow agent focus on the requested flow context", async () => {
    const adapter = new MockFlowWorkbenchAdapter();

    const payload = await adapter.getAgentFocus("flow_visual_refresh", "implementer");

    expect(payload.flow_id).toBe("flow_visual_refresh");
    expect(payload.thread.flow_id).toBe("flow_visual_refresh");
    expect(payload.thread.manager_session_id).toBe("manager_session_mock_02");
    expect(payload.summary.flow_id).toBe("flow_visual_refresh");
    expect(payload.blocks[1]?.summary).toContain("history -> supervisor -> manager");
  });
});
