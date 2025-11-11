"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Check, Clock, XCircle, Utensils, UtensilsCrossed } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import ExternalMealDialog from "./ExternalMealDialog";

interface MacroGroup {
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g: number;
}

interface MealDetail {
  id: number;
  meal_type: string;
  planned_time: string;
  recipe: string;
  status: "pending" | "consumed" | "skipped";
  consumed_time?: string;
  recipe_id?: number;
  macros?: MacroGroup;
}

interface TodayData {
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

export function TodayView() {
  const queryClient = useQueryClient();
  const [selectedMeal, setSelectedMeal] = useState<MealDetail | null>(null);
  const [skipDialogOpen, setSkipDialogOpen] = useState(false);
  const [skipReason, setSkipReason] = useState("");
  const [externalMealDialogOpen, setExternalMealDialogOpen] = useState(false);
  const [mealToReplace, setMealToReplace] = useState<MealDetail | null>(null);

  // Fetch today's meals and progress
  const { data: todayData, isLoading, error } = useQuery<TodayData>({
    queryKey: ["tracking", "today"],
    queryFn: async () => (await api.get("/tracking/today")).data,
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  });

  // Log meal mutation
  const logMealMutation = useMutation({
    mutationFn: async (mealId: number) => {
      const response = await api.post("/tracking/log-meal", {
        meal_log_id: mealId,
        consumed_datetime: new Date().toISOString(),
        portion_multiplier: 1.0,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tracking", "today"] });
      queryClient.invalidateQueries({ queryKey: ["meal-plan"] });
      toast.success("Meal logged successfully!");
      setSelectedMeal(null);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to log meal");
    },
  });

  // Skip meal mutation
  const skipMealMutation = useMutation({
    mutationFn: async ({
      mealLogId,
      reason,
    }: {
      mealLogId: number;
      reason: string;
    }) => {
      const response = await api.post("/tracking/skip-meal", {
        meal_log_id: mealLogId,
        skip_reason: reason,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tracking", "today"] });
      queryClient.invalidateQueries({ queryKey: ["meal-plan"] });
      toast.success("Meal skipped");
      setSkipDialogOpen(false);
      setSkipReason("");
      setSelectedMeal(null);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to skip meal");
    },
  });

  const handleLogMeal = (meal: MealDetail) => {
    logMealMutation.mutate(meal.id);
  };

  const handleSkipMeal = () => {
    if (selectedMeal) {
      skipMealMutation.mutate({
        mealLogId: selectedMeal.id,
        reason: skipReason,
      });
    }
  };

  const getMealIcon = (mealType: string) => <Utensils className="h-5 w-5" />;

  const getMealStatusBadge = (status: string) => {
    switch (status) {
      case "consumed":
        return (
          <Badge className="bg-green-100 text-green-800">
            <Check className="mr-1 h-3 w-3" />
            Logged
          </Badge>
        );
      case "pending":
        return (
          <Badge className="bg-yellow-100 text-yellow-800">
            <Clock className="mr-1 h-3 w-3" />
            Pending
          </Badge>
        );
      case "skipped":
        return (
          <Badge variant="secondary">
            <XCircle className="mr-1 h-3 w-3" />
            Skipped
          </Badge>
        );
      default:
        return null;
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-48" />
          </CardHeader>
          <CardContent className="space-y-4">
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-24" />
            ))}
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>
          Failed to load today's meals. Please try again.
        </AlertDescription>
      </Alert>
    );
  }

  if (!todayData) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">No data available for today</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Macro Progress Section */}
      <Card>
        <CardHeader>
          <CardTitle>Today's Progress</CardTitle>
          <p className="text-sm text-muted-foreground">
            {new Date().toLocaleDateString("en-US", {
              weekday: "long",
              month: "long",
              day: "numeric",
            })}
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Calories */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium">Calories</span>
              <span className="text-muted-foreground">
                {Math.round(todayData.total_macros.calories)} /{" "}
                {Math.round(todayData.target_macros.calories)}
              </span>
            </div>
            <Progress
              value={
                (todayData.total_macros.calories /
                  todayData.target_macros.calories) *
                100
              }
              className="h-2"
            />
          </div>

          {/* Protein */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium">Protein</span>
              <span className="text-muted-foreground">
                {Math.round(todayData.total_macros.protein_g)}g /{" "}
                {Math.round(todayData.target_macros.protein_g)}g
              </span>
            </div>
            <Progress
              value={
                (todayData.total_macros.protein_g /
                  todayData.target_macros.protein_g) *
                100
              }
              className="h-2"
            />
          </div>

          {/* Carbs */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium">Carbs</span>
              <span className="text-muted-foreground">
                {Math.round(todayData.total_macros.carbs_g)}g /{" "}
                {Math.round(todayData.target_macros.carbs_g)}g
              </span>
            </div>
            <Progress
              value={
                (todayData.total_macros.carbs_g /
                  todayData.target_macros.carbs_g) *
                100
              }
              className="h-2"
            />
          </div>

          {/* Fat */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium">Fat</span>
              <span className="text-muted-foreground">
                {Math.round(todayData.total_macros.fat_g)}g /{" "}
                {Math.round(todayData.target_macros.fat_g)}g
              </span>
            </div>
            <Progress
              value={
                (todayData.total_macros.fat_g /
                  todayData.target_macros.fat_g) *
                100
              }
              className="h-2"
            />
          </div>

          {/* Compliance */}
          <div className="pt-2 border-t">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Daily Compliance</span>
              <span className="text-lg font-bold text-primary">
                {Math.round(todayData.compliance_rate)}%
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Meals Timeline */}
      <Card>
        <CardHeader>
          <CardTitle>Today's Meals</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {todayData.meal_details.map((meal) => (
              <div
                key={meal.id}
                className="flex items-start gap-4 p-4 rounded-lg border hover:bg-accent/50 transition-colors"
              >
                <div className="mt-1">{getMealIcon(meal.meal_type)}</div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-4 mb-2">
                    <div>
                      <h4 className="font-semibold capitalize">
                        {meal.meal_type}
                      </h4>
                      <p className="text-sm text-muted-foreground">
                        {meal.planned_time &&
                          new Date(meal.planned_time).toLocaleTimeString(
                            "en-US",
                            { hour: "numeric", minute: "2-digit" }
                          )}
                      </p>
                    </div>
                    {getMealStatusBadge(meal.status)}
                  </div>

                  <p className="text-sm font-medium mb-2">{meal.recipe}</p>

                  <div className="flex items-center gap-4 text-xs text-muted-foreground mb-3">
                    <span>{Math.round(meal.macros?.calories || 0)} cal</span>
                    <span>P: {Math.round(meal.macros?.protein_g || 0)}g</span>
                    <span>C: {Math.round(meal.macros?.carbs_g || 0)}g</span>
                    <span>F: {Math.round(meal.macros?.fat_g || 0)}g</span>
                  </div>

                  {meal.status === "pending" && (
                    <div className="flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        onClick={() => handleLogMeal(meal)}
                        disabled={logMealMutation.isPending}
                      >
                        Log Meal
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setMealToReplace(meal);
                          setExternalMealDialogOpen(true);
                        }}
                      >
                        <UtensilsCrossed className="mr-1 h-3 w-3" />
                        External Meal
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setSelectedMeal(meal);
                          setSkipDialogOpen(true);
                        }}
                      >
                        Skip
                      </Button>
                    </div>
                  )}

                  {meal.status === "consumed" && meal.consumed_time && (
                    <p className="text-xs text-muted-foreground">
                      Logged at{" "}
                      {new Date(meal.consumed_time).toLocaleTimeString("en-US", {
                        hour: "numeric",
                        minute: "2-digit",
                      })}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Skip Meal Dialog */}
      <Dialog open={skipDialogOpen} onOpenChange={setSkipDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Skip Meal</DialogTitle>
            <DialogDescription>
              Are you sure you want to skip {selectedMeal?.meal_type}?
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div>
              <Label htmlFor="skip-reason">Reason (optional)</Label>
              <Textarea
                id="skip-reason"
                placeholder="e.g., Not hungry, eating out, etc."
                value={skipReason}
                onChange={(e) => setSkipReason(e.target.value)}
                rows={3}
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setSkipDialogOpen(false);
                setSkipReason("");
              }}
            >
              Cancel
            </Button>
              <Button
                onClick={handleSkipMeal}
                disabled={skipMealMutation.isPending}
              >
                Skip Meal
              </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* External Meal Dialog */}
      <ExternalMealDialog
        open={externalMealDialogOpen}
        onOpenChange={setExternalMealDialogOpen}
        mealLogId={mealToReplace?.id}
        mealType={mealToReplace?.meal_type}
        onSuccess={() => {
          setMealToReplace(null);
        }}
      />
    </div>
  );
}
