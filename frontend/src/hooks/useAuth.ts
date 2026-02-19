import { useQuery } from "@tanstack/react-query";
import { fetchMe } from "../lib/api";

export function useAuth() {
  const { data: user, isLoading, error } = useQuery({
    queryKey: ["me"],
    queryFn: fetchMe,
    retry: false,
  });

  return {
    user: user ?? null,
    isAuthenticated: !!user,
    isLoading,
    isError: !!error,
  };
}
