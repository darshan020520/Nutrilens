import type { DashboardSummaryVM } from "@/core/api/types";

export function toDashboardSummaryVM(raw: any): DashboardSummaryVM {
  return raw as DashboardSummaryVM;
}

export function toTodayMealsVM(raw: any): any {
  return raw;
}

export function toInventoryStatusVM(raw: any): any {
  return raw;
}

export function toReceiptReviewVM(raw: any): any {
  return raw;
}

export function toHistoryVM(raw: any): any {
  return raw;
}
