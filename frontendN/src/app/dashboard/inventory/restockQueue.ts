"use client";

export type RestockQueue = {
  itemIds: number[];
  ingredientNames: string[];
};

const RESTOCK_QUEUE_KEY = "nutrilens:restock:queue";

function normalizeName(name: string): string {
  return name.trim().toLowerCase();
}

function readQueueUnsafe(): RestockQueue {
  if (typeof window === "undefined") {
    return { itemIds: [], ingredientNames: [] };
  }

  const raw = window.localStorage.getItem(RESTOCK_QUEUE_KEY);
  if (!raw) {
    return { itemIds: [], ingredientNames: [] };
  }

  try {
    const parsed = JSON.parse(raw) as Partial<RestockQueue>;
    const itemIds = Array.isArray(parsed.itemIds)
      ? parsed.itemIds.filter((id): id is number => typeof id === "number")
      : [];
    const ingredientNames = Array.isArray(parsed.ingredientNames)
      ? parsed.ingredientNames.filter((name): name is string => typeof name === "string")
      : [];
    return { itemIds, ingredientNames };
  } catch {
    return { itemIds: [], ingredientNames: [] };
  }
}

function writeQueue(queue: RestockQueue): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(RESTOCK_QUEUE_KEY, JSON.stringify(queue));
}

export function getRestockQueue(): RestockQueue {
  return readQueueUnsafe();
}

export function queueRestockItem(itemId: number): void {
  const queue = readQueueUnsafe();
  const nextItemIds = new Set(queue.itemIds);
  nextItemIds.add(itemId);
  writeQueue({
    ...queue,
    itemIds: Array.from(nextItemIds),
  });
}

export function queueRestockIngredients(names: string[]): void {
  const queue = readQueueUnsafe();
  const normalized = queue.ingredientNames.map(normalizeName);
  const nextNameSet = new Set(normalized);
  names.forEach((name) => {
    const normalizedName = normalizeName(name);
    if (normalizedName) nextNameSet.add(normalizedName);
  });
  writeQueue({
    ...queue,
    ingredientNames: Array.from(nextNameSet),
  });
}

export function unqueueRestockItem(itemId: number): void {
  const queue = readQueueUnsafe();
  writeQueue({
    ...queue,
    itemIds: queue.itemIds.filter((id) => id !== itemId),
  });
}

export function unqueueRestockIngredient(name: string): void {
  const normalizedTarget = normalizeName(name);
  const queue = readQueueUnsafe();
  writeQueue({
    ...queue,
    ingredientNames: queue.ingredientNames.filter((entry) => normalizeName(entry) !== normalizedTarget),
  });
}

export function clearRestockQueue(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(RESTOCK_QUEUE_KEY);
}
