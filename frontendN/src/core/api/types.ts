export interface DashboardSummaryVM {
  meals_card: {
    meals_planned: number;
    meals_consumed: number;
    meals_skipped: number;
    next_meal: string | null;
    next_meal_time: string | null;
  };
  macros_card: {
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
  };
  inventory_card: {
    expiring_soon_count: number;
    low_stock_count: number;
    out_of_stock_count: number;
    total_items: number;
  };
  goal_card: {
    goal_type: string;
    current_weight: number;
    target_weight: number;
    weight_change: number;
    current_streak: number;
    goal_progress_percentage: number;
  };
}

export interface TrackingEvent {
  event_type: string;
  message: string;
  timestamp?: string;
  payload?: Record<string, unknown>;
}

export type ChatMessageVM = {
  id: string;
  role: "user" | "assistant";
  content: string;
  intent?: string;
  timestamp: Date;
};
