// frontend/src/app/dashboard/meals/components/WeekView.tsx
"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { 
  RefreshCw, 
  Download, 
  ShoppingCart, 
  Check, 
  Clock, 
  XCircle,
  ChevronRight
} from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import SwapMealDialog from "./SwapMealDialog";
import RecipeDetailsDialog from "./RecipeDetailsDialog";

interface Macros {
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
}

interface Meal {
  meal_type: string;
  recipe_id: number;
  recipe_name: string;
  macros: Macros;
  status: "logged" | "pending" | "skipped";
  planned_time?: string;
}

interface DayPlan {
  date: string;
  day_name: string;
  meals: Meal[];
}

interface WeekPlan {
  id: number;
  has_plan: boolean;
  week_start: string;
  week_end: string;
  days: DayPlan[];
  grocery_list?: any;
  message?: string;
}

export function WeekView() {
  const queryClient = useQueryClient();
  const todaySummary = queryClient.getQueryData(["tracking", "today"]);
  const [selectedMeal, setSelectedMeal] = useState<{
    day: number;
    meal: Meal;
  } | null>(null);
  const [mealToSwap, setMealToSwap] = useState<{
    day: number;
    meal: Meal;
  } | null>(null);
  const [recipeToView, setRecipeToView] = useState<number | null>(null);
  const [showRecipeDialog, setShowRecipeDialog] = useState(false);
  const [showGroceryList, setShowGroceryList] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);

  // Fetch current week's meal plan with status
  const { data: weekPlan, isLoading, error } = useQuery<WeekPlan>({
    queryKey: ["meal-plan", "current"],
    queryFn: async () => {
        const response = await api.get("/meal-plans/current/with-status");
        const data = response.data;

        // Handle case where no plan exists for current week
        // Check for plan_data existence rather than has_plan flag
        if (!data.plan_data || Object.keys(data.plan_data).length === 0) {
          return {
            id: data.id || 0,
            has_plan: false,
            week_start: data.week_start_date || new Date().toISOString(),
            week_end: "",
            days: [],
            message: data.message || "No meal plan found for this week."
          };
        }

        // 🧩 Transform backend structure → frontend format
        const days: any[] = [];

        if (data.plan_data) {
        // Parse week start date to calculate individual day dates
        const weekStartDate = new Date(data.week_start_date);

        for (const [dayName, dayData] of Object.entries(data.plan_data)) {
            // Type guard for dayData
            const typedDayData = dayData as any;

            // Extract day index from "day_0", "day_1", etc.
            const dayIndex = parseInt(dayName.split('_')[1]);

            // Calculate the actual date for this day
            const dayDate = new Date(weekStartDate);
            dayDate.setDate(weekStartDate.getDate() + dayIndex);

            const mealsArray = Object.entries(typedDayData.meals).map(
            ([mealType, meal]: [string, any]) => ({
                meal_type: mealType,
                recipe_id: meal.id,
                recipe_name: meal.title,
                macros: meal.macros_per_serving,
                goals: meal.goals || [],
                dietary_tags: meal.dietary_tags || [],
                suitable_meal_times: meal.suitable_meal_times || [],
                prep_time_min: meal.prep_time_min ?? null,
                cook_time_min: meal.cook_time_min ?? null,
                status: meal.status || "pending", // Use status from backend
            })
            );

            days.push({
            date: dayDate.toISOString(),
            day_name: dayDate.toLocaleDateString("en-US", { weekday: "long" }),
            day_calories: typedDayData.day_calories ?? null,
            day_macros: typedDayData.day_macros ?? {},
            meals: mealsArray,
            });
        }
        }

        const weekPlan: WeekPlan = {
        id: data.id,
        has_plan: true,
        week_start: data.week_start_date,
        week_end: "", // optional
        days,
        };

        console.log("🧩 Transformed weekPlan:", weekPlan);
        return weekPlan;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    });





  // Fetch grocery list
  const { data: groceryList } = useQuery({
    queryKey: ["meal-plan", weekPlan?.id, "grocery-list"],
    queryFn: async () => {
      if (!weekPlan?.id) return null;
      const response = await api.get(`/meal-plans/${weekPlan.id}/grocery-list`);
      return response.data;
    },
    enabled: !!weekPlan?.id && weekPlan?.has_plan,
  });

  // Regenerate meal plan mutation
  const regenerateMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post("/meal-plans/generate", {
        start_date: new Date().toISOString(),
        days: 7,
        preferences: {},
        use_inventory: true,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["meal-plan"] });
      toast.success("New meal plan generated successfully!");
      setIsRegenerating(false);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to generate meal plan");
      setIsRegenerating(false);
    },
  });

  // Swap meal mutation
  const swapMealMutation = useMutation({
    mutationFn: async ({
      day,
      mealType,
      newRecipeId,
    }: {
      day: number;
      mealType: string;
      newRecipeId: number;
    }) => {
      const response = await api.post(`/meal-plans/${weekPlan?.id}/swap-meal`, {
        day,
        meal_type: mealType,
        new_recipe_id: newRecipeId,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["meal-plan"] });
      toast.success("Meal swapped successfully!");
      setSelectedMeal(null);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to swap meal");
    },
  });

  const handleRegenerate = () => {
    setIsRegenerating(true);
    regenerateMutation.mutate();
  };

  const getMealStatusIcon = (status: string) => {
    switch (status) {
      case "logged":
        return <Check className="h-4 w-4 text-green-600" />;
      case "pending":
        return <Clock className="h-4 w-4 text-yellow-600" />;
      case "skipped":
        return <XCircle className="h-4 w-4 text-gray-400" />;
      default:
        return null;
    }
  };

  const getMealStatusBadge = (status: string) => {
    switch (status) {
      case "logged":
        return (
          <Badge variant="default" className="bg-green-100 text-green-800 hover:bg-green-100">
            Logged
          </Badge>
        );
      case "pending":
        return (
          <Badge variant="default" className="bg-yellow-100 text-yellow-800 hover:bg-yellow-100">
            Pending
          </Badge>
        );
      case "skipped":
        return (
          <Badge variant="secondary">Skipped</Badge>
        );
      default:
        return null;
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex gap-3">
          <Skeleton className="h-10 w-40" />
          <Skeleton className="h-10 w-32" />
          <Skeleton className="h-10 w-48" />
        </div>
        {[1, 2, 3, 4, 5, 6, 7].map((i) => (
          <Card key={i}>
            <CardHeader>
              <Skeleton className="h-6 w-32" />
            </CardHeader>
            <CardContent>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {[1, 2, 3, 4].map((j) => (
                  <Skeleton key={j} className="h-32" />
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>
          Failed to load meal plan. Please try again.
        </AlertDescription>
      </Alert>
    );
  }

  if (!weekPlan?.has_plan) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <div className="max-w-md space-y-4">
          <h3 className="text-lg font-semibold">No Active Meal Plan</h3>
          <p className="text-muted-foreground">
            {weekPlan?.message || "Generate a weekly meal plan to get started!"}
          </p>
          <Button
            onClick={handleRegenerate}
            disabled={isRegenerating}
            size="lg"
          >
            {isRegenerating && <RefreshCw className="mr-2 h-4 w-4 animate-spin" />}
            Generate Meal Plan
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Action Buttons */}
      <div className="flex flex-wrap gap-3">
        <Button
          onClick={handleRegenerate}
          disabled={isRegenerating}
          variant="default"
        >
          {isRegenerating ? (
            <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="mr-2 h-4 w-4" />
          )}
          Regenerate Plan
        </Button>

        <Button variant="outline">
          <Download className="mr-2 h-4 w-4" />
          Export Plan
        </Button>

        <Button
          variant="outline"
          onClick={() => setShowGroceryList(true)}
          disabled={!groceryList}
        >
          <ShoppingCart className="mr-2 h-4 w-4" />
          View Grocery List
        </Button>
      </div>

      {/* Week Plan Grid */}
      <div className="grid gap-4">
        {weekPlan.days.map((day, dayIndex) => (
          <Card key={day.date}>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base font-semibold">
                  {day.day_name}
                </CardTitle>
                <span className="text-sm text-muted-foreground">
                  {new Date(day.date).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                  })}
                </span>
              </div>
            </CardHeader>

            <CardContent>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {day.meals.map((meal) => (
                  <div
                    key={meal.meal_type}
                    className="group relative rounded-lg border p-3 hover:bg-accent/50 transition-colors cursor-pointer"
                    onClick={() => setSelectedMeal({ day: dayIndex, meal })}
                  >
                    {/* Meal Type & Status */}
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium capitalize">
                        {meal.meal_type}
                      </span>
                      {getMealStatusIcon(meal.status)}
                    </div>

                    {/* Recipe Name */}
                    <h4 className="text-sm font-semibold mb-2 line-clamp-2">
                      {meal.recipe_name}
                    </h4>

                    {/* Macros */}
                    <div className="text-xs text-muted-foreground space-y-1 mb-2">
                      <div>{Math.round(meal.macros?.calories || 0)} cal</div>
                      <div>
                        P: {Math.round(meal.macros?.protein_g || 0)}g |{" "}
                        C: {Math.round(meal.macros?.carbs_g || 0)}g |{" "}
                        F: {Math.round(meal.macros?.fat_g || 0)}g
                      </div>
                    </div>

                    {/* Status Badge */}
                    {getMealStatusBadge(meal.status)}

                    {/* Hover indicator */}
                    <div className="absolute right-2 top-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Grocery List Dialog */}
      <Dialog open={showGroceryList} onOpenChange={setShowGroceryList}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Grocery List</DialogTitle>
            <DialogDescription>
              Items needed for this week's meal plan
            </DialogDescription>
          </DialogHeader>

          {groceryList && (
            <div className="space-y-4">
              {Object.entries(groceryList.categorized || {}).map(
                ([category, items]: [string, any]) => (
                  <div key={category}>
                    <h4 className="font-semibold capitalize mb-2">{category}</h4>
                    <ul className="space-y-2">
                      {items.map((item: any, idx: number) => (
                        <li
                          key={idx}
                          className="flex items-center justify-between text-sm"
                        >
                          <span>{item.item_name}</span>
                          <span className="text-muted-foreground">
                            {Math.round(item.to_buy)}g
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Meal Details Dialog (placeholder for swap functionality) */}
      <Dialog
        open={!!selectedMeal}
        onOpenChange={() => setSelectedMeal(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="capitalize">
              {selectedMeal?.meal.meal_type} - {selectedMeal?.meal.recipe_name}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            <div>
              <h4 className="font-semibold mb-2">Macros</h4>
              <div className="grid grid-cols-4 gap-2 text-sm">
                <div>
                  <div className="text-muted-foreground">Calories</div>
                  <div className="font-medium">
                    {Math.round(selectedMeal?.meal.macros?.calories || 0)}
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground">Protein</div>
                  <div className="font-medium">
                    {Math.round(selectedMeal?.meal.macros?.protein_g || 0)}g
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground">Carbs</div>
                  <div className="font-medium">
                    {Math.round(selectedMeal?.meal.macros?.carbs_g || 0)}g
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground">Fat</div>
                  <div className="font-medium">
                    {Math.round(selectedMeal?.meal.macros?.fat_g || 0)}g
                  </div>
                </div>
              </div>
            </div>

            <div className="flex gap-2">
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => {
                  if (selectedMeal) {
                    setRecipeToView(selectedMeal.meal.recipe_id);
                    setShowRecipeDialog(true);
                    setSelectedMeal(null);
                  }
                }}
              >
                View Recipe
              </Button>
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => {
                  if (selectedMeal) {
                    setMealToSwap(selectedMeal);
                    setSelectedMeal(null);
                  }
                }}
              >
                Swap Meal
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Swap Meal Dialog */}
      <SwapMealDialog
        open={!!mealToSwap}
        onOpenChange={(open) => !open && setMealToSwap(null)}
        planId={weekPlan?.id || 0}
        currentRecipe={
          mealToSwap
            ? {
                id: mealToSwap.meal.recipe_id,
                title: mealToSwap.meal.recipe_name,
                macros_per_serving: mealToSwap.meal.macros,
              }
            : null
        }
        day={mealToSwap?.day || 0}
        mealType={mealToSwap?.meal.meal_type || ""}
      />

      {/* Recipe Details Dialog */}
      <RecipeDetailsDialog
        recipeId={recipeToView}
        open={showRecipeDialog}
        onOpenChange={setShowRecipeDialog}
      />
    </div>
  );
}