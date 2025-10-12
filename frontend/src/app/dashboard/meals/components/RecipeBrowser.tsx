// frontend/src/app/dashboard/meals/components/RecipeBrowser.tsx
"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Search, Clock, Utensils, ChevronLeft, ChevronRight } from "lucide-react";
import { api } from "@/lib/api";

interface Recipe {
  id: number;
  title: string;
  description?: string;
  cuisine?: string;
  prep_time_min?: number;
  cook_time_min?: number;
  difficulty_level?: string;
  goals?: string[];
  dietary_tags?: string[];
  suitable_meal_times?: string[];
  macros_per_serving: {
    calories: number;
    protein_g: number;
    carbs_g: number;
    fat_g: number;
  };
  servings: number;
  instructions?: string[];
  ingredients?: Array<{
    item_name: string;
    quantity_grams: number;
    preparation_notes?: string;
  }>;
}

interface RecipeFilters {
  search: string;
  goal: string;
  cuisine: string;
  dietary_type: string;
  meal_time: string;
  max_prep_time: string;
}

export function RecipeBrowser() {
  const [filters, setFilters] = useState<RecipeFilters>({
    search: "",
    goal: "",
    cuisine: "",
    dietary_type: "",
    meal_time: "",
    max_prep_time: "",
  });
  const [page, setPage] = useState(0);
  const [selectedRecipe, setSelectedRecipe] = useState<Recipe | null>(null);
  const pageSize = 20;

  // Fetch recipes
  const { data: recipes, isLoading, error } = useQuery({
    queryKey: ["recipes", filters, page],
    queryFn: async () => {
      const params: any = {
        limit: pageSize,
        offset: page * pageSize,
      };

      if (filters.search) params.search = filters.search;
      if (filters.goal) params.goal = filters.goal;
      if (filters.cuisine) params.cuisine = filters.cuisine;
      if (filters.dietary_type) params.dietary_type = filters.dietary_type;
      if (filters.meal_time) params.meal_time = filters.meal_time;
      if (filters.max_prep_time) params.max_prep_time = parseInt(filters.max_prep_time);

      const response = await api.get("/recipes/", { params });
      return response.data;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  // Fetch recipe details
  const { data: recipeDetails } = useQuery({
    queryKey: ["recipe", selectedRecipe?.id],
    queryFn: async () => {
      if (!selectedRecipe?.id) return null;
      const response = await api.get(`/recipes/${selectedRecipe.id}`);
      return response.data;
    },
    enabled: !!selectedRecipe?.id,
  });

  const handleFilterChange = (key: keyof RecipeFilters, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(0); // Reset to first page
  };

  const handleSearch = () => {
    setPage(0);
  };

  const totalRecipes = recipes?.length || 0;
  const hasMore = totalRecipes === pageSize;

  if (isLoading && !recipes) {
    return (
      <div className="space-y-6">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-40 w-full" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-6 w-3/4 mb-2" />
                <Skeleton className="h-4 w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>
          Failed to load recipes. Please try again.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      {/* Filters Section */}
      <Card>
        <CardHeader>
          <div className="space-y-4">
            {/* Search Bar */}
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search recipes..."
                  value={filters.search}
                  onChange={(e) => handleFilterChange("search", e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                  className="pl-9"
                />
              </div>
              <Button onClick={handleSearch}>Search</Button>
            </div>

            {/* Filter Dropdowns */}
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
              <Select
                value={filters.goal}
                onValueChange={(value) => handleFilterChange("goal", value)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Goal" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Goals</SelectItem>
                  <SelectItem value="weight_loss">Weight Loss</SelectItem>
                  <SelectItem value="muscle_gain">Muscle Gain</SelectItem>
                  <SelectItem value="body_recomp">Body Recomp</SelectItem>
                  <SelectItem value="general_health">General Health</SelectItem>
                </SelectContent>
              </Select>

              <Select
                value={filters.cuisine}
                onValueChange={(value) => handleFilterChange("cuisine", value)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Cuisine" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Cuisines</SelectItem>
                  <SelectItem value="indian">Indian</SelectItem>
                  <SelectItem value="italian">Italian</SelectItem>
                  <SelectItem value="mexican">Mexican</SelectItem>
                  <SelectItem value="asian">Asian</SelectItem>
                  <SelectItem value="mediterranean">Mediterranean</SelectItem>
                </SelectContent>
              </Select>

              <Select
                value={filters.dietary_type}
                onValueChange={(value) => handleFilterChange("dietary_type", value)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Dietary" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  <SelectItem value="vegetarian">Vegetarian</SelectItem>
                  <SelectItem value="vegan">Vegan</SelectItem>
                  <SelectItem value="non_vegetarian">Non-Vegetarian</SelectItem>
                </SelectContent>
              </Select>

              <Select
                value={filters.meal_time}
                onValueChange={(value) => handleFilterChange("meal_time", value)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Meal Time" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Meals</SelectItem>
                  <SelectItem value="breakfast">Breakfast</SelectItem>
                  <SelectItem value="lunch">Lunch</SelectItem>
                  <SelectItem value="dinner">Dinner</SelectItem>
                  <SelectItem value="snack">Snack</SelectItem>
                </SelectContent>
              </Select>

              <Select
                value={filters.max_prep_time}
                onValueChange={(value) => handleFilterChange("max_prep_time", value)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Prep Time" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Any Time</SelectItem>
                  <SelectItem value="15">Under 15 min</SelectItem>
                  <SelectItem value="30">Under 30 min</SelectItem>
                  <SelectItem value="45">Under 45 min</SelectItem>
                  <SelectItem value="60">Under 1 hour</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Results Count */}
      <div className="text-sm text-muted-foreground">
        {isLoading ? (
          "Loading..."
        ) : (
          `Showing ${page * pageSize + 1}-${page * pageSize + totalRecipes} recipes`
        )}
      </div>

      {/* Recipe Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {recipes?.map((recipe: Recipe) => (
          <Card
            key={recipe.id}
            className="cursor-pointer hover:shadow-lg transition-shadow"
            onClick={() => setSelectedRecipe(recipe)}
          >
            {/* Placeholder Image */}
            <div className="aspect-video bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center">
              <Utensils className="h-12 w-12 text-primary/40" />
            </div>

            <CardHeader className="pb-3">
              <h3 className="font-semibold line-clamp-2">{recipe.title}</h3>
              {recipe.description && (
                <p className="text-sm text-muted-foreground line-clamp-2">
                  {recipe.description}
                </p>
              )}
            </CardHeader>

            <CardContent className="space-y-3">
              {/* Macros */}
              <div className="grid grid-cols-4 gap-2 text-xs">
                <div>
                  <div className="text-muted-foreground">Cal</div>
                  <div className="font-medium">
                    {Math.round(recipe.macros_per_serving?.calories ?? 0)}g
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground">P</div>
                  <div className="font-medium">
                    {Math.round(recipe.macros_per_serving?.protein_g ?? 0)}g
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground">C</div>
                  <div className="font-medium">
                    {Math.round(recipe.macros_per_serving?.carbs_g ?? 0)}g
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground">F</div>
                  <div className="font-medium">
                    {Math.round(recipe.macros_per_serving?.fat_g ?? 0)}g
                  </div>
                </div>
              </div>

              {/* Tags */}
              <div className="flex flex-wrap gap-1">
                {recipe.prep_time_min && (
                  <Badge variant="secondary" className="text-xs">
                    <Clock className="mr-1 h-3 w-3" />
                    {recipe.prep_time_min}m
                  </Badge>
                )}
                {recipe.cuisine && (
                  <Badge variant="outline" className="text-xs">
                    {recipe.cuisine}
                  </Badge>
                )}
              </div>
            </CardContent>

            <CardFooter>
              <Button className="w-full" size="sm" variant="outline">
                View Recipe
              </Button>
            </CardFooter>
          </Card>
        ))}
      </div>

      {/* Pagination */}
      {totalRecipes > 0 && (
        <div className="flex items-center justify-between">
          <Button
            variant="outline"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0 || isLoading}
          >
            <ChevronLeft className="mr-2 h-4 w-4" />
            Previous
          </Button>

          <span className="text-sm text-muted-foreground">Page {page + 1}</span>

          <Button
            variant="outline"
            onClick={() => setPage((p) => p + 1)}
            disabled={!hasMore || isLoading}
          >
            Next
            <ChevronRight className="ml-2 h-4 w-4" />
          </Button>
        </div>
      )}

      {/* Recipe Details Dialog */}
      <Dialog
        open={!!selectedRecipe}
        onOpenChange={() => setSelectedRecipe(null)}
      >
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{selectedRecipe?.title}</DialogTitle>
            <DialogDescription>
              {selectedRecipe?.description}
            </DialogDescription>
          </DialogHeader>

          {recipeDetails && (
            <div className="space-y-6">
              {/* Macros */}
              <div>
                <h4 className="font-semibold mb-3">Nutrition (per serving)</h4>
                <div className="grid grid-cols-4 gap-4">
                  <div className="text-center p-3 bg-accent rounded-lg">
                    <div className="text-2xl font-bold">
                      {Math.round(recipeDetails.macros_per_serving.calories)}
                    </div>
                    <div className="text-xs text-muted-foreground">Calories</div>
                  </div>
                  <div className="text-center p-3 bg-accent rounded-lg">
                    <div className="text-2xl font-bold">
                      {Math.round(recipeDetails.macros_per_serving.protein_g)}g
                    </div>
                    <div className="text-xs text-muted-foreground">Protein</div>
                  </div>
                  <div className="text-center p-3 bg-accent rounded-lg">
                    <div className="text-2xl font-bold">
                      {Math.round(recipeDetails.macros_per_serving.carbs_g)}g
                    </div>
                    <div className="text-xs text-muted-foreground">Carbs</div>
                  </div>
                  <div className="text-center p-3 bg-accent rounded-lg">
                    <div className="text-2xl font-bold">
                      {Math.round(recipeDetails.macros_per_serving.fat_g)}g
                    </div>
                    <div className="text-xs text-muted-foreground">Fat</div>
                  </div>
                </div>
              </div>

              {/* Ingredients */}
              {recipeDetails.ingredients && recipeDetails.ingredients.length > 0 && (
                <div>
                  <h4 className="font-semibold mb-3">Ingredients</h4>
                  <ul className="space-y-2">
                    {recipeDetails.ingredients.map((ing: any, idx: number) => (
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
              {recipeDetails.instructions && recipeDetails.instructions.length > 0 && (
                <div>
                  <h4 className="font-semibold mb-3">Instructions</h4>
                  <ol className="space-y-3 list-decimal list-inside">
                    {recipeDetails.instructions.map((step: string, idx: number) => (
                      <li key={idx} className="text-sm">
                        {step}
                      </li>
                    ))}
                  </ol>
                </div>
              )}

              {/* Action Button */}
              <Button className="w-full" disabled>
                Add to Plan (Coming Soon)
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}