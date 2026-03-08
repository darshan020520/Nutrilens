"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useIsFetching, useQuery } from "@tanstack/react-query";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Calendar, Clock, Book, History } from "lucide-react";
import { DashboardLayout } from "@/components/layouts/DashboardLayout";
import { api, getEndpoint } from "@/lib/api";
import { cn } from "@/lib/utils";
import { DashboardPageLoader, useInitialPageLoader } from "@/shared/components/states/DashboardPageLoader";

import { WeekView } from "./components/WeekView";
import { TodayView } from "./components/TodayView";
import { RecipeBrowser } from "./components/RecipeBrowser";
import { MealHistory } from "./components/MealHistory";

const allowedTabs = new Set(["week", "today", "recipes", "history"]);
const tabOrder = ["today", "week", "recipes", "history"] as const;

interface TodayHeaderData {
  meals_planned: number;
  meals_consumed: number;
}

function MealsPageContent() {
  const searchParams = useSearchParams();
  const initialTab = useMemo(() => {
    const value = searchParams.get("tab") || "today";
    return allowedTabs.has(value) ? value : "today";
  }, [searchParams]);

  const [activeTab, setActiveTab] = useState(initialTab);
  const [isFetchBootstrapReady, setIsFetchBootstrapReady] = useState(false);
  const { data: todayHeaderData } = useQuery<TodayHeaderData>({
    queryKey: ["tracking", "today"],
    queryFn: async () => (await api.get(getEndpoint("/tracking/today"))).data,
    enabled: activeTab === "today",
    staleTime: 30 * 1000,
  });

  const activeTabFetchCount = useIsFetching({
    predicate: (query) => {
      const key = query.queryKey;
      if (!Array.isArray(key) || key.length === 0) return false;

      const root = String(key[0] ?? "");
      const leaf = String(key[1] ?? "");

      if (activeTab === "today") {
        return (root === "tracking" && leaf === "today") || (root === "meal-plan" && leaf === "status");
      }
      if (activeTab === "week") return root === "meal-plan";
      if (activeTab === "recipes") return root === "recipes" || root === "recipe";
      if (activeTab === "history") return root === "tracking" && leaf === "history";
      return false;
    },
  });
  const hasRegisteredQueriesForActiveTab = useIsFetching({
    predicate: (query) => {
      const key = query.queryKey;
      if (!Array.isArray(key) || key.length === 0) return false;

      const root = String(key[0] ?? "");
      const leaf = String(key[1] ?? "");

      if (activeTab === "today") {
        return (root === "tracking" && leaf === "today") || (root === "meal-plan" && leaf === "status");
      }
      if (activeTab === "week") return root === "meal-plan" && leaf === "current";
      if (activeTab === "recipes") return root === "recipes";
      if (activeTab === "history") return root === "tracking" && leaf === "history";
      return false;
    },
  });

  useEffect(() => {
    if (isFetchBootstrapReady) return;

    if (activeTabFetchCount > 0 || hasRegisteredQueriesForActiveTab > 0) {
      setIsFetchBootstrapReady(true);
      return;
    }

    const timerId = window.setTimeout(() => {
      setIsFetchBootstrapReady(true);
    }, 220);
    return () => window.clearTimeout(timerId);
  }, [activeTabFetchCount, hasRegisteredQueriesForActiveTab, isFetchBootstrapReady]);

  const isMealsReady = isFetchBootstrapReady && activeTabFetchCount === 0;
  const { showLoader: showInitialLoader, isExiting: isLoaderExiting } = useInitialPageLoader(isMealsReady, {
    showDelayMs: 0,
    minVisibleMs: 420,
    exitMs: 200,
  });
  const plannedCount = todayHeaderData?.meals_planned ?? 0;
  const loggedCount = todayHeaderData?.meals_consumed ?? 0;
  const progressLine =
    activeTab === "today" && plannedCount > 0
      ? `${loggedCount} of ${plannedCount} meals logged`
      : "Daily routine, without overthinking meals";
  const motivationLine =
    loggedCount <= 0
      ? "Start your day strong"
      : loggedCount === 1
        ? "Good start today"
        : loggedCount === 2
          ? "Halfway there"
          : loggedCount === 3
            ? "Almost done"
            : "Great job today";
  const subtitleLine =
    activeTab === "today" && plannedCount > 0
      ? `${progressLine} \u00b7 ${motivationLine}`
      : progressLine;
  const activeTabIndex = Math.max(tabOrder.indexOf((activeTab as (typeof tabOrder)[number]) ?? "today"), 0);

  return (
    <DashboardLayout>
      {/* ── Custom styles ── */}
      <style>{`
        @keyframes nl-meals-fade-up {
          from { opacity: 0; transform: translateY(14px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .nl-meals-hero {
          background: linear-gradient(135deg, #14533C 0%, #166534 30%, #1B7D5A 60%, #22956B 100%);
        }
        .nl-meals-dot-pattern {
          background-image:
            radial-gradient(circle at 15% 85%, rgba(255,255,255,0.05) 1px, transparent 1px),
            radial-gradient(circle at 85% 15%, rgba(255,255,255,0.05) 1px, transparent 1px),
            radial-gradient(circle at 50% 50%, rgba(255,255,255,0.025) 1px, transparent 1px);
          background-size: 48px 48px, 48px 48px, 24px 24px;
        }
        .nl-meals-tab-list {
          background: rgba(255,255,255,0.12);
          backdrop-filter: blur(12px);
          -webkit-backdrop-filter: blur(12px);
          border: 1px solid rgba(255,255,255,0.1);
        }
        .nl-meals-tab-indicator {
          background: rgba(255,255,255,0.18);
          box-shadow: 0 1px 3px rgba(0,0,0,0.1), inset 0 1px 0 rgba(255,255,255,0.1);
        }
        .nl-meals-tab {
          color: rgba(255,255,255,0.55);
          transition: color 0.2s ease;
        }
        .nl-meals-tab:hover {
          color: rgba(255,255,255,0.8);
        }
        .nl-meals-tab[data-state="active"] {
          color: #fff !important;
          font-weight: 600;
          background: transparent !important;
          box-shadow: none !important;
        }
        .nl-meals-content {
          animation: nl-meals-fade-up 0.35s ease both;
        }
      `}</style>

      <div className="mx-auto w-full max-w-[1080px] px-4 py-6 md:px-8">
        <div className="relative">
          <div
            className={cn(
              "space-y-5 transition-[opacity,transform] duration-[350ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
              showInitialLoader ? "pointer-events-none translate-y-2 opacity-0" : "translate-y-0 opacity-100"
            )}
          >
            <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">

              {/* ── Hero Banner ── */}
              <div className="nl-meals-hero relative overflow-hidden rounded-[20px]">
                {/* Texture overlays */}
                <div className="nl-meals-dot-pattern pointer-events-none absolute inset-0" />
                <div
                  className="pointer-events-none absolute inset-0"
                  style={{
                    background: "radial-gradient(ellipse 50% 80% at 0% 100%, rgba(34,149,107,0.25), transparent 55%)",
                  }}
                />
                <div
                  className="pointer-events-none absolute inset-0"
                  style={{
                    background: "radial-gradient(ellipse 40% 60% at 100% 0%, rgba(255,255,255,0.04), transparent 50%)",
                  }}
                />

                <div className="relative z-[1] px-7 pb-7 pt-7 md:px-8 md:pt-8">
                  {/* Title + subtitle */}
                  <div className="flex flex-col gap-1.5">
                    <h1
                      className="text-[28px] font-medium leading-[1.15] tracking-[-0.5px] text-white md:text-[32px]"
                      style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
                    >
                      Your meal plan
                    </h1>
                    <p className="text-[13.5px] leading-relaxed" style={{ color: "rgba(255,255,255,0.5)" }}>
                      {subtitleLine}
                    </p>
                  </div>

                  {/* Tab bar — glass morphism on dark bg */}
                  <TabsList className="nl-meals-tab-list relative mt-6 grid h-11 w-full max-w-[680px] grid-cols-4 rounded-xl p-1">
                    {/* Sliding indicator */}
                    <span
                      aria-hidden
                      className="nl-meals-tab-indicator absolute left-1 top-1 h-9 rounded-[10px] transition-transform duration-250 ease-[cubic-bezier(0.4,0,0.2,1)]"
                      style={{
                        width: "calc((100% - 0.5rem) / 4)",
                        transform: `translateX(calc(${activeTabIndex} * 100%))`,
                      }}
                    />
                    <TabsTrigger value="today" className="nl-meals-tab relative z-10 h-9 gap-2 rounded-[10px] px-4 text-[13.5px]">
                      <Clock className="h-[15px] w-[15px]" />
                      <span>Today</span>
                    </TabsTrigger>
                    <TabsTrigger value="week" className="nl-meals-tab relative z-10 h-9 gap-2 rounded-[10px] px-4 text-[13.5px]">
                      <Calendar className="h-[15px] w-[15px]" />
                      <span>This Week</span>
                    </TabsTrigger>
                    <TabsTrigger value="recipes" className="nl-meals-tab relative z-10 h-9 gap-2 rounded-[10px] px-4 text-[13.5px]">
                      <Book className="h-[15px] w-[15px]" />
                      <span>Recipes</span>
                    </TabsTrigger>
                    <TabsTrigger value="history" className="nl-meals-tab relative z-10 h-9 gap-2 rounded-[10px] px-4 text-[13.5px]">
                      <History className="h-[15px] w-[15px]" />
                      <span>History</span>
                    </TabsTrigger>
                  </TabsList>
                </div>
              </div>

              {/* ── Tab Content ── */}
              <TabsContent value="today" className="nl-meals-content mt-0 space-y-4">
                <TodayView />
              </TabsContent>

              <TabsContent value="week" className="nl-meals-content mt-0 space-y-4">
                <WeekView />
              </TabsContent>

              <TabsContent value="recipes" className="nl-meals-content mt-0 space-y-4">
                <RecipeBrowser />
              </TabsContent>

              <TabsContent value="history" className="nl-meals-content mt-0 space-y-4">
                <MealHistory />
              </TabsContent>
            </Tabs>
          </div>

          {showInitialLoader ? (
            <div className={cn("absolute inset-x-0 top-0 z-20 transition-opacity duration-200", isLoaderExiting ? "opacity-0" : "opacity-100")}>
              <DashboardPageLoader scene="meals" isExiting={isLoaderExiting} />
            </div>
          ) : null}
        </div>
      </div>
    </DashboardLayout>
  );
}

function MealsPageFallback() {
  return (
    <DashboardLayout>
      <div className="mx-auto w-full max-w-[1080px] px-4 py-8 md:px-8">
        <DashboardPageLoader scene="meals" />
      </div>
    </DashboardLayout>
  );
}

export default function MealsPage() {
  return (
    <Suspense fallback={<MealsPageFallback />}>
      <MealsPageContent />
    </Suspense>
  );
}