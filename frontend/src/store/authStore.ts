import { create } from 'zustand';
import { User, OnboardingStatus } from '@/types';

interface AuthState {
  user: User | null;
  onboardingStatus: OnboardingStatus | null;
  isAuthenticated: boolean;
  setUser: (user: User) => void;
  setOnboardingStatus: (status: OnboardingStatus) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  onboardingStatus: null,
  isAuthenticated: false,

  setUser: (user) => set({ user, isAuthenticated: true }),

  setOnboardingStatus: (status) => set({ onboardingStatus: status }),

  logout: () => {
    localStorage.removeItem('access_token');
    set({ user: null, onboardingStatus: null, isAuthenticated: false });
  },
}));