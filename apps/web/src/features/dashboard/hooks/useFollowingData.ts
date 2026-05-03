import { useQuery } from "@tanstack/react-query";

import { listFollows, listTeams } from "../../../shared/api";

export function useFollowingData(token: string) {
  return useQuery({
    queryKey: ["following-page", token],
    queryFn: async () => {
      const [follows, teams] = await Promise.all([listFollows(token), listTeams()]);
      return {
        follows,
        teams,
      };
    },
    refetchInterval: 120_000,
  });
}
