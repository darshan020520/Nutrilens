export interface User {
  id: number;
  email: string;
  is_active: boolean;
  onboarding_completed: boolean;
  onboarding_current_step: number;
  basic_info_completed: boolean;
  goal_selection_completed: boolean;
  path_selection_completed: boolean;
  preferences_completed: boolean;
}

export interface OnboardingStatus {
  completed: boolean;
  current_step: number;
  completed_steps: number[];
  redirect_to: string;
  next_step_name: string | null;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}