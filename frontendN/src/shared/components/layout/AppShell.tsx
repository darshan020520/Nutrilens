"use client";

import { Sidebar } from "@/shared/components/layout/Sidebar";
import { TopBar } from "@/shared/components/layout/TopBar";
import { MobileNav } from "@/shared/components/layout/MobileNav";

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="min-h-screen bg-transparent text-foreground">
      <Sidebar />
      <div className="md:pl-64 min-h-screen pb-20 md:pb-0">
        <TopBar />
        <main className="p-4 md:p-6">{children}</main>
      </div>
      <MobileNav />
    </div>
  );
}
