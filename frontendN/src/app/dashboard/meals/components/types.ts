export interface MacroGroup {
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g: number;
}

export interface MealDetail {
  id: number;
  meal_type: string;
  planned_time: string;
  recipe: string;
  status: "pending" | "consumed" | "skipped";
  consumed_time?: string;
  recipe_id?: number;
  macros?: MacroGroup;
}

export interface TodayData {
  date: string;
  meals_planned: number;
  meals_consumed: number;
  meals_skipped: number;
  total_calories: number;
  total_macros: MacroGroup;
  target_calories: number;
  target_macros: MacroGroup;
  remaining_calories: number;
  remaining_macros: MacroGroup;
  compliance_rate: number;
  meal_details: MealDetail[];
}