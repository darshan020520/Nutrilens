"use client";

import { useMemo } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { DashboardLayout } from "@/components/layouts/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Bot, Sparkles, MessageCircle } from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  BarChart,
  Bar,
} from "recharts";
import { api, getEndpoint } from "@/lib/api";

export default function NutritionPage() {
  const router = useRouter();

  const { data: todayData } = useQuery({
    queryKey: ["tracking", "today"],
    queryFn: async () => (await api.get(getEndpoint("/tracking/today"))).data,
    staleTime: 30 * 1000,
  });

  const { data: historyData } = useQuery({
    queryKey: ["tracking", "history", 7],
    queryFn: async () => (await api.get(getEndpoint("/tracking/history"), { params: { days: 7 } })).data,
    staleTime: 60 * 1000,
  });

  const { data: summaryData } = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: async () => (await api.get(getEndpoint("/dashboard/summary"))).data,
    staleTime: 60 * 1000,
  });

  const macroTrend = useMemo(() => {
    const rows = historyData?.history ?? [];
    return rows.map((day: any) => {
      const logged = day.meals?.filter((m: any) => m.status === "logged")?.length ?? 0;
      const total = day.meals?.length ?? 0;
      const adherence = total > 0 ? Math.round((logged / total) * 100) : 0;
      return {
        date: new Date(day.date).toLocaleDateString("en-US", { weekday: "short" }),
        adherence,
        logged,
      };
    });
  }, [historyData]);

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Nutrition Intelligence</h1>
          <p className="text-muted-foreground mt-1">
            Operational trends, adherence signals, and context-aware AI coaching
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Calories Today</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">{Math.round(todayData?.total_macros?.calories ?? 0)}</p>
              <p className="text-xs text-muted-foreground">
                of {Math.round(todayData?.target_macros?.calories ?? 0)} target
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Protein Today</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">{Math.round(todayData?.total_macros?.protein_g ?? 0)}g</p>
              <p className="text-xs text-muted-foreground">
                of {Math.round(todayData?.target_macros?.protein_g ?? 0)}g target
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Weekly Adherence</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">{Math.round(historyData?.statistics?.adherence_rate ?? 0)}%</p>
              <p className="text-xs text-muted-foreground">
                {historyData?.statistics?.logged_meals ?? 0} logged meals this period
              </p>
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Adherence Trend (7 days)</CardTitle>
            </CardHeader>
            <CardContent className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={macroTrend}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" />
                  <YAxis domain={[0, 100]} />
                  <Tooltip />
                  <Line type="monotone" dataKey="adherence" stroke="#0e8771" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Macro Snapshot</CardTitle>
            </CardHeader>
            <CardContent className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={[
                    {
                      name: "Protein",
                      value: Math.round(summaryData?.macros_card?.protein_percentage ?? 0),
                    },
                    {
                      name: "Carbs",
                      value: Math.round(summaryData?.macros_card?.carbs_percentage ?? 0),
                    },
                    {
                      name: "Fat",
                      value: Math.round(summaryData?.macros_card?.fat_percentage ?? 0),
                    },
                  ]}
                >
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis domain={[0, 120]} />
                  <Tooltip />
                  <Bar dataKey="value" fill="#0e8771" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>

        <Card className="border-primary/20 bg-gradient-to-br from-primary/5 via-background to-background">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bot className="h-6 w-6 text-primary" />
              AI Nutrition Assistant
              <Badge variant="outline" className="ml-auto">
                <Sparkles className="h-3 w-3 mr-1" />
                Context Aware
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-muted-foreground">
              Ask goal-aware questions and get recommendations backed by your meal logs,
              plan status, and current inventory context.
            </p>

            <div className="bg-muted/50 rounded-lg p-4 space-y-2">
              <p className="text-sm font-medium">Suggested prompts</p>
              <ul className="text-sm text-muted-foreground space-y-1">
                <li className="flex items-center gap-2">
                  <MessageCircle className="h-3 w-3" />
                  "How can I improve protein by dinner today?"
                </li>
                <li className="flex items-center gap-2">
                  <MessageCircle className="h-3 w-3" />
                  "Suggest a pantry-friendly high-protein option"
                </li>
                <li className="flex items-center gap-2">
                  <MessageCircle className="h-3 w-3" />
                  "What should I swap to stay on target?"
                </li>
              </ul>
            </div>

            <Button onClick={() => router.push("/dashboard/nutrition/chat")} size="lg" className="w-full">
              <Bot className="h-4 w-4 mr-2" />
              Open AI Coach
            </Button>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
