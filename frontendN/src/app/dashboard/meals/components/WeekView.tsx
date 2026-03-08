"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Apple,
  ArrowLeft,
  Circle,
  Coffee,
  RefreshCw,
  Download,
  ShoppingCart,
  CheckCircle2,
  ChevronRight,
  Soup,
  UtensilsCrossed,
  X,
} from "lucide-react";
import { api, getEndpoint } from "@/lib/api";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import SwapMealDialog from "./SwapMealDialog";

// ── Types (unchanged) ──────────────────────────────────────────────────────

interface Macros { calories: number; protein_g: number; carbs_g: number; fat_g: number; }
interface Meal { meal_type: string; recipe_id: number; recipe_name: string; macros: Macros; status: "logged" | "pending" | "skipped" | "missed"; }
interface DayPlan { date: string; day_name: string; meals: Meal[]; }
interface WeekPlan { id: number; has_plan: boolean; week_start: string; week_end: string; days: DayPlan[]; message?: string; }
interface BackendPlanMeal { id: number; title: string; macros_per_serving: Macros; status?: "logged" | "pending" | "skipped" | "missed"; }
interface BackendDayData { meals: Record<string, BackendPlanMeal>; }
interface BackendWeekPlanResponse { id?: number; has_plan?: boolean; week_start_date?: string; plan_data?: Record<string, BackendDayData>; message?: string; }
interface GroceryListItem { item_name: string; to_buy: number; }
interface GroceryListResponse { categorized?: Record<string, GroceryListItem[]>; }
interface RecipeDetails {
  id: number; title: string; description?: string; servings: number; prep_time_min?: number;
  cook_time_min?: number; difficulty_level?: string; cuisine?: string; dietary_tags?: string[];
  suitable_meal_times?: string[]; goals?: string[];
  macros_per_serving: { calories: number; protein_g: number; carbs_g: number; fat_g: number };
  ingredients?: Array<{ item_name: string; quantity_grams: number; preparation_notes?: string }>;
  instructions?: string[];
}
type ApiErrorLike = { response?: { data?: { detail?: string } } };

// ── Constants (unchanged) ──────────────────────────────────────────────────

const GENERATION_STEPS = [
  "Matching your calorie target",
  "Optimizing protein distribution",
  "Rotating cuisines for variety",
  "Respecting your prep time",
  "Aligning with your preferences",
];
const FIRST_PLAN_TOOLTIP_KEY = "nutrilens:meals:first-plan-tooltip-seen";
const TOTAL_GENERATION_STEPS = GENERATION_STEPS.length;

// ── Helpers (unchanged) ────────────────────────────────────────────────────

const mealTypeIcon = (mealType: string, size = "h-[12px] w-[12px]") => {
  switch (mealType.toLowerCase()) {
    case "breakfast": return <Coffee className={size} aria-hidden />;
    case "lunch": return <UtensilsCrossed className={size} aria-hidden />;
    case "snack": return <Apple className={size} aria-hidden />;
    case "dinner": return <Soup className={size} aria-hidden />;
    default: return <Circle className={size} aria-hidden />;
  }
};

const isToday = (dateIso: string): boolean => {
  const v = new Date(dateIso); if (Number.isNaN(v.getTime())) return false;
  const n = new Date(); return v.getFullYear() === n.getFullYear() && v.getMonth() === n.getMonth() && v.getDate() === n.getDate();
};

const isPastDay = (dateIso: string): boolean => {
  const v = new Date(dateIso); if (Number.isNaN(v.getTime())) return false;
  const t = new Date(); t.setHours(0, 0, 0, 0); v.setHours(0, 0, 0, 0); return v < t;
};

const formatTagLabel = (value: string): string =>
  value.replace(/_/g, " ").replace(/\s+/g, " ").trim().replace(/\b\w/g, (m) => m.toUpperCase());

// ── Status helpers ─────────────────────────────────────────────────────────

const getStatusStrip = (status: string) => {
  switch (status) {
    case "logged": return "bg-emerald-400";
    case "pending": return "bg-amber-300";
    case "skipped": return "bg-slate-300";
    case "missed": return "bg-red-300";
    default: return "bg-slate-200";
  }
};

const getStatusChip = (status: string) => {
  const styles: Record<string, { bg: string; text: string; dot: string }> = {
    logged: { bg: "bg-emerald-50", text: "text-emerald-700", dot: "bg-emerald-500" },
    pending: { bg: "bg-amber-50", text: "text-amber-700", dot: "bg-amber-400" },
    missed: { bg: "bg-red-50", text: "text-red-600", dot: "bg-red-400" },
    skipped: { bg: "bg-slate-50", text: "text-slate-500", dot: "bg-slate-400" },
  };
  const s = styles[status] || styles.pending;
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-lg px-2 py-0.5 text-[10px] font-semibold", s.bg, s.text)}>
      <span className={cn("h-1.5 w-1.5 rounded-full", s.dot)} />
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
};

// ── Component ──────────────────────────────────────────────────────────────

export function WeekView() {
  const queryClient = useQueryClient();
  const [selectedMeal, setSelectedMeal] = useState<{ day: number; meal: Meal } | null>(null);
  const [mealToSwap, setMealToSwap] = useState<{ day: number; meal: Meal } | null>(null);
  const [isRecipeExpanded, setIsRecipeExpanded] = useState(false);
  const [expandedRecipe, setExpandedRecipe] = useState<RecipeDetails | null>(null);
  const [expandedRecipeLoading, setExpandedRecipeLoading] = useState(false);
  const [expandedRecipeError, setExpandedRecipeError] = useState<string | null>(null);
  const [showGroceryList, setShowGroceryList] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [generationStepCount, setGenerationStepCount] = useState(0);
  const [generationProgress, setGenerationProgress] = useState(0);
  const [generationReady, setGenerationReady] = useState(false);
  const [generationFinalizing, setGenerationFinalizing] = useState(false);
  const [planRevealVisible, setPlanRevealVisible] = useState(false);
  const [highlightFirstMealCard, setHighlightFirstMealCard] = useState(false);
  const [showFirstPlanTooltip, setShowFirstPlanTooltip] = useState(false);
  const [collapsedDays, setCollapsedDays] = useState<Record<string, boolean>>({});
  const timersRef = useRef<number[]>([]);
  const finalizeStartedRef = useRef(false);

  // ── Queries (unchanged) ──────────────────────────────────────────────

  const { data: weekPlan, isLoading, error } = useQuery<WeekPlan>({
    queryKey: ["meal-plan", "current"],
    queryFn: async () => {
      const response = await api.get(getEndpoint("/meal-plans/current/with-status"));
      const data = response.data as BackendWeekPlanResponse;
      const hasPlanFromFlag = typeof data.has_plan === "boolean" ? data.has_plan : undefined;
      const dayEntries = Object.entries(data.plan_data ?? {}).filter(([k]) => k.startsWith("day_"));
      const hasAtLeastOneMeal = dayEntries.some(([, d]) => Object.values(d?.meals ?? {}).some((m) => !!m && typeof m === "object"));
      const hasRenderablePlan = (hasPlanFromFlag ?? true) && dayEntries.length > 0 && hasAtLeastOneMeal;
      if (!hasRenderablePlan) {
        return { id: data.id || 0, has_plan: false, week_start: data.week_start_date || new Date().toISOString(), week_end: "", days: [], message: data.message || "No meal plan found for this week." };
      }
      const days: DayPlan[] = [];
      const weekStartDate = new Date(data.week_start_date ?? new Date().toISOString());
      for (const [dayName, dayData] of Object.entries(data.plan_data ?? {})) {
        const dayIndex = parseInt(dayName.split("_")[1], 10);
        if (!Number.isFinite(dayIndex)) continue;
        const dayDate = new Date(weekStartDate);
        dayDate.setDate(weekStartDate.getDate() + dayIndex);
        const mealsArray = Object.entries(dayData.meals ?? {}).filter(([, m]) => !!m && typeof m === "object").map(([mt, m]) => ({
          meal_type: mt, recipe_id: m.id, recipe_name: m.title, macros: m.macros_per_serving, status: m.status || "pending",
        }));
        if (mealsArray.length === 0) continue;
        days.push({ date: dayDate.toISOString(), day_name: dayDate.toLocaleDateString("en-US", { weekday: "long" }), meals: mealsArray });
      }
      return { id: data.id ?? 0, has_plan: days.length > 0, week_start: data.week_start_date ?? new Date().toISOString(), week_end: "", days, message: days.length > 0 ? undefined : "No meal plan found for this week." };
    },
    staleTime: 5 * 60 * 1000,
  });

  const { data: groceryList } = useQuery<GroceryListResponse | null>({
    queryKey: ["meal-plan", weekPlan?.id, "grocery-list"],
    queryFn: async () => { if (!weekPlan?.id) return null; return (await api.get(getEndpoint(`/meal-plans/${weekPlan.id}/grocery-list`))).data; },
    enabled: !!weekPlan?.id && weekPlan?.has_plan,
  });

  // ── Mutations (unchanged) ────────────────────────────────────────────

  const regenerateMutation = useMutation({
    mutationFn: async () => (await api.post(getEndpoint("/meal-plans/generate"), { start_date: new Date().toISOString(), days: 7, preferences: {}, use_inventory: true })).data,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["meal-plan"] }); setGenerationReady(true); },
    onError: (error: unknown) => {
      const detail = (error as ApiErrorLike)?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : "Failed to generate meal plan");
      finalizeStartedRef.current = false; setIsRegenerating(false); setGenerationReady(false); setGenerationProgress(0); setGenerationStepCount(0); setGenerationFinalizing(false);
    },
  });

  // ── Callbacks & Effects (unchanged) ──────────────────────────────────

  const dismissFirstPlanTooltip = useCallback(() => {
    if (typeof window !== "undefined") window.localStorage.setItem(FIRST_PLAN_TOOLTIP_KEY, "1");
    setShowFirstPlanTooltip(false);
  }, []);

  const triggerPlanReveal = useCallback((fromGeneration: boolean) => {
    setPlanRevealVisible(false);
    window.requestAnimationFrame(() => setPlanRevealVisible(true));
    if (!fromGeneration) return;
    setHighlightFirstMealCard(true);
    const t = window.setTimeout(() => setHighlightFirstMealCard(false), 1000);
    timersRef.current.push(t);
    if (typeof window !== "undefined" && !window.localStorage.getItem(FIRST_PLAN_TOOLTIP_KEY)) setShowFirstPlanTooltip(true);
  }, []);

  const handleRegenerate = () => {
    finalizeStartedRef.current = false; setIsRegenerating(true); setGenerationReady(false); setGenerationProgress(0);
    setGenerationStepCount(0); setGenerationFinalizing(false); setPlanRevealVisible(false); setHighlightFirstMealCard(false);
    setShowFirstPlanTooltip(false); regenerateMutation.mutate();
  };

  const handleExportPlan = () => {
    if (!weekPlan?.has_plan || !weekPlan.days.length) { toast.error("No active weekly plan to export"); return; }
    const blob = new Blob([JSON.stringify({ exported_at: new Date().toISOString(), week_start: weekPlan.week_start, week_end: weekPlan.week_end, days: weekPlan.days }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = `nutrilens-week-plan-${new Date(weekPlan.week_start).toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a); a.click(); document.body.removeChild(a); URL.revokeObjectURL(url);
    toast.success("Meal plan exported");
  };

  useEffect(() => { return () => { timersRef.current.forEach((t) => window.clearTimeout(t)); timersRef.current = []; }; }, []);

  useEffect(() => {
    if (!isRegenerating || generationStepCount >= TOTAL_GENERATION_STEPS) return;
    const delay = generationReady ? 220 : 500;
    const t = window.setTimeout(() => setGenerationStepCount((p) => Math.min(p + 1, TOTAL_GENERATION_STEPS)), delay);
    timersRef.current.push(t); return () => window.clearTimeout(t);
  }, [generationReady, generationStepCount, isRegenerating]);

  useEffect(() => {
    if (!isRegenerating) return;
    if (generationStepCount >= TOTAL_GENERATION_STEPS) { if (!generationReady) setGenerationProgress(90); return; }
    setGenerationProgress((generationStepCount / TOTAL_GENERATION_STEPS) * 90);
  }, [generationReady, generationStepCount, isRegenerating]);

  useEffect(() => {
    if (!isRegenerating || !generationReady || generationStepCount < TOTAL_GENERATION_STEPS || finalizeStartedRef.current) return;
    finalizeStartedRef.current = true; setGenerationFinalizing(true); setGenerationProgress(100);
    const t = window.setTimeout(() => {
      finalizeStartedRef.current = false; setIsRegenerating(false); setGenerationFinalizing(false);
      triggerPlanReveal(true); toast.success("Your weekly plan is ready.");
    }, 700);
    timersRef.current.push(t); return () => window.clearTimeout(t);
  }, [generationReady, generationStepCount, isRegenerating, triggerPlanReveal]);

  useEffect(() => {
    if (!weekPlan?.has_plan || isRegenerating) { setPlanRevealVisible(false); return; }
    if (!planRevealVisible) window.requestAnimationFrame(() => setPlanRevealVisible(true));
  }, [isRegenerating, planRevealVisible, weekPlan?.has_plan]);

  useEffect(() => {
    if (!showFirstPlanTooltip) return;
    const dismiss = () => dismissFirstPlanTooltip();
    window.addEventListener("pointerdown", dismiss, { once: true, passive: true });
    window.addEventListener("keydown", dismiss, { once: true });
    return () => { window.removeEventListener("pointerdown", dismiss); window.removeEventListener("keydown", dismiss); };
  }, [dismissFirstPlanTooltip, showFirstPlanTooltip]);

  useEffect(() => {
    if (!weekPlan?.days?.length) return;
    setCollapsedDays((prev) => {
      const next: Record<string, boolean> = {};
      for (const day of weekPlan.days) next[day.date] = Object.prototype.hasOwnProperty.call(prev, day.date) ? prev[day.date] : isPastDay(day.date);
      return next;
    });
  }, [weekPlan?.days]);

  useEffect(() => { if (!selectedMeal) { setIsRecipeExpanded(false); setExpandedRecipe(null); setExpandedRecipeError(null); setExpandedRecipeLoading(false); } }, [selectedMeal]);

  useEffect(() => {
    if (!isRecipeExpanded || !selectedMeal?.meal.recipe_id) return;
    let cancelled = false; setExpandedRecipeLoading(true); setExpandedRecipeError(null);
    api.get(getEndpoint(`/recipes/${selectedMeal.meal.recipe_id}`))
      .then((r) => { if (!cancelled) setExpandedRecipe(r.data as RecipeDetails); })
      .catch((err: unknown) => { if (!cancelled) setExpandedRecipeError(typeof (err as ApiErrorLike)?.response?.data?.detail === "string" ? (err as ApiErrorLike).response!.data!.detail! : "Failed to load recipe details"); })
      .finally(() => { if (!cancelled) setExpandedRecipeLoading(false); });
    return () => { cancelled = true; };
  }, [isRecipeExpanded, selectedMeal?.meal.recipe_id]);

  // ── Loading / Error states ───────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex gap-3">
          <Skeleton className="h-10 w-40 rounded-lg" />
          <Skeleton className="h-10 w-32 rounded-lg" />
          <Skeleton className="h-10 w-48 rounded-lg" />
        </div>
        {[1, 2, 3].map((i) => <Skeleton key={i} className="h-48 rounded-2xl" />)}
      </div>
    );
  }

  if (error) {
    return <Alert variant="destructive"><AlertDescription>Failed to load meal plan. Please try again.</AlertDescription></Alert>;
  }

  // ── Empty state ──────────────────────────────────────────────────────

  if (!weekPlan?.has_plan) {
    return (
      <div className="space-y-6">
        <div className="rounded-2xl border border-emerald-200/60 bg-gradient-to-br from-emerald-50/80 via-white to-amber-50/40 py-14">
          <div className="mx-auto max-w-md space-y-4 text-center">
            <h3
              className="text-[24px] font-medium tracking-[-0.02em] text-slate-900"
              style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
            >
              Let&apos;s build your week.
            </h3>
            <p className="text-[14px] text-slate-500">Your targets are ready. Now we&apos;ll design meals around them.</p>
            <Button
              onClick={handleRegenerate} disabled={isRegenerating} size="lg"
              className="min-w-64 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-[0_4px_16px_rgba(27,125,90,0.25)] hover:from-emerald-500 hover:to-teal-500 hover:shadow-[0_6px_20px_rgba(27,125,90,0.3)]"
            >
              {isRegenerating ? <><RefreshCw className="mr-2 h-4 w-4 animate-spin" />Designing your week...</> : <><RefreshCw className="mr-2 h-4 w-4" />Generate my weekly meal plan</>}
            </Button>
            <p className="text-[12px] text-slate-400">Takes about 5 seconds.</p>
          </div>
        </div>
        {isRegenerating && <MealGenerationOverlay progress={generationProgress} completedSteps={generationStepCount} waitingForBackend={generationStepCount >= TOTAL_GENERATION_STEPS && !generationReady} finalizing={generationFinalizing} />}
      </div>
    );
  }

  // ── Main plan view ───────────────────────────────────────────────────

  return (
    <div className="space-y-5">
      {isRegenerating && <MealGenerationOverlay progress={generationProgress} completedSteps={generationStepCount} waitingForBackend={generationStepCount >= TOTAL_GENERATION_STEPS && !generationReady} finalizing={generationFinalizing} />}

      {/* ── Action Bar ── */}
      <div className="flex flex-wrap gap-2.5">
        <Button
          onClick={handleRegenerate} disabled={isRegenerating}
          className="rounded-lg bg-gradient-to-r from-emerald-600 to-teal-600 px-5 text-[13px] font-semibold text-white shadow-[0_2px_10px_rgba(27,125,90,0.2)] hover:from-emerald-500 hover:to-teal-500"
        >
          <RefreshCw className={cn("mr-2 h-3.5 w-3.5", isRegenerating && "animate-spin")} />
          {isRegenerating ? "Regenerating..." : "Regenerate plan"}
        </Button>
        <Button variant="outline" onClick={handleExportPlan} className="rounded-lg border-slate-200 text-[13px] font-medium text-slate-600 hover:bg-slate-50">
          <Download className="mr-2 h-3.5 w-3.5" />Export Plan
        </Button>
        <Button variant="outline" onClick={() => setShowGroceryList(true)} disabled={!groceryList} className="rounded-lg border-slate-200 text-[13px] font-medium text-slate-600 hover:bg-slate-50">
          <ShoppingCart className="mr-2 h-3.5 w-3.5" />Grocery List
        </Button>
      </div>

      {/* ── Day Cards ── */}
      <div className={cn("space-y-4 transition-opacity duration-500 ease-out", planRevealVisible ? "opacity-100" : "opacity-0")}>
        {weekPlan.days.map((day, dayIndex) => {
          const isCollapsed = collapsedDays[day.date] ?? isPastDay(day.date);
          const dayLogged = day.meals.filter((m) => m.status === "logged").length;
          const dayMissed = day.meals.filter((m) => m.status === "missed").length;
          const dayPending = day.meals.filter((m) => m.status === "pending").length;
          const summaryParts: string[] = [];
          if (dayMissed > 0) summaryParts.push(`${dayMissed} missed`);
          if (dayLogged > 0) summaryParts.push(`${dayLogged} logged`);
          if (summaryParts.length === 0 && dayPending > 0) summaryParts.push(`${dayPending} upcoming`);

          return (
            <div
              key={day.date}
              className={cn(
                "overflow-hidden rounded-2xl border transition-all duration-400 ease-out",
                isToday(day.date) ? "border-emerald-200/70 bg-white shadow-[0_2px_12px_rgba(27,125,90,0.06)]" : "border-slate-200/80 bg-white shadow-[0_1px_3px_rgba(0,0,0,0.03)]",
                planRevealVisible ? "translate-y-0 opacity-100" : "translate-y-2 opacity-0",
              )}
              style={{ transitionDelay: `${dayIndex * 70}ms` }}
            >
              {/* Day Header */}
              <div className={cn("flex items-center justify-between gap-3 px-5", isCollapsed ? "py-3.5" : "pb-3 pt-4")}>
                <div>
                  <div className="flex items-center gap-2.5">
                    <h3
                      className="text-[17px] font-medium text-slate-900"
                      style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
                    >
                      {day.day_name}
                    </h3>
                    {isToday(day.date) && (
                      <span className="rounded-md bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
                        Today
                      </span>
                    )}
                  </div>
                  <p className="mt-0.5 text-[11.5px] text-slate-400">{summaryParts.join(" · ")}</p>
                </div>
                <div className="flex items-center gap-2.5">
                  <span className="text-[12px] font-medium text-slate-400">
                    {new Date(day.date).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                  </span>
                  <button
                    type="button" aria-expanded={!isCollapsed}
                    onClick={() => setCollapsedDays((p) => ({ ...p, [day.date]: !isCollapsed }))}
                    className="inline-flex h-7 items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 px-2.5 text-[11px] font-semibold text-slate-500 transition-colors hover:border-slate-300 hover:bg-slate-100 hover:text-slate-700"
                  >
                    {isCollapsed ? "Expand" : "Collapse"}
                    <ChevronRight className={cn("h-3 w-3 transition-transform", isCollapsed ? "rotate-0" : "rotate-90")} />
                  </button>
                </div>
              </div>

              {/* Meals Grid */}
              {!isCollapsed && (
                <div className="px-5 pb-5 pt-0">
                  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
                    {day.meals.map((meal, mealIndex) => {
                      const isFirst = dayIndex === 0 && mealIndex === 0;
                      return (
                        <div
                          key={meal.meal_type}
                          className={cn(
                            "group relative cursor-pointer overflow-hidden rounded-xl border border-slate-200/80 bg-white transition-all duration-200 hover:-translate-y-0.5 hover:border-slate-300/70 hover:shadow-[0_8px_24px_rgba(0,0,0,0.06)]",
                            planRevealVisible ? "translate-y-0 opacity-100" : "translate-y-2 opacity-0",
                            isFirst && highlightFirstMealCard ? "ring-2 ring-emerald-300/60 shadow-[0_12px_28px_-16px_rgba(16,185,129,0.5)]" : ""
                          )}
                          style={{ transitionDelay: `${dayIndex * 70 + mealIndex * 40}ms` }}
                          onClick={() => {
                            if (showFirstPlanTooltip) dismissFirstPlanTooltip();
                            setSelectedMeal({ day: dayIndex, meal });
                          }}
                        >
                          {/* Tooltip for first meal */}
                          {isFirst && showFirstPlanTooltip && (
                            <div className="pointer-events-none absolute -top-9 left-2 z-20 rounded-lg border border-emerald-200 bg-white px-3 py-1.5 text-[11px] font-medium text-emerald-700 shadow-sm">
                              Click to log or swap this meal.
                            </div>
                          )}

                          {/* Status strip */}
                          <span className={cn("absolute inset-x-0 top-0 h-[2.5px]", getStatusStrip(meal.status))} />

                          <div className="p-4">
                            {/* Meal type header */}
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <span className="flex h-6 w-6 items-center justify-center rounded-md bg-slate-50 text-slate-500 transition-colors group-hover:bg-emerald-50 group-hover:text-emerald-600">
                                  {mealTypeIcon(meal.meal_type, "h-3 w-3")}
                                </span>
                                <span className="text-[10.5px] font-semibold uppercase tracking-[0.05em] text-slate-400">
                                  {meal.meal_type}
                                </span>
                              </div>
                              <ChevronRight className="h-3.5 w-3.5 text-slate-300 opacity-0 transition-opacity group-hover:opacity-100" />
                            </div>

                            {/* Recipe name */}
                            <h4 className="mt-2.5 line-clamp-2 text-[13.5px] font-semibold leading-[1.35] text-slate-800">
                              {meal.recipe_name}
                            </h4>

                            {/* Macros */}
                            <div className="mt-2 flex flex-wrap gap-x-2 gap-y-0.5 text-[11px] text-slate-400">
                              <span className="font-medium text-slate-500">{Math.round(meal.macros?.calories || 0)} cal</span>
                              <span>P: {Math.round(meal.macros?.protein_g || 0)}g</span>
                              <span>C: {Math.round(meal.macros?.carbs_g || 0)}g</span>
                              <span>F: {Math.round(meal.macros?.fat_g || 0)}g</span>
                            </div>

                            {/* Status */}
                            <div className="mt-3">
                              {getStatusChip(meal.status)}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* ── Grocery List Dialog ── */}
      <Dialog open={showGroceryList} onOpenChange={setShowGroceryList}>
        <DialogContent className="max-h-[80vh] max-w-2xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}>Grocery List</DialogTitle>
            <DialogDescription>Items needed for this week&apos;s meal plan</DialogDescription>
          </DialogHeader>
          {groceryList && (
            <div className="space-y-5">
              {Object.entries(groceryList.categorized || {}).map(([category, items]) => (
                <div key={category}>
                  <h4 className="mb-2 text-[13px] font-semibold capitalize text-slate-700">{category}</h4>
                  <ul className="space-y-1.5">
                    {items.map((item, idx: number) => (
                      <li key={idx} className="flex items-center justify-between text-[13px]">
                        <span className="text-slate-600">{item.item_name}</span>
                        <span className="font-medium text-slate-400">{Math.round(item.to_buy)}g</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* ── Meal Detail Dialog ── */}
      <Dialog open={!!selectedMeal} onOpenChange={(open) => { if (!open) setSelectedMeal(null); }}>
        <DialogContent
          overlayClassName="bg-slate-950/65 backdrop-blur-[2px]"
          showCloseButton={!isRecipeExpanded}
          className={cn(
            "max-h-[90vh] overflow-hidden border-slate-200/90 bg-white shadow-[0_26px_70px_-40px_rgba(15,23,42,0.5)] transition-[max-width] duration-[220ms] ease-out",
            isRecipeExpanded ? "max-w-[760px]" : "max-w-lg"
          )}
        >
          {!isRecipeExpanded ? (
            <>
              <DialogHeader className="space-y-1.5">
                <p className="text-[10.5px] font-semibold uppercase tracking-[0.06em] text-slate-400">Quick Meal</p>
                <DialogTitle
                  className="text-[24px] font-medium leading-[1.2] tracking-[-0.01em] text-slate-900"
                  style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
                >
                  {selectedMeal?.meal.recipe_name}
                </DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <div>
                  <h4 className="mb-2.5 text-[13px] font-semibold text-slate-600">Macros per serving</h4>
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                    {[
                      { label: "Calories", value: Math.round(selectedMeal?.meal.macros?.calories || 0), unit: "" },
                      { label: "Protein", value: Math.round(selectedMeal?.meal.macros?.protein_g || 0), unit: "g" },
                      { label: "Carbs", value: Math.round(selectedMeal?.meal.macros?.carbs_g || 0), unit: "g" },
                      { label: "Fat", value: Math.round(selectedMeal?.meal.macros?.fat_g || 0), unit: "g" },
                    ].map((m) => (
                      <div key={m.label} className="rounded-xl bg-slate-50 px-3 py-2.5 text-center">
                        <div
                          className="text-[20px] font-semibold text-slate-900"
                          style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
                        >
                          {m.value}{m.unit}
                        </div>
                        <div className="mt-0.5 text-[10.5px] text-slate-400">{m.label}</div>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="flex gap-2.5">
                  <Button
                    className="h-10 flex-1 rounded-lg bg-emerald-600 font-semibold text-white shadow-[0_2px_8px_rgba(27,125,90,0.2)] hover:bg-emerald-700"
                    onClick={() => setIsRecipeExpanded(true)}
                  >
                    View Recipe
                  </Button>
                  <Button
                    variant="outline"
                    className="h-10 flex-1 rounded-lg border-slate-200 font-medium text-slate-600 hover:bg-slate-50"
                    onClick={() => { if (!selectedMeal) return; setMealToSwap(selectedMeal); setSelectedMeal(null); }}
                  >
                    Swap Meal
                  </Button>
                </div>
              </div>
            </>
          ) : (
            <div className="flex max-h-[78vh] flex-col">
              <div className="mb-3 flex items-start justify-between gap-4 border-b border-slate-100 pb-3">
                <div className="min-w-0 pr-2">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-400">Full Recipe</p>
                  <h3
                    className="mt-0.5 break-words text-[22px] font-medium leading-[1.2] tracking-[-0.01em] text-slate-900"
                    style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
                  >
                    {expandedRecipe?.title || selectedMeal?.meal.recipe_name}
                  </h3>
                </div>
                <div className="mt-0.5 flex shrink-0 items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 p-0.5">
                  <Button variant="ghost" size="sm" className="h-7 px-2.5 text-slate-600 hover:bg-slate-100" onClick={() => setIsRecipeExpanded(false)}>
                    <ArrowLeft className="mr-1 h-3.5 w-3.5" />Back
                  </Button>
                  <DialogClose asChild>
                    <Button variant="ghost" size="icon" className="h-7 w-7 text-slate-600 hover:bg-slate-100"><X className="h-3.5 w-3.5" /></Button>
                  </DialogClose>
                </div>
              </div>

              <div className="recipe-modal-scroll flex-1 overflow-y-auto overflow-x-hidden pr-2">
                {expandedRecipeLoading ? (
                  <div className="py-10 text-center text-[13px] text-slate-400">Loading recipe details...</div>
                ) : expandedRecipeError ? (
                  <div className="py-10 text-center text-[13px] text-red-500">{expandedRecipeError}</div>
                ) : expandedRecipe ? (
                  <div className="space-y-6 pb-2">
                    <div className="flex flex-wrap gap-1.5">
                      {expandedRecipe.dietary_tags?.map((tag) => (
                        <span key={`diet-${tag}`} className="inline-flex items-center rounded-lg bg-slate-50 px-2.5 py-1 text-[11.5px] font-medium text-slate-600">
                          {formatTagLabel(tag)}
                        </span>
                      ))}
                      {expandedRecipe.difficulty_level && (
                        <span className="inline-flex items-center rounded-lg bg-slate-50 px-2.5 py-1 text-[11.5px] font-medium text-slate-600">{formatTagLabel(expandedRecipe.difficulty_level)}</span>
                      )}
                      {expandedRecipe.cuisine && (
                        <span className="inline-flex items-center rounded-lg bg-slate-50 px-2.5 py-1 text-[11.5px] font-medium text-slate-600">{formatTagLabel(expandedRecipe.cuisine)}</span>
                      )}
                    </div>

                    {expandedRecipe.description && <p className="text-[13.5px] leading-[1.55] text-slate-500">{expandedRecipe.description}</p>}

                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                      {[
                        { label: "Servings", value: expandedRecipe.servings },
                        expandedRecipe.prep_time_min ? { label: "Prep", value: `${expandedRecipe.prep_time_min} min` } : null,
                        expandedRecipe.cook_time_min ? { label: "Cook", value: `${expandedRecipe.cook_time_min} min` } : null,
                      ].filter(Boolean).map((item) => (
                        <div key={item!.label} className="rounded-xl bg-slate-50 px-3.5 py-2.5 text-[13px]">
                          <span className="font-semibold text-slate-700">{item!.label}:</span>{" "}
                          <span className="text-slate-500">{item!.value}</span>
                        </div>
                      ))}
                    </div>

                    <div>
                      <h4 className="mb-2.5 text-[13px] font-semibold text-slate-700">Nutrition (per serving)</h4>
                      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                        {[
                          { label: "Calories", value: Math.round(expandedRecipe.macros_per_serving.calories), unit: "" },
                          { label: "Protein", value: Math.round(expandedRecipe.macros_per_serving.protein_g), unit: "g" },
                          { label: "Carbs", value: Math.round(expandedRecipe.macros_per_serving.carbs_g), unit: "g" },
                          { label: "Fat", value: Math.round(expandedRecipe.macros_per_serving.fat_g), unit: "g" },
                        ].map((m) => (
                          <div key={m.label} className="rounded-xl bg-slate-50 px-3 py-2.5 text-center">
                            <div className="text-[17px] font-semibold text-slate-900" style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}>
                              {m.value}{m.unit}
                            </div>
                            <div className="mt-0.5 text-[10.5px] text-slate-400">{m.label}</div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {expandedRecipe.ingredients?.length ? (
                      <div>
                        <h4 className="mb-2.5 text-[13px] font-semibold text-slate-700">Ingredients</h4>
                        <ul className="space-y-1.5">
                          {expandedRecipe.ingredients.map((ing, idx) => (
                            <li key={`${ing.item_name}-${idx}`} className="flex items-center justify-between gap-3 text-[13px]">
                              <span className="min-w-0 truncate text-slate-600">{ing.item_name}</span>
                              <span className="shrink-0 font-medium text-slate-400">{Math.round(ing.quantity_grams)}g</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}

                    {expandedRecipe.instructions?.length ? (
                      <div>
                        <h4 className="mb-2.5 text-[13px] font-semibold text-slate-700">Steps</h4>
                        <ol className="space-y-2 pl-5 text-[13px] leading-[1.55] text-slate-600">
                          {expandedRecipe.instructions.map((step, idx) => (
                            <li key={`step-${idx}`} className="list-decimal">{step}</li>
                          ))}
                        </ol>
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <SwapMealDialog
        open={!!mealToSwap} onOpenChange={(open) => !open && setMealToSwap(null)}
        planId={weekPlan?.id || 0}
        currentRecipe={mealToSwap ? { id: mealToSwap.meal.recipe_id, title: mealToSwap.meal.recipe_name, macros_per_serving: mealToSwap.meal.macros } : null}
        day={mealToSwap?.day || 0} mealType={mealToSwap?.meal.meal_type || ""}
      />
    </div>
  );
}

// ── Generation Overlay (visual polish only) ────────────────────────────────

function MealGenerationOverlay({ progress, completedSteps, waitingForBackend, finalizing }: {
  progress: number; completedSteps: number; waitingForBackend: boolean; finalizing: boolean;
}) {
  const [entered, setEntered] = useState(false);
  useEffect(() => { const id = window.requestAnimationFrame(() => setEntered(true)); return () => window.cancelAnimationFrame(id); }, []);

  return (
    <div className={cn("fixed inset-0 z-50 bg-slate-950/20 backdrop-blur-[3px] transition-opacity duration-400", entered ? "opacity-100" : "opacity-0")}>
      <div className="flex h-full items-center justify-center px-5">
        <div className={cn(
          "w-full max-w-xl rounded-2xl border border-white/80 bg-white/98 p-7 text-slate-900 shadow-[0_30px_70px_-45px_rgba(15,23,42,0.45)] transition-[opacity,transform] duration-400",
          entered ? "translate-y-0 opacity-100" : "translate-y-5 opacity-0"
        )}>
          <div className="mb-4 flex justify-center">
            <div className="relative flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-700">
              <Soup className="h-6 w-6" />
              <svg className="pointer-events-none absolute -top-6 h-8 w-10" viewBox="0 0 40 26" fill="none" aria-hidden>
                <path d="M8 22 C6 16, 10 12, 8 6" className="stroke-emerald-500/70" strokeWidth="1.6" strokeLinecap="round" style={{ animation: "steam-rise 3s ease-in-out infinite" }} />
                <path d="M20 22 C18 15, 22 11, 20 4" className="stroke-emerald-500/70" strokeWidth="1.6" strokeLinecap="round" style={{ animation: "steam-rise 3s ease-in-out 0.4s infinite" }} />
                <path d="M32 22 C30 16, 34 12, 32 6" className="stroke-emerald-500/70" strokeWidth="1.6" strokeLinecap="round" style={{ animation: "steam-rise 3s ease-in-out 0.8s infinite" }} />
              </svg>
            </div>
          </div>

          <p className="text-center text-[10px] font-semibold uppercase tracking-[0.14em] text-emerald-600/70">Meal Planning Engine</p>
          <h3
            className="mt-2 text-center text-[20px] font-medium tracking-[-0.01em] text-slate-900"
            style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
          >
            Designing your weekly meal plan...
          </h3>
          <p className="mt-1 text-center text-[13px] text-slate-500">Crafting meals that fit your goals, taste, and time.</p>

          <div className="mt-5 space-y-2.5">
            {GENERATION_STEPS.map((step, index) => {
              const isDone = index < completedSteps;
              return (
                <div key={step} className={cn(
                  "flex items-center gap-2.5 rounded-xl border border-slate-100 bg-white px-3.5 py-2.5 transition-all duration-300",
                  isDone ? "translate-y-0 opacity-100" : "translate-y-1 opacity-40"
                )}>
                  <div className={cn(
                    "flex h-5 w-5 items-center justify-center rounded-full transition-all duration-300",
                    isDone ? "bg-emerald-50 text-emerald-600" : "bg-slate-50 text-slate-400"
                  )}>
                    <CheckCircle2 className="h-3 w-3" />
                  </div>
                  <p className="text-[13px] text-slate-600">{step}</p>
                </div>
              );
            })}
          </div>

          <div className="relative mt-6 h-2 overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-500 transition-[width] duration-300 ease-in-out"
              style={{ width: `${Math.max(0, Math.min(100, progress)).toFixed(1)}%` }}
            />
            {waitingForBackend && (
              <div className="pointer-events-none absolute inset-0 overflow-hidden rounded-full">
                <div className="h-full w-1/2 bg-gradient-to-r from-transparent via-white/70 to-transparent" style={{ animation: "progress-shimmer 1.2s ease-in-out infinite" }} />
              </div>
            )}
          </div>
          <p className="mt-2 text-center text-[11px] text-slate-400">
            {finalizing ? "Finalizing your week..." : waitingForBackend ? "Applying final recipe scoring..." : "Curating meals for consistency and variety."}
          </p>
        </div>
      </div>
    </div>
  );
}