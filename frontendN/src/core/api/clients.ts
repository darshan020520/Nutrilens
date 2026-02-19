import { httpClient } from "@/core/api/httpClient";
import { getEndpoint } from "@/core/api/endpoints";
import type { DashboardSummaryVM } from "@/core/api/types";

export interface DashboardClient {
  getSummary: () => Promise<DashboardSummaryVM>;
  getRecentActivity: (limit?: number) => Promise<any>;
}

export interface MealPlanClient {
  getCurrentPlanWithStatus: () => Promise<any>;
  generate: (payload: Record<string, unknown>) => Promise<any>;
  swapMeal: (planId: number, payload: Record<string, unknown>) => Promise<any>;
  getAlternatives: (planId: number, recipeId: number, count?: number) => Promise<any>;
}

export interface TrackingClient {
  getToday: () => Promise<any>;
  getHistory: (days: number) => Promise<any>;
}

export interface InventoryClient {
  getStatus: () => Promise<any>;
  getItems: (params?: URLSearchParams) => Promise<any>;
}

export interface ReceiptClient {
  initiate: (payload: Record<string, unknown>) => Promise<any>;
  process: (payload: Record<string, unknown>) => Promise<any>;
}

export interface NutritionClient {
  chat: (payload: Record<string, unknown>) => Promise<any>;
  context: (minimal?: boolean) => Promise<any>;
}

export interface AuthClient {
  me: () => Promise<any>;
}

export interface OnboardingClient {
  submitBasicInfo: (payload: Record<string, unknown>) => Promise<any>;
}

export const dashboardClient: DashboardClient = {
  async getSummary() {
    const response = await httpClient.get(getEndpoint("/dashboard/summary"));
    return response.data;
  },
  async getRecentActivity(limit = 5) {
    const response = await httpClient.get(getEndpoint("/dashboard/recent-activity"), { params: { limit } });
    return response.data;
  },
};

export const mealPlanClient: MealPlanClient = {
  async getCurrentPlanWithStatus() {
    const response = await httpClient.get(getEndpoint("/meal-plans/current/with-status"));
    return response.data;
  },
  async generate(payload) {
    const response = await httpClient.post(getEndpoint("/meal-plans/generate"), payload);
    return response.data;
  },
  async swapMeal(planId, payload) {
    const response = await httpClient.post(getEndpoint(`/meal-plans/${planId}/swap-meal`), payload);
    return response.data;
  },
  async getAlternatives(planId, recipeId, count = 5) {
    const response = await httpClient.get(
      `${getEndpoint(`/meal-plans/${planId}/alternatives/${recipeId}`)}?count=${count}`
    );
    return response.data;
  },
};

export const trackingClient: TrackingClient = {
  async getToday() {
    const response = await httpClient.get(getEndpoint("/tracking/today"));
    return response.data;
  },
  async getHistory(days) {
    const response = await httpClient.get(getEndpoint("/tracking/history"), { params: { days } });
    return response.data;
  },
};

export const inventoryClient: InventoryClient = {
  async getStatus() {
    const response = await httpClient.get(getEndpoint("/inventory/status"));
    return response.data;
  },
  async getItems(params) {
    const query = params?.toString() || "";
    const response = await httpClient.get(`${getEndpoint("/inventory/items")}?${query}`);
    return response.data;
  },
};

export const receiptClient: ReceiptClient = {
  async initiate(payload) {
    const response = await httpClient.post(getEndpoint("/receipt/initiate"), payload);
    return response.data;
  },
  async process(payload) {
    const response = await httpClient.post(getEndpoint("/receipt/process"), payload);
    return response.data;
  },
};

export const nutritionClient: NutritionClient = {
  async chat(payload) {
    const response = await httpClient.post("/nutrition/chat", payload);
    return response.data;
  },
  async context(minimal = false) {
    const response = await httpClient.get("/nutrition/context", { params: { minimal } });
    return response.data;
  },
};

export const authClient: AuthClient = {
  async me() {
    const response = await httpClient.get(getEndpoint("/auth/me"));
    return response.data;
  },
};

export const onboardingClient: OnboardingClient = {
  async submitBasicInfo(payload) {
    const response = await httpClient.post(getEndpoint("/onboarding/basic-info"), payload);
    return response.data;
  },
};
