import { useQuery } from "@tanstack/react-query";
import { electronApi } from "../../lib/electron-api";

export function useFlow(configPath: string, flowId: string) {
  return useQuery({
    queryKey: ["desktop", "flow", configPath, flowId],
    queryFn: () => electronApi.getFlow({ configPath, flowId }),
    refetchInterval: flowId ? 5000 : false,
    enabled: Boolean(configPath && flowId)
  });
}
