"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, getEndpoint } from "@/lib/api";
import { toast } from "sonner";
import {
  ReceiptUploadResult,
  PendingItem,
  ReceiptPendingItemsResponse,
  ConfirmAndSeedResponse
} from "../types";

type ApiErrorLike = {
  response?: {
    data?: {
      detail?: string;
    };
  };
  message?: string;
};

function getErrorMessage(error: unknown, fallback: string): string {
  const casted = error as ApiErrorLike;
  if (typeof casted?.response?.data?.detail === "string") {
    return casted.response.data.detail;
  }
  if (typeof casted?.message === "string") {
    return casted.message;
  }
  return fallback;
}

// Upload receipt for OCR processing
export function useUploadReceipt() {
  const queryClient = useQueryClient();

  return useMutation<ReceiptUploadResult, Error, File>({
    mutationFn: async (file: File) => {
      // 1. INITIATE: Get permission from our backend
      const initResponse = await api.post(getEndpoint("/receipt/initiate"), {
        filename: file.name,
        content_type: file.type,
      });

      const { presigned_url, s3_key, receipt_id } = initResponse.data;

      // 2. UPLOAD: Go directly to AWS S3
      // Note: We use the native 'fetch' here, not 'api' (axios), 
      // because we don't want our Auth headers or base URL sent to Amazon.
      const uploadToS3 = await fetch(presigned_url, {
        method: "PUT",
        body: file,
        headers: {
          "Content-Type": file.type,
        },
      });

      if (!uploadToS3.ok) {
        throw new Error("S3 Upload Failed: Check bucket CORS settings.");
      }

      // 3. PROCESS: Trigger the AI logic
      const processResponse = await api.post(getEndpoint("/receipt/process"), {
        receipt_id: receipt_id,
        s3_key: s3_key,
      });

      return processResponse.data;
    },
    onSuccess: () => {
      toast.success("AI is processing your receipt!");
      queryClient.invalidateQueries({ queryKey: ["inventory"] });
      queryClient.invalidateQueries({ queryKey: ["receipt"] });
    },
    onError: (error: unknown) => {
      toast.error(getErrorMessage(error, "Failed to process receipt"));
    },
  });
}

// Get pending items from a specific receipt (with enrichment data)
export function useReceiptPendingItems(receiptId: number | null) {
  return useQuery<ReceiptPendingItemsResponse>({
    queryKey: ["receipt", receiptId, "pending"],
    queryFn: async () => {
      if (!receiptId) throw new Error("Receipt ID is required");
      const response = await api.get(getEndpoint(`/receipt/${receiptId}/pending`));
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
      const response = await api.get(getEndpoint("/receipt/pending"));
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
      const response = await api.post(getEndpoint("/receipt/confirm-and-seed"), data);
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
    onError: (error: unknown) => {
      toast.error(getErrorMessage(error, "Failed to confirm items"));
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
      const response = await api.post(getEndpoint("/receipt/confirm"), data);
      return response.data;
    },
    onSuccess: (data) => {
      if (data.added_count > 0) {
        toast.success(`${data.added_count} item${data.added_count > 1 ? 's' : ''} added to inventory`);
      }

      queryClient.invalidateQueries({ queryKey: ["inventory"] });
      queryClient.invalidateQueries({ queryKey: ["receipt", "pending"] });
    },
    onError: (error: unknown) => {
      toast.error(getErrorMessage(error, "Failed to confirm items"));
    },
  });
}

// Get receipt history
export function useReceiptHistory(limit: number = 10) {
  return useQuery({
    queryKey: ["receipt", "history", limit],
    queryFn: async () => {
      const response = await api.get(`${getEndpoint("/receipt/history")}?limit=${limit}`);
      return response.data;
    },
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}
