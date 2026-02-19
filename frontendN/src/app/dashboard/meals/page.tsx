"use client";

import { useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Calendar, Clock, Book, History } from "lucide-react";
import { DashboardLayout } from "@/components/layouts/DashboardLayout";

import { WeekView } from "./components/WeekView";
import { TodayView } from "./components/TodayView";
import { RecipeBrowser } from "./components/RecipeBrowser";
import { MealHistory } from "./components/MealHistory";

const allowedTabs = new Set(["week", "today", "recipes", "history"]);

export default function MealsPage() {
  const searchParams = useSearchParams();
  const initialTab = useMemo(() => {
    const value = searchParams.get("tab") || "today";
    return allowedTabs.has(value) ? value : "today";
  }, [searchParams]);

  const [activeTab, setActiveTab] = useState(initialTab);

  return (
    <DashboardLayout>
      <div className="container mx-auto py-6 px-4 md:px-6 space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Meal Execution Hub</h1>
          <p className="text-muted-foreground mt-1">
            Manage today first, then optimize the week and review historical adherence
          </p>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="grid w-full grid-cols-4 lg:w-[600px]">
            <TabsTrigger value="today" className="gap-2">
              <Clock className="h-4 w-4" />
              <span>Today</span>
            </TabsTrigger>
            <TabsTrigger value="week" className="gap-2">
              <Calendar className="h-4 w-4" />
              <span>This Week</span>
            </TabsTrigger>
            <TabsTrigger value="recipes" className="gap-2">
              <Book className="h-4 w-4" />
              <span>Recipes</span>
            </TabsTrigger>
            <TabsTrigger value="history" className="gap-2">
              <History className="h-4 w-4" />
              <span>History</span>
            </TabsTrigger>
          </TabsList>

          <TabsContent value="today" className="space-y-4">
            <TodayView />
          </TabsContent>

          <TabsContent value="week" className="space-y-4">
            <WeekView />
          </TabsContent>

          <TabsContent value="recipes" className="space-y-4">
            <RecipeBrowser />
          </TabsContent>

          <TabsContent value="history" className="space-y-4">
            <MealHistory />
          </TabsContent>
        </Tabs>
      </div>
    </DashboardLayout>
  );
}
