import { create } from "zustand";
import type { TrackingEvent } from "@/core/api/types";

type NotificationState = {
  items: TrackingEvent[];
  unreadCount: number;
  push: (event: TrackingEvent) => void;
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
  clearAll: () => set({ items: [], unreadCount: 0 }),
  markRead: () => set({ unreadCount: 0 }),
}));
