'use client';

const FIRST_NAME_KEY = 'nutrilens:onboarding:first-name';

export function extractFirstName(fullName: string): string {
  const trimmed = fullName.trim();
  if (!trimmed) return '';
  const [firstName] = trimmed.split(/\s+/);
  return firstName ?? '';
}

export function setOnboardingFirstName(name: string): void {
  if (typeof window === 'undefined') return;
  const safeName = name.trim();
  if (!safeName) {
    window.sessionStorage.removeItem(FIRST_NAME_KEY);
    return;
  }
  window.sessionStorage.setItem(FIRST_NAME_KEY, safeName);
}

export function getOnboardingFirstName(): string {
  if (typeof window === 'undefined') return '';
  return window.sessionStorage.getItem(FIRST_NAME_KEY) ?? '';
}
