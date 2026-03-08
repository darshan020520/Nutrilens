"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Apple,
  Circle,
  Coffee,
  UtensilsCrossed,
  Lightbulb,
  CheckCircle2,
  Sparkles,
  ArrowRight,
  Soup,
  Timer,
} from "lucide-react";
import { api, getEndpoint } from "@/lib/api";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import ExternalMealDialog from "./ExternalMealDialog";

// ── Types (unchanged) ──────────────────────────────────────────────────────

interface ActionResult {
  type: "log" | "skip";
  recipeName: string;
  recommendations: string[];
  remainingCalories?: number;
  adherenceRate?: number;
}

interface MacroGroup {
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g: number;
}

interface MealDetail {
  id: number;
  meal_type: string;
  planned_time: string;
  recipe: string;
  status: "pending" | "logged" | "skipped" | "missed";
  consumed_time?: string;
  recipe_id?: number;
  macros?: MacroGroup;
}

interface TodayData {
  date: string;
  meals_planned: number;
  meals_consumed: number;
  meals_skipped: number;
  total_calories: number;
  total_macros: MacroGroup;
  target_calories: number;
  target_macros: MacroGroup;
  remaining_calories: number;
  remaining_macros: MacroGroup;
  compliance_rate: number;
  meal_details: MealDetail[];
  recommendations?: string[];
}

interface WeekPlanStatus {
  has_plan: boolean;
}

interface RawWeekPlanStatus {
  has_plan?: boolean;
  plan_data?: Record<string, { meals?: Record<string, unknown> }>;
}

type RecommendationEntry = string | { description?: string };

interface MealActionResponse {
  recommendations?: RecommendationEntry[];
  recipe_name?: string;
  remaining_targets?: { calories?: number };
  updated_adherence_rate?: number;
}

type ApiErrorLike = {
  response?: { data?: { detail?: string } };
};

// ── Helpers (unchanged) ────────────────────────────────────────────────────

const toRecommendationStrings = (recommendations?: RecommendationEntry[]): string[] =>
  (recommendations ?? []).reduce<string[]>((acc, rec) => {
    const text = typeof rec === "string" ? rec : rec.description;
    if (typeof text === "string" && text.trim().length > 0) acc.push(text);
    return acc;
  }, []);

const clampPercent = (value: number): number => {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, value));
};

const macroProgress = (current: number, target: number): number => {
  if (!Number.isFinite(current) || !Number.isFinite(target) || target <= 0) return 0;
  return clampPercent((current / target) * 100);
};

const normalizeCompliance = (value: number): number => {
  if (!Number.isFinite(value)) return 0;
  return clampPercent(value <= 1 ? value * 100 : value);
};

const toMealSortTime = (plannedTime?: string): number => {
  if (!plannedTime) return Number.MAX_SAFE_INTEGER;
  const parsed = new Date(plannedTime).getTime();
  return Number.isFinite(parsed) ? parsed : Number.MAX_SAFE_INTEGER;
};

const formatPlannedTime = (plannedTime?: string): string => {
  if (!plannedTime) return "Anytime";
  const parsed = new Date(plannedTime);
  if (Number.isNaN(parsed.getTime())) return "Anytime";
  return parsed.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
};

const splitInsightSentences = (value: string): string[] =>
  value.replace(/\s+/g, " ").trim().split(/(?<=[.!?])\s+/).map((s) => s.trim()).filter((s) => s.length > 0);

const compactInsightLine = (value: string, maxLength = 92): string => {
  const normalized = value.replace(/\s+/g, " ").trim();
  return normalized.length <= maxLength ? normalized : `${normalized.slice(0, maxLength - 1).trimEnd()}\u2026`;
};

// ── Component ──────────────────────────────────────────────────────────────

export function TodayView() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [selectedMeal, setSelectedMeal] = useState<MealDetail | null>(null);
  const [skipDialogOpen, setSkipDialogOpen] = useState(false);
  const [skipReason, setSkipReason] = useState("");
  const [externalMealDialogOpen, setExternalMealDialogOpen] = useState(false);
  const [mealToReplace, setMealToReplace] = useState<MealDetail | null>(null);
  const [actionResult, setActionResult] = useState<ActionResult | null>(null);
  const [animatedCompliance, setAnimatedCompliance] = useState(0);
  const [animatedMacroValues, setAnimatedMacroValues] = useState({ calories: 0, protein_g: 0, carbs_g: 0, fat_g: 0 });
  const [showNice, setShowNice] = useState(false);
  const [niceNonce, setNiceNonce] = useState(0);
  const [showFocusInsightExpanded, setShowFocusInsightExpanded] = useState(false);
  const [ringPulseEpoch, setRingPulseEpoch] = useState<Record<string, number>>({});
  const progressFrameRef = useRef<number | null>(null);
  const animatedComplianceRef = useRef(0);
  const previousMacroCompletionRef = useRef<Record<string, boolean>>({ protein: false, carbs: false, fat: false });
  const animatedMacroValuesRef = useRef({ calories: 0, protein_g: 0, carbs_g: 0, fat_g: 0 });

  // ── Data fetching (unchanged) ────────────────────────────────────────

  const { data: todayData, isLoading, error } = useQuery<TodayData>({
    queryKey: ["tracking", "today"],
    queryFn: async () => (await api.get(getEndpoint("/tracking/today"))).data,
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  });

  const { data: weekPlanStatus } = useQuery<WeekPlanStatus>({
    queryKey: ["meal-plan", "status"],
    queryFn: async () => {
      const data = (await api.get(getEndpoint("/meal-plans/current/with-status"))).data as RawWeekPlanStatus;
      const hasPlanFromFlag = typeof data.has_plan === "boolean" ? data.has_plan : undefined;
      const hasPlanFromPlanData = Object.entries(data.plan_data ?? {})
        .filter(([dayKey]) => dayKey.startsWith("day_"))
        .some(([, dayData]) => Object.values(dayData?.meals ?? {}).some((meal) => !!meal && typeof meal === "object"));
      return { has_plan: hasPlanFromFlag ?? hasPlanFromPlanData };
    },
    staleTime: 60 * 1000,
  });

  // ── Mutations (unchanged) ────────────────────────────────────────────

  const logMealMutation = useMutation({
    mutationFn: async (mealId: number) => {
      const response = await api.post(getEndpoint("/tracking/log-meal"), {
        meal_log_id: mealId, consumed_datetime: new Date().toISOString(), portion_multiplier: 1.0,
      });
      return response.data;
    },
    onSuccess: (data: MealActionResponse) => {
      queryClient.invalidateQueries({ queryKey: ["tracking", "today"] });
      queryClient.invalidateQueries({ queryKey: ["meal-plan"] });
      const recs = toRecommendationStrings(data?.recommendations);
      setActionResult({
        type: "log", recipeName: data?.recipe_name || "Meal", recommendations: recs,
        remainingCalories: data?.remaining_targets?.calories,
      });
      setNiceNonce((prev) => prev + 1);
      setSelectedMeal(null);
    },
    onError: (error: unknown) => {
      const detail = (error as ApiErrorLike)?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : "Failed to log meal");
    },
  });

  const skipMealMutation = useMutation({
    mutationFn: async ({ mealLogId, reason }: { mealLogId: number; reason: string }) => {
      const response = await api.post(getEndpoint("/tracking/skip-meal"), { meal_log_id: mealLogId, skip_reason: reason });
      return response.data;
    },
    onSuccess: (data: MealActionResponse) => {
      queryClient.invalidateQueries({ queryKey: ["tracking", "today"] });
      queryClient.invalidateQueries({ queryKey: ["meal-plan"] });
      const recs = toRecommendationStrings(data?.recommendations);
      setSkipDialogOpen(false);
      setSkipReason("");
      setActionResult({
        type: "skip", recipeName: data?.recipe_name || selectedMeal?.recipe || "Meal",
        recommendations: recs, adherenceRate: data?.updated_adherence_rate,
      });
      setSelectedMeal(null);
    },
    onError: (error: unknown) => {
      const detail = (error as ApiErrorLike)?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : "Failed to skip meal");
    },
  });

  // ── Animation effects (unchanged) ────────────────────────────────────

  useEffect(() => {
    if (!todayData) return;
    const targetCompliance = todayData.meals_planned > 0 ? normalizeCompliance(todayData.compliance_rate) : 0;
    const targetMacros = {
      calories: todayData.total_macros.calories, protein_g: todayData.total_macros.protein_g,
      carbs_g: todayData.total_macros.carbs_g, fat_g: todayData.total_macros.fat_g,
    };
    const startCompliance = animatedComplianceRef.current;
    const startMacros = animatedMacroValuesRef.current;
    const durationMs = 520;
    const startTime = performance.now();
    const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);
    const animate = (now: number) => {
      const progress = Math.min(1, (now - startTime) / durationMs);
      const eased = easeOut(progress);
      const nextCompliance = startCompliance + (targetCompliance - startCompliance) * eased;
      const nextMacros = {
        calories: startMacros.calories + (targetMacros.calories - startMacros.calories) * eased,
        protein_g: startMacros.protein_g + (targetMacros.protein_g - startMacros.protein_g) * eased,
        carbs_g: startMacros.carbs_g + (targetMacros.carbs_g - startMacros.carbs_g) * eased,
        fat_g: startMacros.fat_g + (targetMacros.fat_g - startMacros.fat_g) * eased,
      };
      animatedComplianceRef.current = nextCompliance;
      animatedMacroValuesRef.current = nextMacros;
      setAnimatedCompliance(nextCompliance);
      setAnimatedMacroValues(nextMacros);
      if (progress < 1) progressFrameRef.current = window.requestAnimationFrame(animate);
    };
    if (progressFrameRef.current) window.cancelAnimationFrame(progressFrameRef.current);
    progressFrameRef.current = window.requestAnimationFrame(animate);
    return () => { if (progressFrameRef.current) window.cancelAnimationFrame(progressFrameRef.current); };
  }, [todayData?.total_macros.calories, todayData?.total_macros.protein_g, todayData?.total_macros.carbs_g, todayData?.total_macros.fat_g, todayData?.meals_planned, todayData?.compliance_rate, todayData]);

  useEffect(() => {
    if (niceNonce === 0) return;
    setShowNice(true);
    const id = window.setTimeout(() => setShowNice(false), 800);
    return () => window.clearTimeout(id);
  }, [niceNonce]);

  useEffect(() => { setShowFocusInsightExpanded(false); }, [todayData?.date]);

  useEffect(() => {
    if (!todayData) return;
    const macroChecks = [
      { id: "protein", value: animatedMacroValues.protein_g, target: todayData.target_macros.protein_g },
      { id: "carbs", value: animatedMacroValues.carbs_g, target: todayData.target_macros.carbs_g },
      { id: "fat", value: animatedMacroValues.fat_g, target: todayData.target_macros.fat_g },
    ];
    for (const macro of macroChecks) {
      const nowCompleted = macro.target > 0 && macro.value / macro.target >= 1;
      const wasCompleted = previousMacroCompletionRef.current[macro.id] ?? false;
      if (nowCompleted && !wasCompleted) {
        setRingPulseEpoch((prev) => ({ ...prev, [macro.id]: (prev[macro.id] ?? 0) + 1 }));
      }
      previousMacroCompletionRef.current[macro.id] = nowCompleted;
    }
  }, [todayData, animatedMacroValues.protein_g, animatedMacroValues.carbs_g, animatedMacroValues.fat_g]);

  // ── Handlers (unchanged) ─────────────────────────────────────────────

  const handleLogMeal = (meal: MealDetail) => { logMealMutation.mutate(meal.id); };
  const handleSkipMeal = () => { if (selectedMeal) skipMealMutation.mutate({ mealLogId: selectedMeal.id, reason: skipReason }); };

  const getMealTypeIcon = (mealType: string, className = "h-5 w-5") => {
    switch ((mealType || "").toLowerCase()) {
      case "breakfast": return <Coffee className={className} aria-hidden />;
      case "lunch": return <UtensilsCrossed className={className} aria-hidden />;
      case "snack": return <Apple className={className} aria-hidden />;
      case "dinner": return <Soup className={className} aria-hidden />;
      default: return <Circle className={className} aria-hidden />;
    }
  };

  const getMealStatusMeta = (status: MealDetail["status"]) => {
    switch (status) {
      case "logged": return { label: "Logged", chipClass: "bg-emerald-50 text-emerald-700 border-emerald-200/60", dotClass: "bg-emerald-500" };
      case "pending": return { label: "Pending", chipClass: "bg-amber-50 text-amber-700 border-amber-200/60", dotClass: "bg-amber-400" };
      case "skipped": return { label: "Skipped", chipClass: "bg-slate-50 text-slate-600 border-slate-200/80", dotClass: "bg-slate-400" };
      case "missed": return { label: "Missed", chipClass: "bg-red-50 text-red-600 border-red-200/70", dotClass: "bg-red-400" };
      default: return { label: "Pending", chipClass: "bg-amber-50 text-amber-700 border-amber-200/60", dotClass: "bg-amber-400" };
    }
  };

  const getTimelineNodeState = (meal: MealDetail): "logged" | "pending" | "future" => {
    if (meal.status === "logged") return "logged";
    if (meal.status === "pending") {
      const plannedAt = toMealSortTime(meal.planned_time);
      if (Number.isFinite(plannedAt) && plannedAt <= Date.now()) return "pending";
    }
    return "future";
  };

  // ── Loading / Error / Empty states ───────────────────────────────────

  if (isLoading) {
    return (
      <div className="space-y-5">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-[1.6fr_1fr]">
          <Skeleton className="h-[240px] rounded-2xl" />
          <Skeleton className="h-[240px] rounded-2xl" />
        </div>
        <Skeleton className="h-16 rounded-2xl" />
        <div className="space-y-3 pt-4">
          {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-28 rounded-xl" />)}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Failed to load today&apos;s meals. Please try again.</AlertDescription>
      </Alert>
    );
  }

  if (!todayData) {
    return (
      <div className="py-12 text-center">
        <p className="text-muted-foreground">No data available for today</p>
      </div>
    );
  }

  // ── Derived values ───────────────────────────────────────────────────

  const noPlanYet = todayData.meals_planned === 0 && Array.isArray(todayData.meal_details) && todayData.meal_details.length === 0 && weekPlanStatus?.has_plan === false;
  const timelineMeals = [...todayData.meal_details].sort((a, b) => toMealSortTime(a.planned_time) - toMealSortTime(b.planned_time));
  const pendingMeals = timelineMeals.filter((meal) => meal.status === "pending");
  const nextPendingMeal = pendingMeals[0];

  const macroRingMetrics = [
    { id: "protein", label: "Protein", value: animatedMacroValues.protein_g, target: todayData.target_macros.protein_g, unit: "g", baseColor: "#1B7D5A", trackColor: "rgba(27,125,90,0.12)", radius: 40 },
    { id: "carbs", label: "Carbs", value: animatedMacroValues.carbs_g, target: todayData.target_macros.carbs_g, unit: "g", baseColor: "#5B8DEF", trackColor: "rgba(91,141,239,0.12)", radius: 30 },
    { id: "fat", label: "Fat", value: animatedMacroValues.fat_g, target: todayData.target_macros.fat_g, unit: "g", baseColor: "#E8913A", trackColor: "rgba(232,145,58,0.12)", radius: 20 },
  ];

  const caloriesProgress = macroProgress(animatedMacroValues.calories, todayData.target_macros.calories);
  const caloriesProgressWidth = caloriesProgress <= 0 ? "2px" : `max(2px, ${Math.round(caloriesProgress)}%)`;
  const macroRings = macroRingMetrics.map((macro) => {
    const rawProgress = macro.target > 0 ? (macro.value / macro.target) * 100 : 0;
    const clampedProgress = clampPercent(rawProgress);
    const circumference = 2 * Math.PI * macro.radius;
    return { ...macro, rawProgress, progress: clampedProgress, circumference, dashOffset: circumference - (clampedProgress / 100) * circumference, strokeColor: rawProgress > 100 ? "#F97316" : macro.baseColor };
  });
  const mealFlowProgress = todayData.meals_planned > 0 ? clampPercent((todayData.meals_consumed / todayData.meals_planned) * 100) : 0;

  const todayAiInsights = (todayData.recommendations ?? []).map((i) => (typeof i === "string" ? i.trim() : "")).filter((i) => i.length > 0);
  const fallbackInsightPrimary = nextPendingMeal ? "Logging your next meal keeps your daily nutrition rhythm steady." : "All meals completed today. Your nutrition targets are on track.";
  const fallbackInsightSecondary = nextPendingMeal ? "Consistent logging improves visibility and better meal decisions." : "Great consistency today helps reinforce long-term habits.";
  const aiInsightSentences = todayAiInsights.flatMap(splitInsightSentences);
  const focusInsightPrimary = aiInsightSentences[0] ? compactInsightLine(aiInsightSentences[0], 94) : fallbackInsightPrimary;
  const focusInsightSecondary = aiInsightSentences[1] ? compactInsightLine(aiInsightSentences[1], 110) : fallbackInsightSecondary;

  // ── Render ───────────────────────────────────────────────────────────

  return (
    <div className="space-y-5">

      {/* ── No plan banner ── */}
      {noPlanYet && (
        <div className="flex flex-col gap-4 rounded-2xl border border-emerald-200/50 bg-emerald-50/50 p-5 md:flex-row md:items-center md:justify-between md:p-6">
          <div className="space-y-1">
            <p className="flex items-center gap-2 text-[13.5px] font-semibold text-emerald-800">
              <Sparkles className="h-4 w-4" />No meal plan is active yet
            </p>
            <p className="text-[13px] text-emerald-700/80">
              Generate your weekly plan to unlock today&apos;s execution timeline and recommendations.
            </p>
          </div>
          <Button className="w-full md:w-auto" onClick={() => router.push("/dashboard/meals?tab=week")}>
            Open week planner <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
        </div>
      )}

      {/* ── Hero Split: Next Meal + Today Tracking ── */}
      <section className="grid grid-cols-1 gap-4 md:grid-cols-[1.6fr_1fr] md:items-stretch">

        {/* Next Meal Card */}
        <div className="flex h-full flex-col rounded-2xl border border-slate-200/80 bg-white p-6 shadow-[0_1px_3px_rgba(0,0,0,0.04)] transition-shadow hover:shadow-[0_8px_30px_rgba(0,0,0,0.06)]">
          <p className="text-[12px] font-medium text-slate-400">
            {nextPendingMeal
              ? `Up next · ${nextPendingMeal.meal_type} · ${formatPlannedTime(nextPendingMeal.planned_time)}`
              : "Up next"}
          </p>

          {nextPendingMeal ? (
            <>
              <p
                className="mt-2 text-[22px] font-semibold leading-[1.2] tracking-[-0.015em] text-slate-900"
                style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
              >
                {nextPendingMeal.recipe}
              </p>
              <div className="mt-4 flex flex-wrap items-center gap-2">
                <Button
                  size="sm"
                  className="h-8 rounded-lg bg-emerald-600 px-4 text-[12px] font-semibold shadow-[0_2px_8px_rgba(27,125,90,0.25)] hover:bg-emerald-700 hover:shadow-[0_4px_12px_rgba(27,125,90,0.3)]"
                  onClick={() => handleLogMeal(nextPendingMeal)}
                  disabled={logMealMutation.isPending}
                >
                  Log Meal
                </Button>
                <Button
                  size="sm" variant="outline"
                  className="h-8 rounded-lg border-slate-200 bg-white px-4 text-[12px] font-medium text-slate-600 hover:bg-slate-50"
                  onClick={() => { setMealToReplace(nextPendingMeal); setExternalMealDialogOpen(true); }}
                >
                  External Meal
                </Button>
                <Button
                  size="sm" variant="ghost"
                  className="h-8 px-2 text-[12px] text-slate-400 hover:text-slate-600"
                  onClick={() => { setSelectedMeal(nextPendingMeal); setSkipDialogOpen(true); }}
                >
                  Skip
                </Button>
              </div>
            </>
          ) : (
            <>
              <p className="mt-3 text-[13.5px] text-slate-400">You&apos;re done for today.</p>
              <p
                className="mt-1 text-[18px] font-semibold tracking-tight text-slate-900"
                style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
              >
                Great job staying consistent.
              </p>
            </>
          )}

          {/* AI Insight */}
          <div className="mt-auto pt-5">
            <div className="flex items-start gap-3 rounded-xl bg-slate-50 px-4 py-3.5">
              <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg bg-emerald-50">
                <Lightbulb className="h-3.5 w-3.5 text-emerald-600" />
              </div>
              <div className="min-w-0">
                <p className="text-[10.5px] font-semibold uppercase tracking-[0.06em] text-slate-400">AI Insight</p>
                <p className="mt-1 text-[13px] leading-[1.5] text-slate-600">{focusInsightPrimary}</p>
                {showFocusInsightExpanded && focusInsightSecondary ? (
                  <p className="mt-1 text-[13px] leading-[1.5] text-slate-600">{focusInsightSecondary}</p>
                ) : null}
                {focusInsightSecondary ? (
                  <button
                    type="button"
                    className="mt-1.5 text-[12px] font-semibold text-emerald-600 hover:text-emerald-700"
                    onClick={() => setShowFocusInsightExpanded((p) => !p)}
                  >
                    {showFocusInsightExpanded ? "Show less" : "Read more"}
                  </button>
                ) : null}
              </div>
            </div>
          </div>
        </div>

        {/* Today Tracking Card — Redesigned */}
        <div className="flex h-full flex-col rounded-2xl border border-slate-200/80 bg-white p-6 shadow-[0_1px_3px_rgba(0,0,0,0.04)] transition-shadow hover:shadow-[0_8px_30px_rgba(0,0,0,0.06)]">

          {/* Header with status */}
          <div className="flex items-start justify-between">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-400">Today Tracking</p>
              <p className="mt-0.5 text-[12.5px] text-slate-500">
                {todayData.meals_consumed} of {todayData.meals_planned} meals logged
              </p>
            </div>
            {showNice ? (
              <span className="inline-flex animate-in fade-in-0 zoom-in-95 items-center rounded-lg bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700 duration-200">
                Nice.
              </span>
            ) : null}
          </div>

          {/* ── Calories Hero — the most important number ── */}
          <div className="mt-5 rounded-xl bg-slate-50 px-4 py-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[10.5px] font-semibold uppercase tracking-[0.06em] text-slate-400">Calories</p>
                <p className="mt-1 flex items-baseline gap-1.5">
                  <span
                    className="text-[28px] font-semibold leading-none tracking-tight text-slate-900"
                    style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
                  >
                    {Math.round(animatedMacroValues.calories)}
                  </span>
                  <span className="text-[13px] text-slate-400">/ {Math.round(todayData.target_macros.calories)}</span>
                </p>
              </div>
              {/* Mini compliance ring */}
              <div className="relative h-[56px] w-[56px]">
                <svg className="h-[56px] w-[56px] -rotate-90" viewBox="0 0 56 56">
                  <circle cx="28" cy="28" r="23" stroke="#eeede9" strokeWidth="4" fill="none" />
                  <circle
                    cx="28" cy="28" r="23"
                    stroke="#1B7D5A" strokeWidth="4" strokeLinecap="round" fill="none"
                    strokeDasharray={2 * Math.PI * 23}
                    strokeDashoffset={(2 * Math.PI * 23) * (1 - Math.min(animatedCompliance, 100) / 100)}
                    className="transition-[stroke-dashoffset] duration-[450ms] ease-[cubic-bezier(0.22,1,0.36,1)]"
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span
                    className="text-[13px] font-bold text-slate-900"
                    style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
                  >
                    {Math.round(animatedCompliance)}%
                  </span>
                </div>
              </div>
            </div>
            {/* Calories progress bar */}
            <div className="mt-3 h-[5px] w-full overflow-hidden rounded-full bg-white">
              <div
                className="h-full rounded-full transition-[width] duration-[450ms] ease-[cubic-bezier(0.22,1,0.36,1)]"
                style={{
                  width: caloriesProgressWidth,
                  background: "linear-gradient(90deg, #1B7D5A, #22956B)",
                }}
              />
            </div>
          </div>

          {/* ── Macro Progress Bars ── */}
          <div className="mt-5 space-y-3.5">
            {macroRings.map((macro) => {
              const pct = macro.target > 0 ? Math.min((macro.value / macro.target) * 100, 100) : 0;
              return (
                <div key={macro.id}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="flex items-center gap-2 text-[12px] text-slate-500">
                      <span className="h-2 w-2 rounded-full" style={{ backgroundColor: macro.strokeColor }} />
                      {macro.label}
                    </span>
                    <span className="text-[12px] font-semibold text-slate-700">
                      {Math.round(macro.value)}
                      <span className="font-normal text-slate-400"> / {Math.round(macro.target)}{macro.unit}</span>
                    </span>
                  </div>
                  <div className="h-[5px] w-full overflow-hidden rounded-full bg-slate-100">
                    <div
                      key={`${macro.id}-bar-${ringPulseEpoch[macro.id] ?? 0}`}
                      className={cn(
                        "h-full rounded-full transition-[width] duration-[500ms] ease-[cubic-bezier(0.22,1,0.36,1)]",
                        ringPulseEpoch[macro.id] ? "ring-goal-pulse" : ""
                      )}
                      style={{
                        width: pct <= 0 ? "2px" : `${Math.round(pct)}%`,
                        backgroundColor: macro.rawProgress > 100 ? "#F97316" : macro.baseColor,
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>

          {/* ── Remaining callout ── */}
          <div className="mt-auto pt-4">
            <div className="flex items-center justify-between rounded-lg bg-emerald-50/60 px-3.5 py-2.5">
              <span className="text-[11.5px] font-medium text-emerald-700">Remaining</span>
              <span className="text-[13px] font-bold text-emerald-800">
                {Math.round(todayData.remaining_calories)} cal
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* ── Timeline Stepper ── */}
      {timelineMeals.length > 0 && (
        <div className="rounded-2xl border border-slate-200/80 bg-white px-5 py-4 shadow-[0_1px_3px_rgba(0,0,0,0.03)]">
          <div className="relative">
            {/* Track */}
            <span className="absolute left-3 right-3 top-[14px] h-[3px] rounded-full bg-slate-100" />
            <span
              className="absolute left-3 top-[14px] h-[3px] rounded-full transition-[width] duration-[450ms] ease-[cubic-bezier(0.22,1,0.36,1)]"
              style={{
                width: `calc((100% - 1.5rem) * ${mealFlowProgress / 100})`,
                background: "linear-gradient(90deg, #1B7D5A, #22956B)",
              }}
            />
            <div className="relative grid grid-cols-4 gap-2">
              {timelineMeals.slice(0, 4).map((meal) => {
                const nodeState = getTimelineNodeState(meal);
                return (
                  <div key={meal.id} className="flex flex-col items-center">
                    <span className={cn(
                      "inline-flex h-7 w-7 items-center justify-center rounded-full border-2 text-[10px] font-semibold transition-all duration-300",
                      nodeState === "logged"
                        ? "border-emerald-500 bg-emerald-500 text-white shadow-[0_2px_8px_rgba(27,125,90,0.3)]"
                        : nodeState === "pending"
                          ? "border-emerald-500 bg-white text-emerald-600"
                          : "border-slate-200 bg-slate-50 text-slate-400"
                    )}>
                      {getMealTypeIcon(meal.meal_type, "h-3 w-3")}
                    </span>
                    <p className={cn(
                      "mt-1.5 text-[11px] capitalize",
                      nodeState === "logged" ? "font-semibold text-emerald-700" : "text-slate-400"
                    )}>
                      {meal.meal_type}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* ── Today's Meals List ── */}
      <section className="space-y-4 pt-6">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <h3
              className="text-[19px] font-medium tracking-[-0.01em] text-slate-900"
              style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
            >
              Today&apos;s Meals
            </h3>
            <p className="mt-0.5 text-[13.5px] text-slate-400">Log or adjust meals as your day changes.</p>
          </div>
          <p className="text-[12px] font-medium text-slate-400">
            {todayData.meals_planned} planned · {todayData.meals_consumed} logged
          </p>
        </div>

        {todayData.meal_details.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/50 p-8 text-center">
            <p className="text-[14px] font-medium text-slate-700">No scheduled meals for today yet</p>
            <p className="mt-1 text-[13px] text-slate-400">
              Generate a weekly plan from the Week tab to start logging.
            </p>
            <Button className="mt-4" variant="outline" onClick={() => router.push("/dashboard/meals?tab=week")}>
              Open week planner
            </Button>
          </div>
        ) : (
          <ol className="space-y-3">
            {timelineMeals.map((meal, index) => {
              const mealStatusMeta = getMealStatusMeta(meal.status);
              const nodeState = getTimelineNodeState(meal);
              const isLogged = meal.status === "logged";

              return (
                <li key={meal.id} className="grid grid-cols-[20px_minmax(0,1fr)] gap-4">
                  {/* Timeline dot + line */}
                  <div className="relative flex justify-center">
                    <span className={cn(
                      "mt-[28px] h-3 w-3 rounded-full border-2 transition-colors duration-300",
                      nodeState === "logged"
                        ? "border-emerald-500 bg-emerald-500"
                        : nodeState === "pending"
                          ? "border-emerald-500 bg-white"
                          : "border-slate-200 bg-slate-100"
                    )} />
                    {index < timelineMeals.length - 1 && (
                      <span className="absolute bottom-[-16px] top-[42px] w-[1.5px] bg-slate-150 bg-slate-200/80" />
                    )}
                  </div>

                  {/* Meal Card */}
                  <div className={cn(
                    "group rounded-xl border p-5 transition-all duration-200 hover:-translate-y-0.5",
                    isLogged
                      ? "border-slate-200/70 bg-slate-50/50 hover:shadow-[0_4px_16px_rgba(0,0,0,0.04)]"
                      : "border-slate-200/80 bg-white hover:border-slate-300/70 hover:shadow-[0_6px_20px_rgba(0,0,0,0.06)]"
                  )}>
                    {/* Header row */}
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2.5">
                        <span className={cn(
                          "flex h-8 w-8 items-center justify-center rounded-lg transition-colors",
                          isLogged
                            ? "bg-emerald-50 text-emerald-600"
                            : "bg-slate-50 text-slate-500 group-hover:bg-emerald-50 group-hover:text-emerald-600"
                        )}>
                          {getMealTypeIcon(meal.meal_type, "h-4 w-4")}
                        </span>
                        <h4 className="text-[12px] font-semibold uppercase tracking-[0.06em] text-slate-500">
                          {meal.meal_type}
                        </h4>
                        <span className={cn(
                          "inline-flex items-center gap-1.5 rounded-lg border px-2 py-0.5 text-[10px] font-semibold",
                          mealStatusMeta.chipClass
                        )}>
                          <span className={cn("h-1.5 w-1.5 rounded-full", mealStatusMeta.dotClass)} />
                          {mealStatusMeta.label}
                        </span>
                      </div>
                      <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-slate-400">
                        <Timer className="h-3 w-3" />
                        {formatPlannedTime(meal.planned_time)}
                      </span>
                    </div>

                    {/* Body */}
                    <div className="mt-3 grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-start">
                      <div className="min-w-0">
                        <p className={cn(
                          "text-[16px] font-semibold leading-[1.3] tracking-[-0.01em]",
                          isLogged ? "text-slate-500" : "text-slate-900"
                        )}>
                          {meal.recipe}
                        </p>

                        {meal.status === "pending" && (
                          <div className="mt-3 flex flex-wrap items-center gap-2">
                            <Button
                              size="sm"
                              className="h-8 rounded-lg bg-emerald-600 px-4 text-[12px] font-semibold shadow-[0_2px_8px_rgba(27,125,90,0.2)] hover:bg-emerald-700"
                              onClick={() => handleLogMeal(meal)}
                              disabled={logMealMutation.isPending}
                            >
                              Log Meal
                            </Button>
                            <Button
                              size="sm" variant="outline"
                              className="h-8 rounded-lg border-slate-200 bg-white px-3.5 text-[12px] font-medium text-slate-600 hover:bg-slate-50"
                              onClick={() => { setMealToReplace(meal); setExternalMealDialogOpen(true); }}
                            >
                              <UtensilsCrossed className="mr-1 h-3 w-3" />External Meal
                            </Button>
                            <Button
                              size="sm" variant="ghost"
                              className="h-8 px-2 text-[12px] text-slate-400 hover:text-slate-600"
                              onClick={() => { setSelectedMeal(meal); setSkipDialogOpen(true); }}
                            >
                              Skip
                            </Button>
                          </div>
                        )}

                        {isLogged && meal.consumed_time && (
                          <p className="mt-2 text-[11.5px] text-slate-400">
                            Logged at {new Date(meal.consumed_time).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}
                          </p>
                        )}
                      </div>

                      {/* Macro badges */}
                      <div className="grid w-full max-w-[220px] grid-cols-2 gap-1.5 self-start md:ml-auto md:justify-items-end">
                        {[
                          { label: `${Math.round(meal.macros?.calories || 0)} cal`, accent: true },
                          { label: `P ${Math.round(meal.macros?.protein_g || 0)}g` },
                          { label: `C ${Math.round(meal.macros?.carbs_g || 0)}g` },
                          { label: `F ${Math.round(meal.macros?.fat_g || 0)}g` },
                        ].map((badge) => (
                          <span
                            key={badge.label}
                            className={cn(
                              "inline-flex h-[24px] items-center justify-center rounded-lg px-2.5 text-[11.5px] font-medium",
                              badge.accent
                                ? "bg-slate-100 text-slate-700"
                                : "bg-slate-50 text-slate-500"
                            )}
                          >
                            {badge.label}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </section>

      {/* ── Dialogs (unchanged) ── */}

      <Dialog open={skipDialogOpen} onOpenChange={setSkipDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Skip Meal</DialogTitle>
            <DialogDescription>Are you sure you want to skip {selectedMeal?.meal_type}?</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="skip-reason">Reason (optional)</Label>
              <Textarea id="skip-reason" placeholder="e.g., Not hungry, eating out, etc." value={skipReason} onChange={(e) => setSkipReason(e.target.value)} rows={3} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setSkipDialogOpen(false); setSkipReason(""); }}>Cancel</Button>
            <Button onClick={handleSkipMeal} disabled={skipMealMutation.isPending}>Skip Meal</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ExternalMealDialog
        open={externalMealDialogOpen} onOpenChange={setExternalMealDialogOpen}
        mealLogId={mealToReplace?.id} mealType={mealToReplace?.meal_type}
        onSuccess={() => setMealToReplace(null)}
      />

      <Dialog open={!!actionResult} onOpenChange={(open) => { if (!open) setActionResult(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-emerald-600" />
              {actionResult?.type === "log" ? `${actionResult.recipeName} logged!` : `${actionResult?.recipeName} skipped`}
            </DialogTitle>
            <DialogDescription>
              {actionResult?.type === "log" ? "Your meal has been recorded and inventory updated." : "Meal marked as skipped."}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {actionResult?.type === "log" && actionResult.remainingCalories !== undefined && (
              <div className="flex items-center justify-between rounded-xl bg-slate-50 p-3.5">
                <span className="text-[13px] font-medium text-slate-600">Remaining today</span>
                <span className="text-[18px] font-bold text-emerald-700" style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}>
                  {Math.round(actionResult.remainingCalories)} cal
                </span>
              </div>
            )}
            {actionResult?.type === "skip" && actionResult.adherenceRate !== undefined && (
              <div className="flex items-center justify-between rounded-xl bg-slate-50 p-3.5">
                <span className="text-[13px] font-medium text-slate-600">Weekly adherence</span>
                <span className="text-[18px] font-bold text-emerald-700" style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}>
                  {Math.round(actionResult.adherenceRate * 100)}%
                </span>
              </div>
            )}
            {actionResult?.recommendations && actionResult.recommendations.length > 0 && (
              <div className="space-y-2">
                <h4 className="flex items-center gap-1.5 text-[13px] font-semibold text-slate-700">
                  <Lightbulb className="h-3.5 w-3.5 text-amber-500" />Recommendations
                </h4>
                <ul className="space-y-1.5">
                  {actionResult.recommendations.map((rec, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-[13px] text-slate-500">
                      <span className="mt-0.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-slate-300" />
                      <span>{rec}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button onClick={() => setActionResult(null)}>Done</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}