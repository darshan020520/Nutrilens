"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loader2, ArrowRight, TrendingUp, TrendingDown } from "lucide-react";
import { useRecipeAlternatives, useSwapMeal } from "../hooks/useMealPlan";

interface SwapMealDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  planId: number;
  currentRecipe: {
    id: number;
    title: string;
    macros_per_serving: {
      calories: number;
      protein_g: number;
      carbs_g: number;
      fat_g: number;
    };
  } | null;
  day: number;
  mealType: string;
}

export default function SwapMealDialog({
  open,
  onOpenChange,
  planId,
  currentRecipe,
  day,
  mealType,
}: SwapMealDialogProps) {
  const [selectedAlternative, setSelectedAlternative] = useState<number | null>(null);

  const { data: alternatives, isLoading } = useRecipeAlternatives(
    planId,
    currentRecipe?.id || null,
    5
  );

  const swapMeal = useSwapMeal(planId);

  const handleSwap = async () => {
    if (!selectedAlternative) return;

    await swapMeal.mutateAsync({
      day,
      mealType,
      newRecipeId: selectedAlternative,
    });

    onOpenChange(false);
    setSelectedAlternative(null);
  };

  const handleClose = () => {
    setSelectedAlternative(null);
    onOpenChange(false);
  };

  const MacroDifference = ({ value, label }: { value: number; label: string }) => {
    if (Math.abs(value) < 0.5) return null;

    return (
      <div className="flex items-center gap-1 text-xs">
        {value > 0 ? (
          <TrendingUp className="h-3 w-3 text-green-600" />
        ) : (
          <TrendingDown className="h-3 w-3 text-red-600" />
        )}
        <span className={value > 0 ? "text-green-600" : "text-red-600"}>
          {value > 0 ? "+" : ""}
          {Math.round(value)} {label}
        </span>
      </div>
    );
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Swap Meal</DialogTitle>
          <DialogDescription>
            {currentRecipe ? (
              <>
                Find alternatives for <strong>{currentRecipe.title}</strong>
              </>
            ) : (
              "Select a meal to swap"
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {isLoading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              <span className="ml-2 text-sm text-muted-foreground">
                Finding alternatives...
              </span>
            </div>
          )}

          {!isLoading && alternatives && alternatives.length === 0 && (
            <div className="text-center py-8 text-muted-foreground">
              <p>No suitable alternatives found.</p>
              <p className="text-sm mt-2">
                Try adjusting your dietary preferences or try a different meal.
              </p>
            </div>
          )}

          {!isLoading && alternatives && alternatives.length > 0 && (
            <>
              <div className="text-sm text-muted-foreground mb-4">
                Found {alternatives.length} alternative{alternatives.length > 1 ? "s" : ""} with
                similar macros
              </div>

              <div className="space-y-3">
                {alternatives.map((alt: any) => {
                  const recipe = alt.recipe;
                  const isSelected = selectedAlternative === recipe.id;

                  return (
                    <Card
                      key={recipe.id}
                      className={`cursor-pointer transition-all ${
                        isSelected
                          ? "ring-2 ring-blue-500 border-blue-500"
                          : "hover:border-gray-400"
                      }`}
                      onClick={() => setSelectedAlternative(recipe.id)}
                    >
                      <CardContent className="p-4">
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-2">
                              <h4 className="font-semibold">{recipe.title}</h4>
                              <Badge variant="secondary" className="text-xs">
                                {Math.round(alt.similarity_score * 100)}% match
                              </Badge>
                            </div>

                            <div className="grid grid-cols-2 gap-2 text-sm">
                              <div>
                                <span className="text-muted-foreground">Calories:</span>{" "}
                                <span className="font-medium">
                                  {Math.round(recipe.macros_per_serving.calories)}
                                </span>
                                <MacroDifference
                                  value={alt.calorie_difference}
                                  label="cal"
                                />
                              </div>

                              <div>
                                <span className="text-muted-foreground">Protein:</span>{" "}
                                <span className="font-medium">
                                  {Math.round(recipe.macros_per_serving.protein_g)}g
                                </span>
                                <MacroDifference
                                  value={alt.protein_difference}
                                  label="g"
                                />
                              </div>

                              <div>
                                <span className="text-muted-foreground">Carbs:</span>{" "}
                                <span className="font-medium">
                                  {Math.round(recipe.macros_per_serving.carbs_g)}g
                                </span>
                                <MacroDifference
                                  value={alt.carbs_difference}
                                  label="g"
                                />
                              </div>

                              <div>
                                <span className="text-muted-foreground">Fat:</span>{" "}
                                <span className="font-medium">
                                  {Math.round(recipe.macros_per_serving.fat_g)}g
                                </span>
                                <MacroDifference
                                  value={alt.fat_difference}
                                  label="g"
                                />
                              </div>
                            </div>

                            {recipe.tags && recipe.tags.length > 0 && (
                              <div className="flex gap-1 mt-2 flex-wrap">
                                {recipe.tags.slice(0, 3).map((tag: string) => (
                                  <Badge key={tag} variant="outline" className="text-xs">
                                    {tag}
                                  </Badge>
                                ))}
                              </div>
                            )}
                          </div>

                          {isSelected && (
                            <div className="flex-shrink-0">
                              <div className="h-8 w-8 rounded-full bg-blue-500 flex items-center justify-center">
                                <ArrowRight className="h-4 w-4 text-white" />
                              </div>
                            </div>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>

              <div className="flex gap-2 justify-end pt-4 border-t">
                <Button variant="outline" onClick={handleClose}>
                  Cancel
                </Button>
                <Button
                  onClick={handleSwap}
                  disabled={!selectedAlternative || swapMeal.isPending}
                >
                  {swapMeal.isPending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Swapping...
                    </>
                  ) : (
                    "Swap Meal"
                  )}
                </Button>
              </div>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
