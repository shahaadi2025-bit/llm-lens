import { useQuery } from "@tanstack/react-query";
import { api } from "../services/api";

export function useHealth() {
  return useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 30_000 });
}
