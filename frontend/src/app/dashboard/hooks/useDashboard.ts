import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface MealsCardData {
  meals_planned: number;
  meals_consumed: number;
  meals_skipped: number;
  next_meal: string | null;
  next_meal_time: string | null;
}

interface MacrosCardData {
  calories_consumed: number;
  calories_target: number;
  calories_percentage: number;
  protein_consumed: number;
  protein_target: number;
  protein_percentage: number;
  carbs_consumed: number;
  carbs_target: number;
  carbs_percentage: number;
  fat_consumed: number;
  fat_target: number;
  fat_percentage: number;
}

interface InventoryCardData {
  expiring_soon_count: number;
  low_stock_count: number;
  out_of_stock_count: number;
  total_items: number;
}

interface GoalCardData {
  goal_type: string;
  current_weight: number;
  target_weight: number;
  weight_change: number;
  current_streak: number;
  goal_progress_percentage: number;
}

interface DashboardSummary {
  meals_card: MealsCardData;
  macros_card: MacrosCardData;
  inventory_card: InventoryCardData;
  goal_card: GoalCardData;
}

interface ActivityItem {
  id: number;
  type: string;
  description: string;
  timestamp: string;
  icon: string;
}

interface RecentActivityData {
  activities: ActivityItem[];
  total_count: number;
}

export function useDashboard() {
  // Fetch dashboard summary
  const {
    data: summary,
    isLoading: summaryLoading,
    error: summaryError,
    refetch: refetchSummary,
  } = useQuery<DashboardSummary>({
    queryKey: ["dashboard-summary"],
    queryFn: async () => {
      const response = await api.get("/dashboard/summary");
      return response.data;
    },
    refetchInterval: 60000, // Refetch every minute
    staleTime: 30000, // Data stays fresh for 30 seconds
  });

  // Fetch recent activity
  const {
    data: activity,
    isLoading: activityLoading,
    error: activityError,
    refetch: refetchActivity,
  } = useQuery<RecentActivityData>({
    queryKey: ["dashboard-activity"],
    queryFn: async () => {
      const response = await api.get("/dashboard/recent-activity", {
        params: { limit: 5 },
      });
      return response.data;
    },
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