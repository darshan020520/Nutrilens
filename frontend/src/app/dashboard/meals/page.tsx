// frontend/src/app/dashboard/meals/page.tsx
"use client";

import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Calendar, Clock, Book, History } from "lucide-react";
import { DashboardLayout } from "@/components/layouts/DashboardLayout";

// Import all tab components
import { WeekView } from "./components/WeekView";
import { TodayView } from "./components/TodayView";
import { RecipeBrowser } from "./components/RecipeBrowser";
import { MealHistory } from "./components/MealHistory";

export default function MealsPage() {
  const [activeTab, setActiveTab] = useState("week");

  return (
    <DashboardLayout>
      <div className="container mx-auto py-6 px-4 md:px-6 space-y-6">
        {/* Page Header */}
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Meal Planning</h1>
          <p className="text-muted-foreground mt-1">
            Plan your meals, track nutrition, and stay on target
          </p>
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="grid w-full grid-cols-4 lg:w-[600px]">
            <TabsTrigger value="week" className="gap-2">
              <Calendar className="h-4 w-4" />
              <span className="hidden sm:inline">This Week</span>
              <span className="sm:hidden">Week</span>
            </TabsTrigger>
            <TabsTrigger value="today" className="gap-2">
              <Clock className="h-4 w-4" />
              <span className="hidden sm:inline">Today</span>
              <span className="sm:hidden">Today</span>
            </TabsTrigger>
            <TabsTrigger value="recipes" className="gap-2">
              <Book className="h-4 w-4" />
              <span className="hidden sm:inline">Recipes</span>
              <span className="sm:hidden">Browse</span>
            </TabsTrigger>
            <TabsTrigger value="history" className="gap-2">
              <History className="h-4 w-4" />
              <span className="hidden sm:inline">History</span>
              <span className="sm:hidden">Past</span>
            </TabsTrigger>
          </TabsList>

          {/* Tab 1: This Week's Plan */}
          <TabsContent value="week" className="space-y-4">
            <WeekView />
          </TabsContent>

          {/* Tab 2: Today's Meals */}
          <TabsContent value="today" className="space-y-4">
            <TodayView />
          </TabsContent>

          {/* Tab 3: Recipe Browser */}
          <TabsContent value="recipes" className="space-y-4">
            <RecipeBrowser />
          </TabsContent>

          {/* Tab 4: Meal History */}
          <TabsContent value="history" className="space-y-4">
            <MealHistory />
          </TabsContent>
        </Tabs>
      </div>
    </DashboardLayout>
  );
}