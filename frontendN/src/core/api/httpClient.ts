import axios from "axios";

function resolveApiBaseUrl(): string {
  const envBase = process.env.NEXT_PUBLIC_API_URL?.trim();
  const fallbackBase = "http://localhost:8000";
  const normalizedBase = (envBase || fallbackBase).replace(/\/+$/, "");
  return normalizedBase.endsWith("/api") ? normalizedBase : `${normalizedBase}/api`;
}

const API_URL = resolveApiBaseUrl();

export const httpClient = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

httpClient.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }

  return config;
});

httpClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (typeof window !== "undefined" && error.response?.status === 401) {
      localStorage.removeItem("access_token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);
