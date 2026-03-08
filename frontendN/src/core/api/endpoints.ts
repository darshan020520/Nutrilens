const USE_V2_ENDPOINTS = true;

const endpointMap: Record<string, string> = {
  "/auth/register": "/auth/v2/register",
  "/auth/login": "/auth/v2/login",
  "/auth/me": "/auth/v2/me",
  "/auth/refresh": "/auth/v2/refresh",
  "/auth/verify-email": "/auth/v2/verify-email",
  "/auth/resend-verification": "/auth/v2/resend-verification",

  "/onboarding/basic-info": "/onboarding/v2/basic-info",
  "/onboarding/goal-selection": "/onboarding/v2/goal-selection",
  "/onboarding/path-selection": "/onboarding/v2/path-selection",
  "/onboarding/preferences": "/onboarding/v2/preferences",
  "/onboarding/calculated-targets": "/onboarding/v2/calculated-targets",
  "/onboarding/lock-targets": "/onboarding/v2/lock-targets",

  "/inventory/add-items": "/inventory/v2/add-items",
  "/inventory/confirm-item": "/inventory/v2/confirm-item",
  "/inventory/status": "/inventory/v2/status",
  "/inventory/items": "/inventory/v2/items",
  "/inventory/makeable-recipes": "/inventory/v2/makeable-recipes",
  "/inventory/ai-recipes": "/inventory/v2/ai-recipes",
  "/inventory/bulk-add-from-restock": "/inventory/v2/bulk-add-from-restock",
  "/inventory/item/": "/inventory/v2/item/",

  "/receipt/initiate": "/receipt/v2/initiate",
  "/receipt/process": "/receipt/v2/process",
  "/receipt/upload": "/receipt/v2/upload",
  "/receipt/confirm-and-seed": "/receipt/v2/confirm-and-seed",
  "/receipt/": "/receipt/v2/",

  "/recipes/": "/recipes/v2/",

  "/meal-plans/generate": "/meal-plans/v2/generate",
  "/meal-plans/current/with-status": "/meal-plans/v2/current/with-status",
  "/meal-plans/": "/meal-plans/v2/",

  "/tracking/log-meal": "/tracking/v2/log-meal",
  "/tracking/log-external-meal": "/tracking/v2/log-external-meal",
  "/tracking/skip-meal": "/tracking/v2/skip-meal",
  "/tracking/today": "/tracking/v2/today",
  "/tracking/history": "/tracking/v2/history",
  "/tracking/estimate-external-meal": "/tracking/v2/estimate-external-meal",
  "/tracking/inventory-status": "/tracking/v2/inventory-status",
  "/tracking/restock-list": "/tracking/v2/restock-list",
  "/tracking/expiring-items": "/tracking/v2/expiring-items",

  "/dashboard/summary": "/dashboard/v2/summary",
  "/dashboard/recent-activity": "/dashboard/v2/recent-activity",
};

export function getEndpoint(path: string): string {
  if (!USE_V2_ENDPOINTS) {
    return path;
  }

  for (const [source, target] of Object.entries(endpointMap)) {
    if (path.startsWith(source)) {
      return path.replace(source, target);
    }
  }

  return path;
}

export const ApiEndpoints = endpointMap;
