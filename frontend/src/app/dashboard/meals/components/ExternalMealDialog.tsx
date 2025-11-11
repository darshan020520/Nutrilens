"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Loader2, UtensilsCrossed, AlertCircle, CheckCircle2 } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";

interface ExternalMealDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mealLogId?: number | null; // If provided, will replace this meal
  mealType?: string; // Meal type (breakfast/lunch/dinner)
  onSuccess?: () => void;
}

interface EstimatedNutrition {
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g: number;
  confidence: number;
  reasoning: string;
  estimation_method: string;
}

type Step = "input" | "estimate" | "confirm";

export default function ExternalMealDialog({
  open,
  onOpenChange,
  mealLogId,
  mealType,
  onSuccess,
}: ExternalMealDialogProps) {
  const queryClient = useQueryClient();

  // Step management
  const [currentStep, setCurrentStep] = useState<Step>("input");

  // Form data
  const [dishName, setDishName] = useState("");
  const [portionSize, setPortionSize] = useState("");
  const [restaurantName, setRestaurantName] = useState("");
  const [cuisineType, setCuisineType] = useState("");
  const [notes, setNotes] = useState("");

  // Estimated nutrition
  const [estimatedNutrition, setEstimatedNutrition] = useState<EstimatedNutrition | null>(null);

  // Editable macros (user can adjust after estimate)
  const [calories, setCalories] = useState<number>(0);
  const [proteinG, setProteinG] = useState<number>(0);
  const [carbsG, setCarbsG] = useState<number>(0);
  const [fatG, setFatG] = useState<number>(0);
  const [fiberG, setFiberG] = useState<number>(0);

  // Get nutrition estimate from LLM
  const estimateMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post("/tracking/estimate-external-meal", {
        dish_name: dishName,
        portion_size: portionSize,
        restaurant_name: restaurantName || null,
        cuisine_type: cuisineType || null,
      });
      return response.data;
    },
    onSuccess: (data) => {
      setEstimatedNutrition(data);
      // Set editable values
      setCalories(Math.round(data.calories));
      setProteinG(Math.round(data.protein_g));
      setCarbsG(Math.round(data.carbs_g));
      setFatG(Math.round(data.fat_g));
      setFiberG(Math.round(data.fiber_g));
      setCurrentStep("estimate");
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to estimate nutrition");
    },
  });

  // Log the external meal
  const logMealMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post("/tracking/log-external-meal", {
        dish_name: dishName,
        portion_size: portionSize,
        restaurant_name: restaurantName || null,
        cuisine_type: cuisineType || null,
        calories: calories,
        protein_g: proteinG,
        carbs_g: carbsG,
        fat_g: fatG,
        fiber_g: fiberG,
        meal_log_id_to_replace: mealLogId || null,
        meal_type: mealLogId ? null : mealType,
        notes: notes || null,
      });
      return response.data;
    },
    onSuccess: (data) => {
      // Invalidate queries to refresh data
      queryClient.invalidateQueries({ queryKey: ["tracking", "today"] });
      queryClient.invalidateQueries({ queryKey: ["meal-plan", "current"] });

      // Show success message
      if (data.replaced_meal) {
        toast.success(`Replaced "${data.original_recipe}" with external meal`);
      } else {
        toast.success("External meal logged successfully");
      }

      // Show insights
      if (data.insights && data.insights.length > 0) {
        data.insights.forEach((insight: string) => {
          toast.info(insight);
        });
      }

      // Close dialog and reset
      handleClose();
      onSuccess?.();
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to log external meal");
    },
  });

  const handleEstimate = () => {
    if (!dishName.trim()) {
      toast.error("Please enter a dish name");
      return;
    }
    if (!portionSize.trim()) {
      toast.error("Please enter a portion size");
      return;
    }
    estimateMutation.mutate();
  };

  const handleConfirmAndLog = () => {
    if (calories <= 0) {
      toast.error("Calories must be greater than 0");
      return;
    }
    logMealMutation.mutate();
  };

  const handleClose = () => {
    setCurrentStep("input");
    setDishName("");
    setPortionSize("");
    setRestaurantName("");
    setCuisineType("");
    setNotes("");
    setEstimatedNutrition(null);
    setCalories(0);
    setProteinG(0);
    setCarbsG(0);
    setFatG(0);
    setFiberG(0);
    onOpenChange(false);
  };

  const handleBack = () => {
    if (currentStep === "estimate") {
      setCurrentStep("input");
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <UtensilsCrossed className="h-5 w-5" />
            {mealLogId ? "Replace with External Meal" : "Log External Meal"}
          </DialogTitle>
          <DialogDescription>
            {currentStep === "input" && "Enter details about what you ate"}
            {currentStep === "estimate" && "Review and adjust AI-estimated nutrition"}
            {currentStep === "confirm" && "Confirm and log your meal"}
          </DialogDescription>
        </DialogHeader>

        {/* Step 1: Input Details */}
        {currentStep === "input" && (
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="dish-name">
                Dish Name <span className="text-red-500">*</span>
              </Label>
              <Input
                id="dish-name"
                placeholder="e.g., Chicken Tikka Masala"
                value={dishName}
                onChange={(e) => setDishName(e.target.value)}
                disabled={estimateMutation.isPending}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="portion-size">
                Portion Size <span className="text-red-500">*</span>
              </Label>
              <Input
                id="portion-size"
                placeholder="e.g., 1 large plate, 300g"
                value={portionSize}
                onChange={(e) => setPortionSize(e.target.value)}
                disabled={estimateMutation.isPending}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="restaurant">Restaurant Name (optional)</Label>
              <Input
                id="restaurant"
                placeholder="e.g., Indian Palace"
                value={restaurantName}
                onChange={(e) => setRestaurantName(e.target.value)}
                disabled={estimateMutation.isPending}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="cuisine">Cuisine Type (optional)</Label>
              <Input
                id="cuisine"
                placeholder="e.g., Indian, Italian, Chinese"
                value={cuisineType}
                onChange={(e) => setCuisineType(e.target.value)}
                disabled={estimateMutation.isPending}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="notes">Notes (optional)</Label>
              <Textarea
                id="notes"
                placeholder="Any additional notes..."
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                disabled={estimateMutation.isPending}
              />
            </div>
          </div>
        )}

        {/* Step 2: Review Estimate */}
        {currentStep === "estimate" && estimatedNutrition && (
          <div className="space-y-4 py-4">
            {/* AI Confidence Badge */}
            <Alert>
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                <div className="flex items-center justify-between">
                  <span>AI Estimation Confidence</span>
                  <Badge variant={estimatedNutrition.confidence > 0.7 ? "default" : "secondary"}>
                    {Math.round(estimatedNutrition.confidence * 100)}%
                  </Badge>
                </div>
                <p className="text-xs mt-2 text-muted-foreground">
                  {estimatedNutrition.reasoning}
                </p>
              </AlertDescription>
            </Alert>

            {/* Meal Summary */}
            <div className="bg-muted p-4 rounded-lg space-y-2">
              <h4 className="font-semibold">{dishName}</h4>
              <p className="text-sm text-muted-foreground">{portionSize}</p>
              {restaurantName && (
                <p className="text-sm text-muted-foreground">at {restaurantName}</p>
              )}
            </div>

            {/* Editable Macros */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="font-semibold">Estimated Nutrition</h4>
                <span className="text-xs text-muted-foreground">
                  You can adjust these values
                </span>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="calories">Calories (kcal)</Label>
                  <Input
                    id="calories"
                    type="number"
                    value={calories}
                    onChange={(e) => setCalories(Number(e.target.value))}
                    min={0}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="protein">Protein (g)</Label>
                  <Input
                    id="protein"
                    type="number"
                    value={proteinG}
                    onChange={(e) => setProteinG(Number(e.target.value))}
                    min={0}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="carbs">Carbs (g)</Label>
                  <Input
                    id="carbs"
                    type="number"
                    value={carbsG}
                    onChange={(e) => setCarbsG(Number(e.target.value))}
                    min={0}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="fat">Fat (g)</Label>
                  <Input
                    id="fat"
                    type="number"
                    value={fatG}
                    onChange={(e) => setFatG(Number(e.target.value))}
                    min={0}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="fiber">Fiber (g)</Label>
                  <Input
                    id="fiber"
                    type="number"
                    value={fiberG}
                    onChange={(e) => setFiberG(Number(e.target.value))}
                    min={0}
                  />
                </div>
              </div>

              {/* Visual Macro Display */}
              <div className="grid grid-cols-4 gap-2 mt-4">
                <div className="text-center p-3 bg-accent rounded-lg">
                  <div className="text-2xl font-bold">{calories}</div>
                  <div className="text-xs text-muted-foreground">Calories</div>
                </div>
                <div className="text-center p-3 bg-accent rounded-lg">
                  <div className="text-2xl font-bold">{proteinG}g</div>
                  <div className="text-xs text-muted-foreground">Protein</div>
                </div>
                <div className="text-center p-3 bg-accent rounded-lg">
                  <div className="text-2xl font-bold">{carbsG}g</div>
                  <div className="text-xs text-muted-foreground">Carbs</div>
                </div>
                <div className="text-center p-3 bg-accent rounded-lg">
                  <div className="text-2xl font-bold">{fatG}g</div>
                  <div className="text-xs text-muted-foreground">Fat</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Footer Actions */}
        <DialogFooter>
          {currentStep === "input" && (
            <>
              <Button variant="outline" onClick={handleClose}>
                Cancel
              </Button>
              <Button
                onClick={handleEstimate}
                disabled={estimateMutation.isPending || !dishName.trim() || !portionSize.trim()}
              >
                {estimateMutation.isPending && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Get AI Estimate
              </Button>
            </>
          )}

          {currentStep === "estimate" && (
            <>
              <Button variant="outline" onClick={handleBack}>
                Back
              </Button>
              <Button
                onClick={handleConfirmAndLog}
                disabled={logMealMutation.isPending || calories <= 0}
              >
                {logMealMutation.isPending && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                <CheckCircle2 className="mr-2 h-4 w-4" />
                {mealLogId ? "Replace & Log Meal" : "Log Meal"}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
