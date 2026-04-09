import { useQuery } from "@tanstack/react-query";
import { electronApi } from "../../lib/electron-api";

const HOME_POLL_MS = 6000;
const THREAD_POLL_MS = 5000;
const QUERY_DEFAULTS = {
  refetchOnWindowFocus: false,
  retry: 1,
  staleTime: 1200,
  gcTime: 60_000
} as const;

export function useThreadHome(configPath: string, enabled = true) {
  return useQuery({
    ...QUERY_DEFAULTS,
    queryKey: ["desktop", "thread-home", configPath],
    queryFn: () => electronApi.getThreadHome({ configPath }),
    refetchInterval: configPath && enabled ? HOME_POLL_MS : false,
    enabled: enabled && Boolean(configPath)
  });
}

export function useManagerThread(configPath: string, managerSessionId: string, enabled = true) {
  return useQuery({
    ...QUERY_DEFAULTS,
    queryKey: ["desktop", "manager-thread", configPath, managerSessionId],
    queryFn: () => electronApi.getManagerThread({ configPath, managerSessionId }),
    refetchInterval: configPath && enabled ? HOME_POLL_MS : false,
    enabled: enabled && Boolean(configPath)
  });
}

export function useSupervisorThread(configPath: string, flowId: string, enabled = true) {
  return useQuery({
    ...QUERY_DEFAULTS,
    queryKey: ["desktop", "supervisor-thread", configPath, flowId],
    queryFn: () => electronApi.getSupervisorThread({ configPath, flowId }),
    refetchInterval: configPath && flowId && enabled ? THREAD_POLL_MS : false,
    enabled: enabled && Boolean(configPath && flowId)
  });
}

export function useAgentFocus(configPath: string, flowId: string, roleId: string, enabled = true) {
  return useQuery({
    ...QUERY_DEFAULTS,
    queryKey: ["desktop", "agent-focus", configPath, flowId, roleId],
    queryFn: () => electronApi.getAgentFocus({ configPath, flowId, roleId }),
    refetchInterval: configPath && flowId && roleId && enabled ? THREAD_POLL_MS : false,
    enabled: enabled && Boolean(configPath && flowId && roleId)
  });
}

export function useTemplateTeam(configPath: string, assetId: string, enabled = true) {
  return useQuery({
    ...QUERY_DEFAULTS,
    queryKey: ["desktop", "template-team", configPath, assetId],
    queryFn: () => electronApi.getTemplateTeam({ configPath, assetId }),
    enabled: enabled && Boolean(configPath && assetId)
  });
}
