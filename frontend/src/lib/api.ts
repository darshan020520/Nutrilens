import axios from 'axios';

const API_URL = 'http://localhost:8000/api';

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
    const response = await api.post('/auth/register', { email, password });
    return response.data;
  },

  login: async (email: string, password: string) => {
    const formData = new FormData();
    formData.append('username', email);  // FastAPI OAuth2PasswordRequestForm uses 'username'
    formData.append('password', password);
    
    const response = await api.post('/auth/login', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  getMe: async () => {
    const response = await api.get('/auth/me');
    return response.data;
  },
};

// Onboarding API calls
export const onboardingAPI = {
  submitBasicInfo: async (data: any) => {
    const response = await api.post('/onboarding/basic-info', data);
    return response.data;
  },

  submitGoal: async (data: any) => {
    const response = await api.post('/onboarding/goal-selection', data);
    return response.data;
  },

  submitPath: async (data: any) => {
    const response = await api.post('/onboarding/path-selection', data);
    return response.data;
  },

  submitPreferences: async (data: any) => {
    const response = await api.post('/onboarding/preferences', data);
    return response.data;
  },
};