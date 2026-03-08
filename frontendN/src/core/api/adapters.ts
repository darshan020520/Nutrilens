import type { DashboardSummaryVM } from "@/core/api/types";

export function toDashboardSummaryVM(raw: unknown): DashboardSummaryVM {
  return raw as DashboardSummaryVM;
}

export function toTodayMealsVM(raw: unknown): unknown {
  return raw;
}

export function toInventoryStatusVM(raw: unknown): unknown {
  return raw;
}

export function toReceiptReviewVM(raw: unknown): unknown {
  return raw;
}

export function toHistoryVM(raw: unknown): unknown {
  return raw;
}
