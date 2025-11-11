"use client";

import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Loader2 } from "lucide-react";
import { api } from "@/lib/api";

interface RecipeDetails {
  id: number;
  title: string;
  description?: string;
  servings: number;
  prep_time_min?: number;
  cook_time_min?: number;
  difficulty_level?: string;
  cuisine?: string;
  dietary_tags?: string[];
  suitable_meal_times?: string[];
  goals?: string[];
  macros_per_serving: {
    calories: number;
    protein_g: number;
    carbs_g: number;
    fat_g: number;
  };
  ingredients?: Array<{
    item_name: string;
    quantity_grams: number;
    preparation_notes?: string;
  }>;
  instructions?: string[];
  image_url?: string;
}

interface RecipeDetailsDialogProps {
  recipeId: number | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export default function RecipeDetailsDialog({
  recipeId,
  open,
  onOpenChange,
}: RecipeDetailsDialogProps) {
  const [recipe, setRecipe] = useState<RecipeDetails | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open && recipeId) {
      fetchRecipeDetails();
    }
  }, [open, recipeId]);

  const fetchRecipeDetails = async () => {
    if (!recipeId) return;

    setLoading(true);
    setError(null);
    try {
      const response = await api.get(`/recipes/${recipeId}`);
      setRecipe(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to load recipe details");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
          </div>
        ) : error ? (
          <div className="text-center py-12 text-red-500">{error}</div>
        ) : recipe ? (
          <>
            <DialogHeader>
              <DialogTitle className="text-2xl">{recipe.title}</DialogTitle>
            </DialogHeader>

            <div className="space-y-6">
              {/* Image */}
              {recipe.image_url && (
                <img
                  src={recipe.image_url}
                  alt={recipe.title}
                  className="w-full h-64 object-cover rounded-lg"
                />
              )}

              {/* Tags */}
              <div className="flex flex-wrap gap-2">
                {recipe.suitable_meal_times?.map((time: string) => (
                  <Badge key={time} variant="secondary">
                    {time}
                  </Badge>
                ))}
                {recipe.dietary_tags?.map((tag: string) => (
                  <Badge key={tag} variant="outline">
                    {tag}
                  </Badge>
                ))}
                {recipe.difficulty_level && (
                  <Badge variant="default">{recipe.difficulty_level}</Badge>
                )}
                {recipe.cuisine && (
                  <Badge variant="default">{recipe.cuisine}</Badge>
                )}
              </div>

              {/* Description */}
              {recipe.description && (
                <div>
                  <h3 className="font-semibold mb-2">Description</h3>
                  <p className="text-sm text-muted-foreground">
                    {recipe.description}
                  </p>
                </div>
              )}

              {/* Time & Servings */}
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="font-semibold">Servings:</span> {recipe.servings}
                </div>
                {recipe.prep_time_min && (
                  <div>
                    <span className="font-semibold">Prep Time:</span>{" "}
                    {recipe.prep_time_min} min
                  </div>
                )}
                {recipe.cook_time_min && (
                  <div>
                    <span className="font-semibold">Cook Time:</span>{" "}
                    {recipe.cook_time_min} min
                  </div>
                )}
              </div>

              {/* Macros */}
              <div>
                <h3 className="font-semibold mb-2">Nutrition (per serving)</h3>
                <div className="grid grid-cols-4 gap-4 text-sm">
                  <div className="text-center p-3 bg-accent rounded-lg">
                    <div className="text-2xl font-bold">
                      {Math.round(recipe.macros_per_serving.calories)}
                    </div>
                    <div className="text-xs text-muted-foreground">Calories</div>
                  </div>
                  <div className="text-center p-3 bg-accent rounded-lg">
                    <div className="text-2xl font-bold">
                      {Math.round(recipe.macros_per_serving.protein_g)}g
                    </div>
                    <div className="text-xs text-muted-foreground">Protein</div>
                  </div>
                  <div className="text-center p-3 bg-accent rounded-lg">
                    <div className="text-2xl font-bold">
                      {Math.round(recipe.macros_per_serving.carbs_g)}g
                    </div>
                    <div className="text-xs text-muted-foreground">Carbs</div>
                  </div>
                  <div className="text-center p-3 bg-accent rounded-lg">
                    <div className="text-2xl font-bold">
                      {Math.round(recipe.macros_per_serving.fat_g)}g
                    </div>
                    <div className="text-xs text-muted-foreground">Fat</div>
                  </div>
                </div>
              </div>

              {/* Ingredients */}
              {recipe.ingredients && recipe.ingredients.length > 0 && (
                <div>
                  <h3 className="font-semibold mb-2">Ingredients</h3>
                  <ul className="space-y-2">
                    {recipe.ingredients.map((ing, idx) => (
                      <li key={idx} className="text-sm flex justify-between">
                        <span>{ing.item_name}</span>
                        <span className="text-muted-foreground">
                          {Math.round(ing.quantity_grams)}g
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Instructions */}
              {recipe.instructions && recipe.instructions.length > 0 && (
                <div>
                  <h3 className="font-semibold mb-2">Instructions</h3>
                  <ol className="space-y-3 list-decimal list-inside">
                    {recipe.instructions.map((step: string, idx: number) => (
                      <li key={idx} className="text-sm">
                        {step}
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </div>
          </>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
