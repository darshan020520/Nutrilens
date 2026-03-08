import { useQuery } from "@tanstack/react-query";
import { dashboardClient, type RecentActivityResponse } from "@/core/api/clients";
import { toDashboardSummaryVM } from "@/core/api/adapters";

export function useDashboard() {
  const {
    data: summary,
    isLoading: summaryLoading,
    error: summaryError,
    refetch: refetchSummary,
  } = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: async () => {
      const data = await dashboardClient.getSummary();
      return toDashboardSummaryVM(data);
    },
    refetchInterval: 60000,
    staleTime: 30000,
  });

  const {
    data: activity,
    isLoading: activityLoading,
    error: activityError,
    refetch: refetchActivity,
  } = useQuery<RecentActivityResponse>({
    queryKey: ["dashboard-activity"],
    queryFn: async () => dashboardClient.getRecentActivity(5),
    refetchInterval: 60000,
    staleTime: 30000,
  });

  const isLoading = summaryLoading || activityLoading;
  const error = summaryError || activityError;

  return {
    summary,
    activity,
    isLoading,
    error: error ? "Failed to load dashboard data" : null,
    refetch: () => {
      refetchSummary();
      refetchActivity();
    },
  };
}
