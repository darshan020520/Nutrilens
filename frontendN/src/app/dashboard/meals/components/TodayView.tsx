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
import { Check, Clock, XCircle, Utensils, UtensilsCrossed, Lightbulb, CheckCircle2 } from "lucide-react";
import { api, getEndpoint } from "@/lib/api";
import { toast } from "sonner";
import ExternalMealDialog from "./ExternalMealDialog";

interface ActionResult {
  type: "log" | "skip";
  recipeName: string;
  recommendations: string[];
  remainingCalories?: number;
  adherenceRate?: number;
}

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
  recommendations?: string[];
}

export function TodayView() {
  const queryClient = useQueryClient();
  const [selectedMeal, setSelectedMeal] = useState<MealDetail | null>(null);
  const [skipDialogOpen, setSkipDialogOpen] = useState(false);
  const [skipReason, setSkipReason] = useState("");
  const [externalMealDialogOpen, setExternalMealDialogOpen] = useState(false);
  const [mealToReplace, setMealToReplace] = useState<MealDetail | null>(null);
  const [actionResult, setActionResult] = useState<ActionResult | null>(null);

  // Fetch today's meals and progress
  const { data: todayData, isLoading, error } = useQuery<TodayData>({
    queryKey: ["tracking", "today"],
    queryFn: async () => (await api.get(getEndpoint("/tracking/today"))).data,
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  });

  // Log meal mutation
  const logMealMutation = useMutation({
    mutationFn: async (mealId: number) => {
      const response = await api.post(getEndpoint("/tracking/log-meal"), {
        meal_log_id: mealId,
        consumed_datetime: new Date().toISOString(),
        portion_multiplier: 1.0,
      });
      return response.data;
    },
    onSuccess: (data: any) => {
      queryClient.invalidateQueries({ queryKey: ["tracking", "today"] });
      queryClient.invalidateQueries({ queryKey: ["meal-plan"] });

      // Extract recommendations (handle both string and RecommendationItem objects)
      const recs: string[] = (data?.recommendations || [])
        .map((rec: any) => (typeof rec === "string" ? rec : rec.description))
        .filter(Boolean);

      setActionResult({
        type: "log",
        recipeName: data?.recipe_name || "Meal",
        recommendations: recs,
        remainingCalories: data?.remaining_targets?.calories,
      });

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
      const response = await api.post(getEndpoint("/tracking/skip-meal"), {
        meal_log_id: mealLogId,
        skip_reason: reason,
      });
      return response.data;
    },
    onSuccess: (data: any) => {
      queryClient.invalidateQueries({ queryKey: ["tracking", "today"] });
      queryClient.invalidateQueries({ queryKey: ["meal-plan"] });

      // Extract recommendations (handle both string and object formats)
      const recs: string[] = (data?.recommendations || [])
        .map((rec: any) => (typeof rec === "string" ? rec : rec.description))
        .filter(Boolean);

      setSkipDialogOpen(false);
      setSkipReason("");

      setActionResult({
        type: "skip",
        recipeName: data?.recipe_name || selectedMeal?.recipe || "Meal",
        recommendations: recs,
        adherenceRate: data?.updated_adherence_rate,
      });

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

      {/* AI Recommendations */}
      {todayData.recommendations && todayData.recommendations.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Lightbulb className="h-4 w-4 text-yellow-500" />
              AI Recommendations
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {todayData.recommendations.map((rec, idx) => (
                <li key={idx} className="flex items-start gap-2 text-sm">
                  <span className="text-muted-foreground mt-0.5">-</span>
                  <span>{rec}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

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

      {/* Action Result Dialog */}
      <Dialog open={!!actionResult} onOpenChange={(open) => { if (!open) setActionResult(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-green-600" />
              {actionResult?.type === "log"
                ? `${actionResult.recipeName} logged!`
                : `${actionResult?.recipeName} skipped`}
            </DialogTitle>
            <DialogDescription>
              {actionResult?.type === "log"
                ? "Your meal has been recorded and inventory updated."
                : "Meal marked as skipped."}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {/* Remaining calories / adherence */}
            {actionResult?.type === "log" && actionResult.remainingCalories !== undefined && (
              <div className="flex items-center justify-between p-3 rounded-lg bg-muted">
                <span className="text-sm font-medium">Remaining today</span>
                <span className="text-lg font-bold text-primary">
                  {Math.round(actionResult.remainingCalories)} cal
                </span>
              </div>
            )}
            {actionResult?.type === "skip" && actionResult.adherenceRate !== undefined && (
              <div className="flex items-center justify-between p-3 rounded-lg bg-muted">
                <span className="text-sm font-medium">Weekly adherence</span>
                <span className="text-lg font-bold text-primary">
                  {Math.round(actionResult.adherenceRate * 100)}%
                </span>
              </div>
            )}

            {/* Recommendations */}
            {actionResult?.recommendations && actionResult.recommendations.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium flex items-center gap-1.5">
                  <Lightbulb className="h-4 w-4 text-yellow-500" />
                  Recommendations
                </h4>
                <ul className="space-y-2">
                  {actionResult.recommendations.map((rec, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-sm text-muted-foreground">
                      <span className="mt-0.5 shrink-0">-</span>
                      <span>{rec}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button onClick={() => setActionResult(null)}>
              Done
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
