import { useQuery } from "@tanstack/react-query";
import { electronApi } from "../../lib/electron-api";

export function useThreadHome(configPath: string, enabled = true) {
  return useQuery({
    queryKey: ["desktop", "thread-home", configPath],
    queryFn: () => electronApi.getThreadHome({ configPath }),
    refetchInterval: configPath && enabled ? 6000 : false,
    enabled: enabled && Boolean(configPath)
  });
}

export function useManagerThread(configPath: string, managerSessionId: string, enabled = true) {
  return useQuery({
    queryKey: ["desktop", "manager-thread", configPath, managerSessionId],
    queryFn: () => electronApi.getManagerThread({ configPath, managerSessionId }),
    refetchInterval: configPath && enabled ? 6000 : false,
    enabled: enabled && Boolean(configPath)
  });
}

export function useSupervisorThread(configPath: string, flowId: string, enabled = true) {
  return useQuery({
    queryKey: ["desktop", "supervisor-thread", configPath, flowId],
    queryFn: () => electronApi.getSupervisorThread({ configPath, flowId }),
    refetchInterval: configPath && flowId && enabled ? 5000 : false,
    enabled: enabled && Boolean(configPath && flowId)
  });
}

export function useAgentFocus(configPath: string, flowId: string, roleId: string, enabled = true) {
  return useQuery({
    queryKey: ["desktop", "agent-focus", configPath, flowId, roleId],
    queryFn: () => electronApi.getAgentFocus({ configPath, flowId, roleId }),
    refetchInterval: configPath && flowId && roleId && enabled ? 5000 : false,
    enabled: enabled && Boolean(configPath && flowId && roleId)
  });
}

export function useTemplateTeam(configPath: string, assetId: string, enabled = true) {
  return useQuery({
    queryKey: ["desktop", "template-team", configPath, assetId],
    queryFn: () => electronApi.getTemplateTeam({ configPath, assetId }),
    enabled: enabled && Boolean(configPath)
  });
}
