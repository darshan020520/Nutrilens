"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Bell, Search, LogOut, User, Settings, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { formatRelativeTime } from "@/core/utils/date";
import { useNotificationStore } from "@/core/realtime/notificationStore";
import { useTrackingSocket } from "@/core/realtime/useTrackingSocket";
import { clearSession, getUserEmail } from "@/core/auth/sessionStore";

export function TopBar() {
  const router = useRouter();
  // useTrackingSocket(true);  // WebSocket disabled temporarily

  const items = useNotificationStore((state) => state.items);
  const unread = useNotificationStore((state) => state.unreadCount);
  const markRead = useNotificationStore((state) => state.markRead);
  const clearAll = useNotificationStore((state) => state.clearAll);
  const dismissAt = useNotificationStore((state) => state.dismissAt);

  const email = getUserEmail() || "user@example.com";
  const initials = email.split("@")[0].slice(0, 2).toUpperCase();

  const handleLogout = () => {
    clearSession();
    router.push("/login");
  };

  return (
    <header className="sticky top-0 z-20 h-16 border-b bg-background/95 backdrop-blur px-4 md:px-6 flex items-center gap-4">
      <div className="relative w-full max-w-lg">
        <Search className="h-4 w-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
        <Input aria-label="Global command search" placeholder="Search meals, recipes, pantry..." className="pl-9" />
      </div>

      <div className="ml-auto flex items-center gap-2">
        <DropdownMenu onOpenChange={(open) => !open && markRead()}>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="relative" aria-label="Open notifications">
              <Bell className="h-5 w-5" />
              {unread > 0 && (
                <span className="absolute -top-0.5 -right-0.5 h-4 min-w-4 px-1 rounded-full bg-destructive text-[10px] text-white leading-4 text-center">
                  {unread > 9 ? "9+" : unread}
                </span>
              )}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-[360px]">
            <div className="flex items-center justify-between px-2 py-1">
              <DropdownMenuLabel className="px-0">Notifications</DropdownMenuLabel>
              <Button size="sm" variant="ghost" onClick={clearAll}>Clear</Button>
            </div>
            <DropdownMenuSeparator />
            <ScrollArea className="h-[320px]">
              <div className="p-2 space-y-2">
                {items.length === 0 && (
                  <p className="text-sm text-muted-foreground p-3">No recent alerts</p>
                )}
                {items.map((item, idx) => (
                  <div key={`${item.event_type}-${idx}`} className="rounded-md border p-3 space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <Badge variant="outline" className="text-[10px]">{item.event_type}</Badge>
                        {item.timestamp && (
                          <span className="text-[11px] text-muted-foreground truncate">
                            {formatRelativeTime(item.timestamp)}
                          </span>
                        )}
                      </div>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-6 w-6 shrink-0"
                        onClick={() => dismissAt(idx)}
                        aria-label="Dismiss notification"
                      >
                        <X className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                    <p className="text-sm">{item.message}</p>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </DropdownMenuContent>
        </DropdownMenu>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="rounded-full h-9 w-9 p-0">
              <Avatar>
                <AvatarFallback>{initials}</AvatarFallback>
              </Avatar>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>
              <div className="flex flex-col">
                <span className="text-sm font-medium">My Account</span>
                <span className="text-xs text-muted-foreground">{email}</span>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link href="/dashboard/profile"><User className="h-4 w-4 mr-2" />Profile</Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href="/dashboard/settings"><Settings className="h-4 w-4 mr-2" />Settings</Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleLogout} className="text-destructive">
              <LogOut className="h-4 w-4 mr-2" />Logout
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
