// frontend/src/app/dashboard/page.tsx
"use client";

import { DashboardLayout } from "@/components/layouts/DashboardLayout";
import { MealsCard } from "./components/MealsCard";
import { MacrosCard } from "./components/MacrosCard";
import { InventoryCard } from "./components/InventoryCard";
import { GoalCard } from "./components/GoalCard";
import { QuickActions } from "./components/QuickActions";
import { RecentActivity } from "./components/RecentActivity";
import { useDashboard } from "./hooks/useDashboard";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function DashboardPage() {
  const { summary, activity, isLoading, error, refetch } = useDashboard();

  if (error) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Alert variant="destructive" className="max-w-md">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription className="flex items-center justify-between gap-4">
              <span>Failed to load dashboard data</span>
              <Button variant="outline" size="sm" onClick={() => refetch()}>
                Try Again
              </Button>
            </AlertDescription>
          </Alert>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-8">
        {/* Page Header */}
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground mt-1">
            Welcome back! Here's your nutrition overview.
          </p>
        </div>

        {/* Summary Cards Grid */}
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          <MealsCard data={summary?.meals_card} isLoading={isLoading} />
          <MacrosCard data={summary?.macros_card} isLoading={isLoading} />
          <InventoryCard data={summary?.inventory_card} isLoading={isLoading} />
          <GoalCard data={summary?.goal_card} isLoading={isLoading} />
        </div>

        {/* Quick Actions */}
        <QuickActions />

        {/* Recent Activity */}
        <RecentActivity data={activity} isLoading={isLoading} />
      </div>
    </DashboardLayout>
  );
}