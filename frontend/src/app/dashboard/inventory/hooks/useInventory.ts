"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { toast } from "sonner";
import {
  InventoryStatus,
  InventoryItem,
  AddItemsResult,
  FilterOptions,
} from "../types";

// Fetch inventory status with AI insights
export function useInventoryStatus() {
  return useQuery<InventoryStatus>({
    queryKey: ["inventory", "status"],
    queryFn: async () => {
      const response = await api.get("/inventory/status");
      return response.data;
    },
    staleTime: 2 * 60 * 1000, // 2 minutes
    refetchInterval: 5 * 60 * 1000, // Refetch every 5 minutes
  });
}

// Fetch inventory items with filters
export function useInventoryItems(filters: FilterOptions) {
  return useQuery<{ count: number; items: InventoryItem[] }>({
    queryKey: ["inventory", "items", filters],
    queryFn: async () => {
      const params = new URLSearchParams();

      if (filters.category) {
        params.append("category", filters.category);
      }
      if (filters.lowStockOnly) {
        params.append("low_stock_only", "true");
      }
      if (filters.expiringSoon) {
        params.append("expiring_soon", "true");
      }

      const response = await api.get(`/inventory/items?${params.toString()}`);
      return response.data;
    },
    staleTime: 1 * 60 * 1000, // 1 minute
  });
}

// Add items from text input
export function useAddItems() {
  const queryClient = useQueryClient();

  return useMutation<AddItemsResult, Error, { text_input: string }>({
    mutationFn: async (data) => {
      const response = await api.post("/inventory/add-items", data);
      return response.data;
    },
    onSuccess: (data) => {
      const successCount = data.results.summary.successful;
      const confirmCount = data.results.summary.needs_confirmation;

      if (successCount > 0) {
        toast.success(`${successCount} item${successCount > 1 ? 's' : ''} added successfully!`);
      }

      if (confirmCount > 0) {
        toast.info(`${confirmCount} item${confirmCount > 1 ? 's need' : ' needs'} confirmation`);
      }

      // Invalidate queries to refetch data
      queryClient.invalidateQueries({ queryKey: ["inventory"] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to add items");
    },
  });
}

// Confirm a medium-confidence item
export function useConfirmItem() {
  const queryClient = useQueryClient();

  return useMutation<
    any,
    Error,
    { original_text: string; item_id: number; quantity_grams: number }
  >({
    mutationFn: async (data) => {
      const response = await api.post("/inventory/confirm-item", data);
      return response.data;
    },
    onSuccess: (data) => {
      toast.success(`${data.item} added to inventory`);
      queryClient.invalidateQueries({ queryKey: ["inventory"] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to confirm item");
    },
  });
}

// Delete inventory item
export function useDeleteItem() {
  const queryClient = useQueryClient();

  return useMutation<any, Error, number>({
    mutationFn: async (inventoryId) => {
      const response = await api.delete(`/inventory/item/${inventoryId}`);
      return response.data;
    },
    onSuccess: () => {
      toast.success("Item removed from inventory");
      queryClient.invalidateQueries({ queryKey: ["inventory"] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to delete item");
    },
  });
}

// Get recipes that can be made with current inventory
export function useMakeableRecipes(limit: number = 10) {
  return useQuery({
    queryKey: ["inventory", "makeable-recipes", limit],
    queryFn: async () => {
      const response = await api.get(`/inventory/makeable-recipes?limit=${limit}`);
      return response.data;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}
