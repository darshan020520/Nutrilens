"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { ExpiringItem, RestockList } from "../types";

// Get expiring items with recipe suggestions
export function useExpiringItems(days: number = 3) {
  return useQuery<{
    total_expiring: number;
    urgent_count: number;
    high_priority_count: number;
    medium_priority_count: number;
    items: ExpiringItem[];
    action_recommendations: string[];
  }>({
    queryKey: ["tracking", "expiring-items", days],
    queryFn: async () => {
      const response = await api.get(`/tracking/expiring-items?days=${days}`);
      return response.data;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    refetchInterval: 10 * 60 * 1000, // Refetch every 10 minutes
  });
}

// Get smart restock/shopping list
export function useRestockList() {
  return useQuery<RestockList>({
    queryKey: ["tracking", "restock-list"],
    queryFn: async () => {
      const response = await api.get("/tracking/restock-list");
      return response.data;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

// Get inventory status (alternative endpoint from tracking)
export function useInventoryStatusTracking() {
  return useQuery({
    queryKey: ["tracking", "inventory-status"],
    queryFn: async () => {
      const response = await api.get("/tracking/inventory-status");
      return response.data;
    },
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}
