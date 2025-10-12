// frontend/src/app/dashboard/nutrition/page.tsx
"use client";

import { DashboardLayout } from "@/components/layouts/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BarChart3 } from "lucide-react";

export default function NutritionPage() {
  return (
    <DashboardLayout>
      <div className="container mx-auto py-6 px-4 md:px-6 space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Nutrition Analytics</h1>
          <p className="text-muted-foreground mt-1">
            Track your progress and analyze your nutrition
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5" />
              Coming Soon
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">
              Nutrition dashboard is under development. This will show:
            </p>
            <ul className="list-disc list-inside mt-4 space-y-2 text-sm text-muted-foreground">
              <li>Macro trends over time</li>
              <li>Goal progress charts</li>
              <li>Adherence heatmaps</li>
              <li>AI-powered insights</li>
              <li>Weight tracking</li>
            </ul>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}