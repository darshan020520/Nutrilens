'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/store/authStore';
import { authAPI } from '@/lib/api';

export function useAuth() {
  const router = useRouter();
  const { user, onboardingStatus, isAuthenticated, setUser, setOnboardingStatus, logout } = useAuthStore();

  useEffect(() => {
    // Check if user is logged in on mount
    const token = localStorage.getItem('access_token');
    if (token && !user) {
      checkAuth();
    }
  }, [user]); // Added dependency

  const checkAuth = async () => {
    try {
      const response = await authAPI.getMe();
      setUser(response.data.user);
      setOnboardingStatus(response.data.onboarding);

      // Redirect based on onboarding status
      if (!response.data.onboarding.completed) {
        router.push(response.data.onboarding.redirect_to);
      }
    } catch (error) {
      logout();
      router.push('/login');
    }
  };

  const login = async (email: string, password: string) => {
    const response = await authAPI.login(email, password);
    localStorage.setItem('access_token', response.access_token);
    setUser(response.user);
    
    // Get onboarding status
    const meResponse = await authAPI.getMe();
    setOnboardingStatus(meResponse.data.onboarding);
    
    
    return meResponse.data.onboarding;
  };

  const register = async (email: string, password: string) => {
    const response = await authAPI.register(email, password);
    return response;
  };

  return {
    user,
    onboardingStatus,
    isAuthenticated,
    login,
    register,
    logout,
    checkAuth,
  };
}