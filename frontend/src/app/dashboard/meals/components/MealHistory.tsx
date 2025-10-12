// frontend/src/app/dashboard/meals/components/MealHistory.tsx
"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ChevronDown, ChevronUp, TrendingUp, TrendingDown } from "lucide-react";
import { api } from "@/lib/api";

interface MealLog {
  meal_type: string;
  recipe_name: string;
  status: "logged" | "pending" | "skipped";
  time?: string;
}

interface DayHistory {
  date: string;
  meals: MealLog[];
}

interface HistoryData {
  period: {
    start_date: string;
    end_date: string;
    days: number;
  };
  statistics: {
    total_meals: number;
    logged_meals: number;
    skipped_meals: number;
    adherence_rate: number;
  };
  history: DayHistory[];
}

export function MealHistory() {
  const [days, setDays] = useState<number>(7);
  const [expandedDays, setExpandedDays] = useState<Set<string>>(new Set());

  // Fetch meal history
  const { data: historyData, isLoading, error } = useQuery<HistoryData>({
    queryKey: ["tracking", "history", days],
    queryFn: async () => {
      const response = await api.get("/tracking/history", {
        params: { days },
      });
      return response.data;
    },
    staleTime: 2 * 60 * 1000, // 2 minutes
  });

  const toggleDay = (date: string) => {
    setExpandedDays((prev) => {
      const next = new Set(prev);
      if (next.has(date)) {
        next.delete(date);
      } else {
        next.add(date);
      }
      return next;
    });
  };

  const getMealStatusBadge = (status: string) => {
    switch (status) {
      case "logged":
        return <Badge className="bg-green-100 text-green-800">Logged</Badge>;
      case "pending":
        return <Badge className="bg-yellow-100 text-yellow-800">Pending</Badge>;
      case "skipped":
        return <Badge variant="secondary">Skipped</Badge>;
      default:
        return null;
    }
  };

  const getAdherenceColor = (rate: number) => {
    if (rate >= 90) return "text-green-600";
    if (rate >= 70) return "text-yellow-600";
    return "text-red-600";
  };

  const getAdherenceIcon = (rate: number) => {
    if (rate >= 70) {
      return <TrendingUp className="h-4 w-4 text-green-600" />;
    }
    return <TrendingDown className="h-4 w-4 text-red-600" />;
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-48" />
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 sm:grid-cols-4">
              {[1, 2, 3, 4].map((i) => (
                <Skeleton key={i} className="h-24" />
              ))}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>
          Failed to load meal history. Please try again.
        </AlertDescription>
      </Alert>
    );
  }

  if (!historyData) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">No history data available</p>
      </div>
    );
  }

  const stats = historyData.statistics;

  return (
    <div className="space-y-6">
      {/* Date Range Selector */}
      <div className="flex items-center gap-4">
        <span className="text-sm font-medium">Time Period:</span>
        <Select
          value={days.toString()}
          onValueChange={(value) => setDays(parseInt(value))}
        >
          <SelectTrigger className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="7">Last 7 Days</SelectItem>
            <SelectItem value="14">Last 14 Days</SelectItem>
            <SelectItem value="30">Last 30 Days</SelectItem>
            <SelectItem value="90">Last 90 Days</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Statistics Cards */}
      <Card>
        <CardHeader>
          <CardTitle>Statistics</CardTitle>
          <p className="text-sm text-muted-foreground">
            {new Date(historyData.period.start_date).toLocaleDateString()} -{" "}
            {new Date(historyData.period.end_date).toLocaleDateString()}
          </p>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {/* Total Meals */}
            <div className="p-4 rounded-lg bg-accent">
              <div className="text-sm text-muted-foreground mb-1">
                Total Meals
              </div>
              <div className="text-2xl font-bold">{stats.total_meals}</div>
            </div>

            {/* Logged Meals */}
            <div className="p-4 rounded-lg bg-green-50">
              <div className="text-sm text-muted-foreground mb-1">
                Logged Meals
              </div>
              <div className="text-2xl font-bold text-green-700">
                {stats.logged_meals}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                {((stats.logged_meals / stats.total_meals) * 100).toFixed(0)}%
                of total
              </div>
            </div>

            {/* Skipped Meals */}
            <div className="p-4 rounded-lg bg-yellow-50">
              <div className="text-sm text-muted-foreground mb-1">
                Skipped Meals
              </div>
              <div className="text-2xl font-bold text-yellow-700">
                {stats.skipped_meals}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                {((stats.skipped_meals / stats.total_meals) * 100).toFixed(0)}%
                of total
              </div>
            </div>

            {/* Adherence Rate */}
            <div className="p-4 rounded-lg bg-primary/5">
              <div className="text-sm text-muted-foreground mb-1 flex items-center gap-2">
                Adherence Rate
                {getAdherenceIcon(stats.adherence_rate)}
              </div>
              <div
                className={`text-2xl font-bold ${getAdherenceColor(
                  stats.adherence_rate
                )}`}
              >
                {Math.round(stats.adherence_rate)}%
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                {stats.adherence_rate >= 90
                  ? "Excellent!"
                  : stats.adherence_rate >= 70
                  ? "Good job!"
                  : "Needs improvement"}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Daily History */}
      <div className="space-y-3">
        <h3 className="text-lg font-semibold">Daily History</h3>

        {historyData.history.map((day) => {
          const isExpanded = expandedDays.has(day.date);
          const loggedCount = day.meals.filter((m) => m.status === "logged")
            .length;
          const totalCount = day.meals.length;
          const dayAdherence =
            totalCount > 0 ? (loggedCount / totalCount) * 100 : 0;

          return (
            <Card key={day.date} className="overflow-hidden">
              <button
                onClick={() => toggleDay(day.date)}
                className="w-full text-left hover:bg-accent/50 transition-colors"
              >
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-semibold">
                        {new Date(day.date).toLocaleDateString("en-US", {
                          weekday: "long",
                          month: "long",
                          day: "numeric",
                        })}
                      </h4>
                      <p className="text-sm text-muted-foreground">
                        {loggedCount} / {totalCount} meals logged (
                        {Math.round(dayAdherence)}%)
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={dayAdherence >= 75 ? "default" : "secondary"}
                        className={
                          dayAdherence >= 75
                            ? "bg-green-100 text-green-800"
                            : ""
                        }
                      >
                        {Math.round(dayAdherence)}%
                      </Badge>
                      {isExpanded ? (
                        <ChevronUp className="h-5 w-5 text-muted-foreground" />
                      ) : (
                        <ChevronDown className="h-5 w-5 text-muted-foreground" />
                      )}
                    </div>
                  </div>
                </CardHeader>
              </button>

              {isExpanded && (
                <CardContent className="border-t pt-4">
                  <div className="space-y-3">
                    {day.meals.map((meal, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between p-3 rounded-lg bg-accent/30"
                      >
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-medium capitalize">
                              {meal.meal_type}
                            </span>
                            {getMealStatusBadge(meal.status)}
                          </div>
                          <p className="text-sm text-muted-foreground">
                            {meal.recipe_name}
                          </p>
                        </div>
                        {meal.time && meal.status === "logged" && (
                          <div className="text-sm text-muted-foreground">
                            {meal.time}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </CardContent>
              )}
            </Card>
          );
        })}
      </div>

      {historyData.history.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">
              No meal history found for the selected period
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}