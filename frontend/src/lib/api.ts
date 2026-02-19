import axios from 'axios';

const API_URL = 'http://localhost:8000/api';

// ============================================================
// FEATURE FLAG: Toggle between v1 and v2 endpoints
// ============================================================
// Set to true to use new clean architecture v2 endpoints
// Set to false to use legacy v1 endpoints
const USE_V2_ENDPOINTS = true;
// ============================================================

/**
 * Helper function to get the correct endpoint based on feature flag
 * Maps v1 endpoints to their v2 equivalents
 */
export function getEndpoint(v1Path: string): string {
  if (!USE_V2_ENDPOINTS) {
    return v1Path;
  }

  // Mapping of v1 endpoints to v2 endpoints
  const endpointMap: Record<string, string> = {
    // Auth endpoints
    '/auth/register': '/auth/v2/register',
    '/auth/login': '/auth/v2/login',
    '/auth/me': '/auth/v2/me',
    '/auth/refresh': '/auth/v2/refresh',
    '/auth/verify-email': '/auth/v2/verify-email',
    '/auth/resend-verification': '/auth/v2/resend-verification',

    // Onboarding endpoints
    '/onboarding/basic-info': '/onboarding/v2/basic-info',
    '/onboarding/goal-selection': '/onboarding/v2/goal-selection',
    '/onboarding/path-selection': '/onboarding/v2/path-selection',
    '/onboarding/preferences': '/onboarding/v2/preferences',
    '/onboarding/calculated-targets': '/onboarding/v2/calculated-targets',

    // Inventory endpoints
    '/inventory/add-items': '/inventory/v2/add-items',
    '/inventory/confirm-item': '/inventory/v2/confirm-item',
    '/inventory/status': '/inventory/v2/status',
    '/inventory/items': '/inventory/v2/items',
    '/inventory/makeable-recipes': '/inventory/v2/makeable-recipes',
    '/inventory/ai-recipes': '/inventory/v2/ai-recipes',
    '/inventory/bulk-add-from-restock': '/inventory/v2/bulk-add-from-restock',
    '/inventory/item/': '/inventory/v2/item/',

    // Receipt endpoints (specific paths first, then generic)
    '/receipt/upload': '/receipt/v2/upload',
    '/receipt/confirm-and-seed': '/receipt/v2/confirm-and-seed',
    '/receipt/': '/receipt/v2/',  // Handles dynamic paths like /receipt/123/pending

    // Recipes endpoints
    '/recipes/': '/recipes/v2/',

    // Meal Plan endpoints (specific paths first, then generic)
    '/meal-plans/generate': '/meal-plans/v2/generate',
    '/meal-plans/current/with-status': '/meal-plans/v2/current/with-status',
    '/meal-plans/': '/meal-plans/v2/',  // Handles dynamic paths like /meal-plans/123/grocery-list

    // Tracking endpoints
    '/tracking/log-meal': '/tracking/v2/log-meal',
    '/tracking/log-external-meal': '/tracking/v2/log-external-meal',
    '/tracking/skip-meal': '/tracking/v2/skip-meal',
    '/tracking/today': '/tracking/v2/today',
    '/tracking/history': '/tracking/v2/history',
    '/tracking/estimate-external-meal': '/tracking/v2/estimate-external-meal',
    '/tracking/inventory-status': '/tracking/v2/inventory-status',
    '/tracking/restock-list': '/tracking/v2/restock-list',
    '/tracking/expiring-items': '/tracking/v2/expiring-items',

    // Dashboard endpoints
    '/dashboard/summary': '/dashboard/v2/summary',
    '/dashboard/recent-activity': '/dashboard/v2/recent-activity',
  };

  // Handle dynamic paths (e.g., /inventory/item/:id)
  for (const [v1, v2] of Object.entries(endpointMap)) {
    if (v1Path.startsWith(v1)) {
      return v1Path.replace(v1, v2);
    }
  }

  // If no mapping found, return original path
  return v1Path;
}

// Create axios instance
export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor - add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor - handle errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Clear token and redirect to login
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Auth API calls
export const authAPI = {
  register: async (email: string, password: string) => {
    const response = await api.post(getEndpoint('/auth/register'), { email, password });
    return response.data;
  },

  login: async (email: string, password: string) => {
    const formData = new FormData();
    formData.append('username', email);  // FastAPI OAuth2PasswordRequestForm uses 'username'
    formData.append('password', password);

    const response = await api.post(getEndpoint('/auth/login'), formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  getMe: async () => {
    const response = await api.get(getEndpoint('/auth/me'));
    return response.data;
  },

  verifyEmail: async (token: string) => {
    const response = await api.post(getEndpoint('/auth/verify-email'), { token });
    return response.data;
  },

  resendVerification: async (email: string) => {
    const response = await api.post(getEndpoint('/auth/resend-verification'), { email });
    return response.data;
  },
};

// Onboarding API calls
export const onboardingAPI = {
  submitBasicInfo: async (data: any) => {
    const response = await api.post(getEndpoint('/onboarding/basic-info'), data);
    return response.data;
  },

  submitGoal: async (data: any) => {
    const response = await api.post(getEndpoint('/onboarding/goal-selection'), data);
    return response.data;
  },

  submitPath: async (data: any) => {
    const response = await api.post(getEndpoint('/onboarding/path-selection'), data);
    return response.data;
  },

  submitPreferences: async (data: any) => {
    const response = await api.post(getEndpoint('/onboarding/preferences'), data);
    return response.data;
  },

  getCalculatedTargets: async () => {
    const response = await api.get(getEndpoint('/onboarding/calculated-targets'));
    return response.data;
  },
};
