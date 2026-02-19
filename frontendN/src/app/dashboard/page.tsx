"use client";

import { DashboardLayout } from "@/components/layouts/DashboardLayout";
import { MealsCard } from "./components/MealsCard";
import { MacrosCard } from "./components/MacrosCard";
import { InventoryCard } from "./components/InventoryCard";
import { GoalCard } from "./components/GoalCard";
import { QuickActions } from "./components/QuickActions";
import { RecentActivity } from "./components/RecentActivity";
import { useDashboard } from "./hooks/useDashboard";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";

export default function DashboardPage() {
  const router = useRouter();
  const { summary, activity, isLoading, error, refetch } = useDashboard();

  const remainingCalories = Math.max(
    0,
    (summary?.macros_card.calories_target ?? 0) - (summary?.macros_card.calories_consumed ?? 0)
  );

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
        <section className="rounded-2xl border bg-card p-6 md:p-8">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">Daily Command Center</p>
              <h1 className="text-3xl md:text-4xl font-bold tracking-tight">Plan. Eat. Track. Adapt.</h1>
              <p className="text-muted-foreground max-w-xl">
                {summary?.meals_card.next_meal
                  ? `Next meal: ${summary.meals_card.next_meal} at ${summary.meals_card.next_meal_time}`
                  : "No next meal scheduled yet. Generate or review your current meal plan."}
              </p>
            </div>

            <div className="rounded-xl border bg-background p-4 min-w-[220px]">
              <p className="text-xs text-muted-foreground">Remaining Calories</p>
              <p className="text-3xl font-bold mt-1">{Math.round(remainingCalories)}</p>
              <Button className="w-full mt-3" size="sm" onClick={() => router.push("/dashboard/meals?tab=today")}>
                Continue Today
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            </div>
          </div>
        </section>

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          <MealsCard data={summary?.meals_card} isLoading={isLoading} />
          <MacrosCard data={summary?.macros_card} isLoading={isLoading} />
          <InventoryCard data={summary?.inventory_card} isLoading={isLoading} />
          <GoalCard data={summary?.goal_card} isLoading={isLoading} />
        </div>

        <QuickActions />

        <RecentActivity data={activity} isLoading={isLoading} />
      </div>
    </DashboardLayout>
  );
}
