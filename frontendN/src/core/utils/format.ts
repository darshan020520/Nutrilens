export function formatCalories(value: number): string {
  return `${Math.round(value)} cal`;
}

export function formatPercent(value: number): string {
  return `${Math.round(value)}%`;
}

export function formatWeightGrams(value: number): string {
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)} kg`;
  }
  return `${Math.round(value)} g`;
}
