import { formatDistanceToNow, format } from "date-fns";

export function formatRelativeTime(value: Date | string | number): string {
  return formatDistanceToNow(new Date(value), { addSuffix: true });
}

export function formatDayLabel(value: Date | string | number, pattern = "EEE, MMM d"): string {
  return format(new Date(value), pattern);
}
