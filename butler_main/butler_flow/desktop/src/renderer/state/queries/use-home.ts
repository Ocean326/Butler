import { useQuery } from "@tanstack/react-query";
import { electronApi } from "../../lib/electron-api";

export function useHome(configPath: string) {
  return useQuery({
    queryKey: ["desktop", "home", configPath],
    queryFn: () => electronApi.getHome({ configPath }),
    refetchInterval: configPath ? 6000 : false,
    enabled: Boolean(configPath)
  });
}
