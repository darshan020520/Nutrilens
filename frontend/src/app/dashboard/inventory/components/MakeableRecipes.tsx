"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ChefHat,
  Clock,
  Users,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { useMakeableRecipes } from "../hooks/useInventory";

export default function MakeableRecipes() {
  const { data, isLoading, error } = useMakeableRecipes(20);

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <Card key={i}>
            <CardHeader>
              <Skeleton className="h-6 w-48" />
              <Skeleton className="h-4 w-32 mt-2" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-4 w-full mb-2" />
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
        <AlertDescription>
          Failed to load recipes. Please try again.
        </AlertDescription>
      </Alert>
    );
  }

  if (!data) return null;

  const { fully_makeable, partially_makeable, count } = data;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold">Recipes You Can Make</h2>
        <p className="text-sm text-muted-foreground">
          Based on your current inventory
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card className="border-green-200 bg-green-50/50">
          <CardContent className="p-4 text-center">
            <div className="flex items-center justify-center gap-2 mb-1">
              <CheckCircle2 className="h-4 w-4 text-green-600" />
              <span className="text-2xl font-bold text-green-700">
                {fully_makeable?.length || 0}
              </span>
            </div>
            <p className="text-xs text-green-700">Fully Makeable</p>
          </CardContent>
        </Card>

        <Card className="border-yellow-200 bg-yellow-50/50">
          <CardContent className="p-4 text-center">
            <div className="flex items-center justify-center gap-2 mb-1">
              <TrendingUp className="h-4 w-4 text-yellow-600" />
              <span className="text-2xl font-bold text-yellow-700">
                {partially_makeable?.length || 0}
              </span>
            </div>
            <p className="text-xs text-yellow-700">Partially Makeable</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 text-center">
            <div className="flex items-center justify-center gap-2 mb-1">
              <ChefHat className="h-4 w-4 text-muted-foreground" />
              <span className="text-2xl font-bold">{count}</span>
            </div>
            <p className="text-xs text-muted-foreground">Total Recipes</p>
          </CardContent>
        </Card>
      </div>

      {/* Empty State */}
      {count === 0 && (
        <Card>
          <CardContent className="py-12 text-center">
            <ChefHat className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
            <p className="text-lg font-medium mb-1">No Recipes Available Yet</p>
            <p className="text-sm text-muted-foreground">
              Add more items to your inventory to see recipe suggestions
            </p>
          </CardContent>
        </Card>
      )}

      {/* Fully Makeable Recipes */}
      {fully_makeable && fully_makeable.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-green-600" />
            <h3 className="text-lg font-semibold">Fully Makeable Recipes</h3>
            <Badge variant="secondary">{fully_makeable.length}</Badge>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            {fully_makeable.map((recipe) => (
              <Card key={recipe.recipe_id} className="border-green-200">
                <CardHeader>
                  <CardTitle className="text-base flex items-start justify-between gap-2">
                    <span>{recipe.recipe_name}</span>
                    <Badge variant="secondary" className="text-xs">
                      100%
                    </Badge>
                  </CardTitle>
                  {recipe.description && (
                    <p className="text-sm text-muted-foreground line-clamp-2">
                      {recipe.description}
                    </p>
                  )}
                </CardHeader>
                <CardContent className="space-y-3">
                  {/* Recipe Metadata */}
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

                  {/* Ingredient Match */}
                  <div>
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="text-muted-foreground">
                        All ingredients available
                      </span>
                      <span className="font-medium text-green-600">
                        {recipe.available_ingredients}/{recipe.total_ingredients}
                      </span>
                    </div>
                    <Progress value={100} className="h-2" />
                  </div>

                  {/* Available Ingredients */}
                  {recipe.available_ingredient_names &&
                    recipe.available_ingredient_names.length > 0 && (
                      <div>
                        <p className="text-xs text-muted-foreground mb-1">
                          You have:
                        </p>
                        <div className="flex flex-wrap gap-1">
                          {recipe.available_ingredient_names
                            .slice(0, 5)
                            .map((ingredient, idx) => (
                              <Badge
                                key={idx}
                                variant="outline"
                                className="text-xs"
                              >
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
                    <ChefHat className="mr-2 h-4 w-4" />
                    View Recipe
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Partially Makeable Recipes */}
      {partially_makeable && partially_makeable.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-yellow-600" />
            <h3 className="text-lg font-semibold">Partially Makeable Recipes</h3>
            <Badge variant="secondary">{partially_makeable.length}</Badge>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            {partially_makeable.map((recipe) => (
              <Card key={recipe.recipe_id} className="border-yellow-200">
                <CardHeader>
                  <CardTitle className="text-base flex items-start justify-between gap-2">
                    <span>{recipe.recipe_name}</span>
                    <Badge variant="outline" className="text-xs">
                      {recipe.match_percentage
                        ? `${Math.round(recipe.match_percentage)}%`
                        : "Partial"}
                    </Badge>
                  </CardTitle>
                  {recipe.description && (
                    <p className="text-sm text-muted-foreground line-clamp-2">
                      {recipe.description}
                    </p>
                  )}
                </CardHeader>
                <CardContent className="space-y-3">
                  {/* Recipe Metadata */}
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

                  {/* Ingredient Match */}
                  <div>
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="text-muted-foreground">Ingredients match</span>
                      <span className="font-medium">
                        {recipe.available_ingredients}/{recipe.total_ingredients}
                      </span>
                    </div>
                    <Progress
                      value={recipe.match_percentage || 0}
                      className="h-2"
                    />
                  </div>

                  {/* Available Ingredients */}
                  {recipe.available_ingredient_names &&
                    recipe.available_ingredient_names.length > 0 && (
                      <div>
                        <p className="text-xs text-muted-foreground mb-1 flex items-center gap-1">
                          <CheckCircle2 className="h-3 w-3 text-green-600" />
                          You have:
                        </p>
                        <div className="flex flex-wrap gap-1">
                          {recipe.available_ingredient_names
                            .slice(0, 3)
                            .map((ingredient, idx) => (
                              <Badge
                                key={idx}
                                variant="outline"
                                className="text-xs"
                              >
                                {ingredient}
                              </Badge>
                            ))}
                        </div>
                      </div>
                    )}

                  {/* Missing Ingredients */}
                  {recipe.missing_ingredient_names &&
                    recipe.missing_ingredient_names.length > 0 && (
                      <div>
                        <p className="text-xs text-muted-foreground mb-1 flex items-center gap-1">
                          <XCircle className="h-3 w-3 text-red-600" />
                          You need:
                        </p>
                        <div className="flex flex-wrap gap-1">
                          {recipe.missing_ingredient_names
                            .slice(0, 3)
                            .map((ingredient, idx) => (
                              <Badge
                                key={idx}
                                variant="outline"
                                className="text-xs text-red-600 border-red-200"
                              >
                                {ingredient}
                              </Badge>
                            ))}
                          {recipe.missing_ingredient_names.length > 3 && (
                            <Badge
                              variant="outline"
                              className="text-xs text-red-600 border-red-200"
                            >
                              +{recipe.missing_ingredient_names.length - 3} more
                            </Badge>
                          )}
                        </div>
                      </div>
                    )}

                  <Button className="w-full" variant="outline" size="sm">
                    <ChefHat className="mr-2 h-4 w-4" />
                    View Recipe
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
