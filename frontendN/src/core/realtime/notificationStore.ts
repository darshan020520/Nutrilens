import { create } from "zustand";
import type { TrackingEvent } from "@/core/api/types";

type NotificationState = {
  items: TrackingEvent[];
  unreadCount: number;
  push: (event: TrackingEvent) => void;
  dismissAt: (index: number) => void;
  clearAll: () => void;
  markRead: () => void;
};

export const useNotificationStore = create<NotificationState>((set) => ({
  items: [],
  unreadCount: 0,
  push: (event) =>
    set((state) => ({
      items: [event, ...state.items].slice(0, 50),
      unreadCount: state.unreadCount + 1,
    })),
  dismissAt: (index) =>
    set((state) => {
      if (index < 0 || index >= state.items.length) {
        return state;
      }

      const nextItems = [...state.items];
      nextItems.splice(index, 1);
      return { items: nextItems };
    }),
  clearAll: () => set({ items: [], unreadCount: 0 }),
  markRead: () => set({ unreadCount: 0 }),
}));
