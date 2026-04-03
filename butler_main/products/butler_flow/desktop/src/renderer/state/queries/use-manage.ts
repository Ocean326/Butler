import { useQuery } from "@tanstack/react-query";
import { electronApi } from "../../lib/electron-api";

export function useManage(configPath: string, enabled: boolean) {
  return useQuery({
    queryKey: ["desktop", "manage", configPath],
    queryFn: () => electronApi.getManageCenter({ configPath }),
    enabled: enabled && Boolean(configPath)
  });
}
