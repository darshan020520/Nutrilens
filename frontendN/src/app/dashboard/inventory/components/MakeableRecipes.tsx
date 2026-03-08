"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { motion as motionTokens } from "@/design/motion";
import {
  ChefHat,
  Clock,
  Users,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Loader2,
  Flame,
  Dumbbell,
  WandSparkles,
  ArrowRight,
} from "lucide-react";
import { useMakeableRecipes, useAIRecipes } from "../hooks/useInventory";
import { AIRecipeSuggestion } from "../types";

type MakeableRecipeItem = {
  recipe_id: number;
  recipe_name: string;
  description?: string | null;
  prep_time_minutes?: number | null;
  servings?: number | null;
  available_ingredients: number;
  total_ingredients: number;
  available_ingredient_names?: string[] | null;
  missing_ingredient_names?: string[] | null;
  match_percentage?: number | null;
};

type MakeableResponse = {
  fully_makeable: MakeableRecipeItem[];
  partially_makeable: MakeableRecipeItem[];
  count: number;
};

const aiPhases = [
  "Mapping pantry inventory to flavor vectors",
  "Applying goal and macro-aware constraints",
  "Synthesizing creative, cookable suggestions",
];

export default function MakeableRecipes() {
  const { data, isLoading, error } = useMakeableRecipes(20);
  const aiRecipesMutation = useAIRecipes();
  const [aiMode, setAiMode] = useState<"goal_adherent" | "guilt_free">("goal_adherent");
  const [aiRecipes, setAiRecipes] = useState<AIRecipeSuggestion[]>([]);
  const [generationPhase, setGenerationPhase] = useState(0);

  useEffect(() => {
    if (!aiRecipesMutation.isPending) return;
    const interval = window.setInterval(() => {
      setGenerationPhase((prev) => (prev + 1) % aiPhases.length);
    }, 850);
    return () => window.clearInterval(interval);
  }, [aiRecipesMutation.isPending]);

  const handleGenerateAI = (mode: "goal_adherent" | "guilt_free") => {
    setAiMode(mode);
    setGenerationPhase(0);
    aiRecipesMutation.mutate(
      { mode },
      {
        onSuccess: (payload) => {
          setAiRecipes(payload.recipes || []);
        },
      }
    );
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <Card key={i}>
            <CardHeader>
              <Skeleton className="h-6 w-48" />
              <Skeleton className="mt-2 h-4 w-32" />
            </CardHeader>
            <CardContent>
              <Skeleton className="mb-2 h-4 w-full" />
              <Skeleton className="h-4 w-3/4" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription>Failed to load recipes. Please try again.</AlertDescription>
      </Alert>
    );
  }

  if (!data) return null;

  const typedData = data as MakeableResponse;
  const fullyMakeable = typedData.fully_makeable || [];
  const partiallyMakeable = typedData.partially_makeable || [];
  const count = typedData.count || 0;

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-cyan-200 bg-[linear-gradient(145deg,rgba(20,184,166,0.10),rgba(14,165,233,0.08))] px-5 py-4">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-600">Cookable Intelligence</p>
        <h2 className="text-xl font-semibold text-slate-900">Recipes optimized by your current inventory</h2>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card className="border-green-200 bg-green-50/60">
          <CardContent className="p-4 text-center">
            <div className="mb-1 flex items-center justify-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-green-600" />
              <span className="text-2xl font-bold text-green-700">{fullyMakeable.length}</span>
            </div>
            <p className="text-xs text-green-700">Fully Makeable</p>
          </CardContent>
        </Card>

        <Card className="border-yellow-200 bg-yellow-50/60">
          <CardContent className="p-4 text-center">
            <div className="mb-1 flex items-center justify-center gap-2">
              <TrendingUp className="h-4 w-4 text-yellow-600" />
              <span className="text-2xl font-bold text-yellow-700">{partiallyMakeable.length}</span>
            </div>
            <p className="text-xs text-yellow-700">Partially Makeable</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 text-center">
            <div className="mb-1 flex items-center justify-center gap-2">
              <ChefHat className="h-4 w-4 text-muted-foreground" />
              <span className="text-2xl font-bold">{count}</span>
            </div>
            <p className="text-xs text-muted-foreground">Total Candidate Recipes</p>
          </CardContent>
        </Card>
      </div>

      {count === 0 && (
        <Card>
          <CardContent className="py-12 text-center">
            <ChefHat className="mx-auto mb-3 h-12 w-12 text-muted-foreground" />
            <p className="mb-1 text-lg font-medium">No recipes available yet</p>
            <p className="text-sm text-muted-foreground">Add more inventory items to unlock recipe matching.</p>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-5 xl:grid-cols-[1.25fr_0.75fr]">
        <section className="space-y-5">
          {fullyMakeable.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-green-600" />
                <h3 className="text-lg font-semibold">Ready to cook now</h3>
                <Badge variant="secondary">{fullyMakeable.length}</Badge>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                {fullyMakeable.map((recipe: MakeableRecipeItem) => (
                  <Card key={recipe.recipe_id} className="border-green-200">
                    <CardHeader>
                      <CardTitle className="flex items-start justify-between gap-2 text-base">
                        <span>{recipe.recipe_name}</span>
                        <Badge variant="secondary" className="text-xs">
                          100%
                        </Badge>
                      </CardTitle>
                      {recipe.description && (
                        <p className="line-clamp-2 text-sm text-muted-foreground">{recipe.description}</p>
                      )}
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div className="flex items-center gap-4 text-xs text-muted-foreground">
                        {recipe.prep_time_minutes && (
                          <div className="flex items-center gap-1">
                            <Clock className="h-3.5 w-3.5" />
                            <span>{recipe.prep_time_minutes} min</span>
                          </div>
                        )}
                        {recipe.servings && (
                          <div className="flex items-center gap-1">
                            <Users className="h-3.5 w-3.5" />
                            <span>{recipe.servings} servings</span>
                          </div>
                        )}
                      </div>

                      <div>
                        <div className="mb-1 flex items-center justify-between text-xs">
                          <span className="text-muted-foreground">All ingredients available</span>
                          <span className="font-medium text-green-600">
                            {recipe.available_ingredients}/{recipe.total_ingredients}
                          </span>
                        </div>
                        <Progress value={100} className="h-2" />
                      </div>

                      {recipe.available_ingredient_names && recipe.available_ingredient_names.length > 0 && (
                        <div>
                          <p className="mb-1 text-xs text-muted-foreground">You already have</p>
                          <div className="flex flex-wrap gap-1">
                            {recipe.available_ingredient_names.slice(0, 5).map((ingredient: string) => (
                              <Badge key={`${recipe.recipe_id}-${ingredient}`} variant="outline" className="text-xs">
                                {ingredient}
                              </Badge>
                            ))}
                            {recipe.available_ingredient_names.length > 5 && (
                              <Badge variant="outline" className="text-xs">
                                +{recipe.available_ingredient_names.length - 5} more
                              </Badge>
                            )}
                          </div>
                        </div>
                      )}

                      <Button className="w-full" size="sm">
                        View Recipe
                      </Button>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {partiallyMakeable.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-yellow-600" />
                <h3 className="text-lg font-semibold">Almost ready</h3>
                <Badge variant="secondary">{partiallyMakeable.length}</Badge>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                {partiallyMakeable.map((recipe: MakeableRecipeItem) => (
                  <Card key={recipe.recipe_id} className="border-yellow-200">
                    <CardHeader>
                      <CardTitle className="flex items-start justify-between gap-2 text-base">
                        <span>{recipe.recipe_name}</span>
                        <Badge variant="outline" className="text-xs">
                          {recipe.match_percentage ? `${Math.round(recipe.match_percentage)}%` : "Partial"}
                        </Badge>
                      </CardTitle>
                      {recipe.description && (
                        <p className="line-clamp-2 text-sm text-muted-foreground">{recipe.description}</p>
                      )}
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div className="flex items-center gap-4 text-xs text-muted-foreground">
                        {recipe.prep_time_minutes && (
                          <div className="flex items-center gap-1">
                            <Clock className="h-3.5 w-3.5" />
                            <span>{recipe.prep_time_minutes} min</span>
                          </div>
                        )}
                        {recipe.servings && (
                          <div className="flex items-center gap-1">
                            <Users className="h-3.5 w-3.5" />
                            <span>{recipe.servings} servings</span>
                          </div>
                        )}
                      </div>

                      <div>
                        <div className="mb-1 flex items-center justify-between text-xs">
                          <span className="text-muted-foreground">Ingredients match</span>
                          <span className="font-medium">
                            {recipe.available_ingredients}/{recipe.total_ingredients}
                          </span>
                        </div>
                        <Progress value={recipe.match_percentage || 0} className="h-2" />
                      </div>

                      {recipe.missing_ingredient_names && recipe.missing_ingredient_names.length > 0 && (
                        <div>
                          <p className="mb-1 flex items-center gap-1 text-xs text-muted-foreground">
                            <XCircle className="h-3 w-3 text-red-600" />
                            Missing ingredients
                          </p>
                          <div className="flex flex-wrap gap-1">
                            {recipe.missing_ingredient_names.slice(0, 4).map((ingredient: string) => (
                              <Badge
                                key={`${recipe.recipe_id}-missing-${ingredient}`}
                                variant="outline"
                                className="border-red-200 text-xs text-red-600"
                              >
                                {ingredient}
                              </Badge>
                            ))}
                            {recipe.missing_ingredient_names.length > 4 && (
                              <Badge variant="outline" className="border-red-200 text-xs text-red-600">
                                +{recipe.missing_ingredient_names.length - 4} more
                              </Badge>
                            )}
                          </div>
                        </div>
                      )}

                      <Button className="w-full" size="sm" variant="outline">
                        View Recipe
                      </Button>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          )}
        </section>

        <aside className="space-y-4">
          <Card className="border-cyan-200 bg-[linear-gradient(145deg,rgba(14,165,233,0.08),rgba(45,212,191,0.08))] xl:sticky xl:top-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <WandSparkles className="h-5 w-5 text-cyan-600" />
                AI Creative Recipe Studio
              </CardTitle>
              <p className="text-sm text-muted-foreground">
                Generate personalized recipes instantly from what you already have.
              </p>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex gap-2">
                <Button
                  size="sm"
                  className="flex-1"
                  variant={aiMode === "goal_adherent" ? "default" : "outline"}
                  onClick={() => handleGenerateAI("goal_adherent")}
                  disabled={aiRecipesMutation.isPending}
                >
                  {aiRecipesMutation.isPending && aiMode === "goal_adherent" ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Dumbbell className="mr-2 h-4 w-4" />
                  )}
                  Goal-aligned
                </Button>
                <Button
                  size="sm"
                  className="flex-1"
                  variant={aiMode === "guilt_free" ? "default" : "outline"}
                  onClick={() => handleGenerateAI("guilt_free")}
                  disabled={aiRecipesMutation.isPending}
                >
                  {aiRecipesMutation.isPending && aiMode === "guilt_free" ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Flame className="mr-2 h-4 w-4" />
                  )}
                  Guilt-free
                </Button>
              </div>

              <AnimatePresence>
                {aiRecipesMutation.isPending && (
                  <motion.div
                    className="space-y-2 rounded-xl border border-cyan-200 bg-white/80 p-3"
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: motionTokens.base, ease: motionTokens.easing }}
                  >
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-cyan-700">AI Engine</p>
                    <p className="text-sm text-slate-700">{aiPhases[generationPhase]}</p>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-cyan-100">
                      <motion.div
                        className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-teal-500"
                        initial={{ width: "18%" }}
                        animate={{ width: "100%" }}
                        transition={{ duration: 1.3, ease: "easeInOut" }}
                      />
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {aiRecipesMutation.isError && (
                <Alert variant="destructive">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>Failed to generate AI recipes. Please try again.</AlertDescription>
                </Alert>
              )}
            </CardContent>
          </Card>

          {aiRecipes.length > 0 && (
            <div className="space-y-3">
              {aiRecipes.map((recipe, idx) => (
                <Card key={`${recipe.name}-${idx}`} className="border-cyan-200">
                  <CardHeader>
                    <CardTitle className="flex items-start justify-between gap-2 text-base">
                      <span>{recipe.name}</span>
                      <Badge variant="outline" className="text-xs capitalize">
                        {recipe.difficulty}
                      </Badge>
                    </CardTitle>
                    <p className="line-clamp-2 text-sm text-muted-foreground">{recipe.description}</p>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Clock className="h-3.5 w-3.5" />
                        {recipe.estimated_prep_time_min} min
                      </span>
                      <Badge variant="secondary" className="text-[10px] uppercase tracking-wide">
                        {recipe.cuisine || "general"}
                      </Badge>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-2">
                        <p className="text-[10px] uppercase tracking-[0.08em] text-slate-500">Calories</p>
                        <p className="font-semibold text-slate-900">{recipe.estimated_calories}</p>
                      </div>
                      <div className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-2">
                        <p className="text-[10px] uppercase tracking-[0.08em] text-slate-500">Protein</p>
                        <p className="font-semibold text-slate-900">{recipe.estimated_protein_g}g</p>
                      </div>
                      <div className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-2">
                        <p className="text-[10px] uppercase tracking-[0.08em] text-slate-500">Carbs</p>
                        <p className="font-semibold text-slate-900">{recipe.estimated_carbs_g}g</p>
                      </div>
                      <div className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-2">
                        <p className="text-[10px] uppercase tracking-[0.08em] text-slate-500">Fat</p>
                        <p className="font-semibold text-slate-900">{recipe.estimated_fat_g}g</p>
                      </div>
                    </div>

                    {(recipe.suitable_meal_times?.length || recipe.goals?.length || recipe.dietary_tags?.length) ? (
                      <div className="space-y-2">
                        <div className="flex flex-wrap gap-1">
                          {(recipe.suitable_meal_times ?? []).map((mealTime, mealTimeIndex) => (
                            <Badge
                              key={`${recipe.name}-meal-${mealTime}-${mealTimeIndex}`}
                              variant="secondary"
                              className="text-[10px] capitalize"
                            >
                              {mealTime}
                            </Badge>
                          ))}
                          {(recipe.goals ?? []).map((goal, goalIndex) => (
                            <Badge
                              key={`${recipe.name}-goal-${goal}-${goalIndex}`}
                              variant="outline"
                              className="text-[10px] capitalize"
                            >
                              {goal.replaceAll("_", " ")}
                            </Badge>
                          ))}
                          {(recipe.dietary_tags ?? []).map((tag, tagIndex) => (
                            <Badge
                              key={`${recipe.name}-tag-${tag}-${tagIndex}`}
                              variant="outline"
                              className="text-[10px] capitalize"
                            >
                              {tag.replaceAll("_", " ")}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    ) : null}

                    <div>
                      <p className="mb-1 text-xs font-medium text-slate-700">Ingredients from your pantry</p>
                      <div className="flex flex-wrap gap-1">
                        {(recipe.ingredients ?? []).slice(0, 6).map((ingredient, index) => (
                          <Badge
                            key={`${recipe.name}-${ingredient.name}-${ingredient.quantity_grams}-${index}`}
                            variant="outline"
                            className="text-xs"
                          >
                            {ingredient.name} ({Math.round(ingredient.quantity_grams)}g)
                          </Badge>
                        ))}
                        {(recipe.ingredients ?? []).length > 6 && (
                          <Badge variant="outline" className="text-xs">
                            +{(recipe.ingredients ?? []).length - 6} more
                          </Badge>
                        )}
                      </div>
                    </div>

                    {(recipe.instructions ?? []).length > 0 && (
                      <div className="space-y-1.5">
                        <p className="text-xs font-medium text-slate-700">Recipe guidelines</p>
                        {(recipe.instructions ?? []).slice(0, 3).map((step, stepIndex) => (
                          <div
                            key={`${recipe.name}-step-${stepIndex}`}
                            className="flex gap-2 rounded-md border border-slate-200 bg-slate-50 px-2.5 py-2 text-xs text-slate-700"
                          >
                            <span className="font-semibold text-slate-500">{stepIndex + 1}.</span>
                            <span>{step}</span>
                          </div>
                        ))}
                        {(recipe.instructions ?? []).length > 3 && (
                          <p className="text-[11px] text-muted-foreground">
                            +{(recipe.instructions ?? []).length - 3} more steps
                          </p>
                        )}
                      </div>
                    )}

                    <Button
                      variant="outline"
                      size="sm"
                      className="w-full border-cyan-300 bg-cyan-50/50 text-cyan-800 hover:bg-cyan-100"
                    >
                      Use this recipe
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Button>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
