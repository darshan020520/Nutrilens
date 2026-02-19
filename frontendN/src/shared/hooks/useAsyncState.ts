import { useMemo } from "react";

export function useAsyncState<T>(data: T | undefined, fallback: T): T {
  return useMemo(() => data ?? fallback, [data, fallback]);
}
