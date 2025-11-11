"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { toast } from "sonner";
import {
  ReceiptUploadResult,
  PendingItem,
  EnrichedPendingItem,
  ReceiptPendingItemsResponse,
  ConfirmAndSeedResponse
} from "../types";

// Upload receipt for OCR processing
export function useUploadReceipt() {
  const queryClient = useQueryClient();

  return useMutation<ReceiptUploadResult, Error, File>({
    mutationFn: async (file) => {
      const formData = new FormData();
      formData.append("file", file);

      const response = await api.post("/receipt/upload", formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });
      return response.data;
    },
    onSuccess: (data) => {
      const autoAdded = data.auto_added_count;
      const needsConfirm = data.needs_confirmation_count;

      toast.success(
        `Receipt processed! ${autoAdded} items added${needsConfirm > 0 ? `, ${needsConfirm} need confirmation` : ""}`
      );

      queryClient.invalidateQueries({ queryKey: ["inventory"] });
      queryClient.invalidateQueries({ queryKey: ["receipt", "pending"] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to process receipt");
    },
  });
}

// Get pending items from a specific receipt (with enrichment data)
export function useReceiptPendingItems(receiptId: number | null) {
  return useQuery<ReceiptPendingItemsResponse>({
    queryKey: ["receipt", receiptId, "pending"],
    queryFn: async () => {
      if (!receiptId) throw new Error("Receipt ID is required");
      const response = await api.get(`/receipt/${receiptId}/pending`);
      return response.data;
    },
    enabled: !!receiptId,
    staleTime: 30 * 1000, // 30 seconds
  });
}

// DEPRECATED: Get pending items from receipts (old endpoint - kept for backwards compatibility)
export function usePendingItems() {
  return useQuery<{ count: number; items: PendingItem[] }>({
    queryKey: ["receipt", "pending"],
    queryFn: async () => {
      const response = await api.get("/receipt/pending");
      return response.data;
    },
    staleTime: 30 * 1000, // 30 seconds
  });
}

// Confirm and seed enriched receipt items (new endpoint with auto-seeding)
export function useConfirmAndSeedItems() {
  const queryClient = useQueryClient();

  return useMutation<
    ConfirmAndSeedResponse,
    Error,
    {
      items: Array<{
        pending_item_id: number;
        action: "confirm" | "skip";
      }>;
    }
  >({
    mutationFn: async (data) => {
      const response = await api.post("/receipt/confirm-and-seed", data);
      return response.data;
    },
    onSuccess: (data) => {
      const { added_count, seeded_count } = data;

      if (seeded_count > 0 && added_count > 0) {
        toast.success(
          `${seeded_count} new item${seeded_count > 1 ? 's' : ''} created and ${added_count} item${added_count > 1 ? 's' : ''} added to inventory`
        );
      } else if (added_count > 0) {
        toast.success(`${added_count} item${added_count > 1 ? 's' : ''} added to inventory`);
      }

      queryClient.invalidateQueries({ queryKey: ["inventory"] });
      queryClient.invalidateQueries({ queryKey: ["receipt"] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to confirm items");
    },
  });
}

// DEPRECATED: Confirm receipt items (old endpoint - kept for backwards compatibility)
export function useConfirmReceiptItems() {
  const queryClient = useQueryClient();

  return useMutation<
    { status: string; added_count: number },
    Error,
    {
      items: Array<{
        pending_item_id: number;
        action: "add" | "skip";
        item_id?: number;
        quantity_grams?: number;
      }>;
    }
  >({
    mutationFn: async (data) => {
      const response = await api.post("/receipt/confirm", data);
      return response.data;
    },
    onSuccess: (data) => {
      if (data.added_count > 0) {
        toast.success(`${data.added_count} item${data.added_count > 1 ? 's' : ''} added to inventory`);
      }

      queryClient.invalidateQueries({ queryKey: ["inventory"] });
      queryClient.invalidateQueries({ queryKey: ["receipt", "pending"] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to confirm items");
    },
  });
}

// Get receipt history
export function useReceiptHistory(limit: number = 10) {
  return useQuery({
    queryKey: ["receipt", "history", limit],
    queryFn: async () => {
      const response = await api.get(`/receipt/history?limit=${limit}`);
      return response.data;
    },
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}
