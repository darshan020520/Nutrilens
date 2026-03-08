"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, getEndpoint } from "@/lib/api";
import { toast } from "sonner";
import {
  InventoryStatus,
  InventoryItem,
  AddItemsResult,
  FilterOptions,
  AIRecipeSuggestion,
  BulkAddFromRestockItem,
  BulkAddFromRestockResponse,
} from "../types";

type ApiErrorLike = {
  response?: {
    data?: {
      detail?: string;
    };
  };
};

function getErrorMessage(error: unknown, fallback: string): string {
  const detail = (error as ApiErrorLike)?.response?.data?.detail;
  return typeof detail === "string" ? detail : fallback;
}

// Fetch inventory status with AI insights
export function useInventoryStatus() {
  return useQuery<InventoryStatus>({
    queryKey: ["inventory", "status"],
    queryFn: async () => {
      const response = await api.get(getEndpoint("/inventory/status"));
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

      const response = await api.get(`${getEndpoint("/inventory/items")}?${params.toString()}`);
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
      const response = await api.post(getEndpoint("/inventory/add-items"), data);
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
    onError: (error: unknown) => {
      toast.error(getErrorMessage(error, "Failed to add items"));
    },
  });
}

// Confirm a medium-confidence item
export function useConfirmItem() {
  const queryClient = useQueryClient();

  return useMutation<
    { item?: string },
    Error,
    { original_text: string; item_id: number; quantity_grams: number }
  >({
    mutationFn: async (data) => {
      const response = await api.post(getEndpoint("/inventory/confirm-item"), data);
      return response.data;
    },
    onSuccess: (data) => {
      toast.success(`${data.item ?? "Item"} added to inventory`);
      queryClient.invalidateQueries({ queryKey: ["inventory"] });
    },
    onError: (error: unknown) => {
      toast.error(getErrorMessage(error, "Failed to confirm item"));
    },
  });
}

// Delete inventory item
export function useDeleteItem() {
  const queryClient = useQueryClient();

  return useMutation<unknown, Error, number>({
    mutationFn: async (inventoryId) => {
      const response = await api.delete(getEndpoint(`/inventory/item/${inventoryId}`));
      return response.data;
    },
    onSuccess: () => {
      toast.success("Item removed from inventory");
      queryClient.invalidateQueries({ queryKey: ["inventory"] });
    },
    onError: (error: unknown) => {
      toast.error(getErrorMessage(error, "Failed to delete item"));
    },
  });
}

// Get recipes that can be made with current inventory
export function useMakeableRecipes(limit: number = 10) {
  return useQuery({
    queryKey: ["inventory", "makeable-recipes", limit],
    queryFn: async () => {
      const response = await api.get(`${getEndpoint("/inventory/makeable-recipes")}?limit=${limit}`);
      return response.data;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

// Generate AI creative recipes from inventory
export function useAIRecipes() {
  return useMutation<
    { recipes: AIRecipeSuggestion[]; mode?: string; items_available?: number; message?: string },
    Error,
    { mode: string }
  >({
    mutationFn: async ({ mode }) => {
      const response = await api.get(`${getEndpoint("/inventory/ai-recipes")}?mode=${mode}`);
      return response.data;
    },
  });
}

// Bulk add items from restock list to inventory
export function useBulkAddFromRestock() {
  const queryClient = useQueryClient();

  return useMutation<
    BulkAddFromRestockResponse,
    Error,
    { items: BulkAddFromRestockItem[]; suppressToast?: boolean }
  >({
    mutationFn: async ({ items }) => {
      const response = await api.post(
        getEndpoint("/inventory/bulk-add-from-restock"),
        { items }
      );
      return response.data;
    },
    onSuccess: (data, variables) => {
      if (!variables?.suppressToast && data.successfully_added > 0) {
        toast.success(
          `${data.successfully_added} item${data.successfully_added > 1 ? "s" : ""} added to inventory!`
        );
      }
      if (!variables?.suppressToast && data.failed_count > 0) {
        toast.error(
          `Failed to add ${data.failed_count} item${data.failed_count > 1 ? "s" : ""}`
        );
      }
      queryClient.invalidateQueries({ queryKey: ["inventory"] });
      queryClient.invalidateQueries({ queryKey: ["tracking", "restock-list"] });
    },
    onError: (error: unknown) => {
      toast.error(getErrorMessage(error, "Failed to add items to inventory"));
    },
  });
}
