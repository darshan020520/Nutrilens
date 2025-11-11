"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { toast } from "sonner";

// Fetch alternative recipes for swapping
export function useRecipeAlternatives(planId: number, recipeId: number | null, count: number = 5) {
  return useQuery({
    queryKey: ["meal-plan", planId, "alternatives", recipeId, count],
    queryFn: async () => {
      if (!recipeId) return null;
      const response = await api.get(`/meal-plans/${planId}/alternatives/${recipeId}?count=${count}`);
      return response.data;
    },
    enabled: !!recipeId && !!planId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

// Swap meal mutation
export function useSwapMeal(planId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      day,
      mealType,
      newRecipeId,
    }: {
      day: number;
      mealType: string;
      newRecipeId: number;
    }) => {
      const response = await api.post(`/meal-plans/${planId}/swap-meal`, {
        day,
        meal_type: mealType,
        new_recipe_id: newRecipeId,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["meal-plan"] });
      toast.success("Meal swapped successfully!");
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to swap meal");
    },
  });
}
