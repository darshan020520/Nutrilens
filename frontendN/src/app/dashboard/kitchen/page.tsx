"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  ChefHat,
  Clock,
  UtensilsCrossed,
  Loader2,
  Sparkles,
  WandSparkles,
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { dashboardClient } from "@/core/api/clients";
import { cn } from "@/lib/utils";
import { DashboardPageLoader, useInitialPageLoader } from "@/shared/components/states/DashboardPageLoader";
import { useAIRecipes, useInventoryItems, useMakeableRecipes } from "../inventory/hooks/useInventory";
import { useExpiringItems } from "../inventory/hooks/useTracking";
import { AIRecipeSuggestion, FilterOptions } from "../inventory/types";

type KitchenMode = "goal_adherent" | "guilt_free";
type KitchenDataState = "loading" | "no-pantry" | "no-recipes" | "has-recipes";
type ModalPhase = "idle" | "staging" | "result" | "error";

type MakeableRecipeItem = {
  recipe_id: number;
  recipe_name: string;
  prep_time_minutes?: number | null;
  available_ingredients: number;
  total_ingredients: number;
  available_ingredient_names?: string[] | null;
  missing_ingredient_names?: string[] | null;
  match_percentage?: number | null;
  macros?: {
    protein_g?: number;
    carbs_g?: number;
    fat_g?: number;
  } | null;
};

type MakeableResponse = {
  fully_makeable: MakeableRecipeItem[];
  partially_makeable: MakeableRecipeItem[];
};

type MacroRemaining = {
  protein: number;
  carbs: number;
  fat: number;
};

const MIN_STAGING_MS = 1500;
const CHECKLIST_STAGGER_MS = 250;
const TYPE_H1 = "text-[36px] leading-[1.14] font-semibold";
const TYPE_H2 = "text-[21px] leading-[1.2] font-semibold";
const TYPE_H3 = "text-[17px] leading-[1.3] font-medium";
const TYPE_BODY = "text-[14px] leading-[1.5]";
const TYPE_META = "text-[12px] leading-[1.35]";

const aiChecklist = [
  "Analyzing available ingredients",
  "Checking macro alignment",
  "Reducing waste risk",
  "Designing preparation flow",
];

function normalizeName(value: string): string {
  return value.trim().toLowerCase();
}

function resolvePrepMinutes(recipe: MakeableRecipeItem): number {
  return typeof recipe.prep_time_minutes === "number" && recipe.prep_time_minutes > 0
    ? recipe.prep_time_minutes
    : 20;
}

function resolveMatchPercentage(recipe: MakeableRecipeItem): number {
  if (typeof recipe.match_percentage === "number" && Number.isFinite(recipe.match_percentage)) {
    return Math.max(0, Math.min(100, Math.round(recipe.match_percentage)));
  }
  if (recipe.total_ingredients > 0) {
    return Math.max(0, Math.min(100, Math.round((recipe.available_ingredients / recipe.total_ingredients) * 100)));
  }
  return 0;
}

function recipeMatchesFilter(recipe: MakeableRecipeItem, filter: string): boolean {
  if (!filter) return true;
  const haystack = [
    recipe.recipe_name,
    ...(recipe.available_ingredient_names ?? []),
    ...(recipe.missing_ingredient_names ?? []),
  ]
    .join(" ")
    .toLowerCase();
  return haystack.includes(filter);
}

export default function KitchenPage() {
  const searchParams = useSearchParams();
  const ingredientFilter = normalizeName(searchParams.get("ingredient") ?? "");

  const [heroVisible, setHeroVisible] = useState(false);
  const [barsMounted, setBarsMounted] = useState(false);
  const [revealedHeadings, setRevealedHeadings] = useState<Record<string, boolean>>({});
  const [forceReveal, setForceReveal] = useState(false);
  const [visibleReadyBars, setVisibleReadyBars] = useState<Record<number, boolean>>({});
  const [showAllReady, setShowAllReady] = useState(false);

  const [mode, setMode] = useState<KitchenMode>("goal_adherent");
  const [modalOpen, setModalOpen] = useState(false);
  const [modalPhase, setModalPhase] = useState<ModalPhase>("idle");
  const [visibleChecklistCount, setVisibleChecklistCount] = useState(0);
  const [stagingProgress, setStagingProgress] = useState(0);
  const [stagingInsightIndex, setStagingInsightIndex] = useState(0);
  const [generatedRecipe, setGeneratedRecipe] = useState<AIRecipeSuggestion | null>(null);
  const [generationError, setGenerationError] = useState<string | null>(null);
  const [resultVisible, setResultVisible] = useState(false);

  const checklistTimersRef = useRef<number[]>([]);
  const progressRafRef = useRef<number | null>(null);
  const generationRunRef = useRef(0);

  const filters: FilterOptions = { lowStockOnly: false, expiringSoon: false };

  const { data: pantryData, isLoading: pantryLoading, error: pantryError } = useInventoryItems(filters);
  const { data: makeableDataRaw, isLoading: recipesLoading, error: recipesError } = useMakeableRecipes(24);
  const { data: expiringData } = useExpiringItems(3);
  const aiRecipesMutation = useAIRecipes();

  const { data: summary } = useQuery({
    queryKey: ["dashboard-summary", "kitchen"],
    queryFn: async () => dashboardClient.getSummary(),
    staleTime: 60 * 1000,
  });

  const pantryItems = useMemo(() => pantryData?.items ?? [], [pantryData?.items]);
  const pantryCount = pantryData?.count ?? pantryItems.length;

  const makeableData: MakeableResponse = useMemo(() => {
    const raw = (makeableDataRaw ?? {}) as Partial<MakeableResponse>;
    return {
      fully_makeable: Array.isArray(raw.fully_makeable) ? raw.fully_makeable : [],
      partially_makeable: Array.isArray(raw.partially_makeable) ? raw.partially_makeable : [],
    };
  }, [makeableDataRaw]);

  const expiringNameSet = useMemo(() => {
    const names = (expiringData?.items ?? []).map((item) => normalizeName(item.item_name));
    return new Set(names);
  }, [expiringData?.items]);

  const readyRecipes = useMemo(
    () => makeableData.fully_makeable.filter((recipe) => recipeMatchesFilter(recipe, ingredientFilter)),
    [makeableData.fully_makeable, ingredientFilter]
  );

  const almostRecipes = useMemo(
    () => makeableData.partially_makeable.filter((recipe) => recipeMatchesFilter(recipe, ingredientFilter)),
    [ingredientFilter, makeableData.partially_makeable]
  );

  const macroRemaining: MacroRemaining | null = useMemo(() => {
    const macros = summary?.macros_card;
    if (!macros) return null;
    return {
      protein: Math.max(0, (macros.protein_target ?? 0) - (macros.protein_consumed ?? 0)),
      carbs: Math.max(0, (macros.carbs_target ?? 0) - (macros.carbs_consumed ?? 0)),
      fat: Math.max(0, (macros.fat_target ?? 0) - (macros.fat_consumed ?? 0)),
    };
  }, [summary?.macros_card]);

  const kitchenState: KitchenDataState = useMemo(() => {
    if (pantryLoading || recipesLoading) return "loading";
    if (pantryCount === 0) return "no-pantry";
    if (readyRecipes.length === 0 && almostRecipes.length === 0) return "no-recipes";
    return "has-recipes";
  }, [almostRecipes.length, pantryCount, pantryLoading, readyRecipes.length, recipesLoading]);

  const { showLoader: showInitialLoader, isExiting: isLoaderExiting } = useInitialPageLoader(kitchenState !== "loading", {
    showDelayMs: 0,
    minVisibleMs: 560,
    exitMs: 200,
  });

  const pantryNameSet = useMemo(() => {
    return new Set(pantryItems.map((item) => normalizeName(item.item_name)));
  }, [pantryItems]);

  const generatedUsesCount = useMemo(() => {
    if (!generatedRecipe) return 0;
    return (generatedRecipe.ingredients ?? []).reduce((count, ingredient) => {
      return pantryNameSet.has(normalizeName(ingredient.name)) ? count + 1 : count;
    }, 0);
  }, [generatedRecipe, pantryNameSet]);

  const generatedOptionalBadges = useMemo(() => {
    if (!generatedRecipe) return [];
    const badges: string[] = [];
    const usesExpiring = (generatedRecipe.ingredients ?? []).some((ingredient) =>
      expiringNameSet.has(normalizeName(ingredient.name))
    );
    if (usesExpiring) badges.push("Reduces waste");
    if ((generatedRecipe.estimated_protein_g ?? 0) >= 30) badges.push("High protein");
    if ((generatedRecipe.estimated_prep_time_min ?? 0) <= 20) badges.push("Quick prep");
    return badges;
  }, [expiringNameSet, generatedRecipe]);

  const proteinOptimizedCount = useMemo(() => {
    const target = Math.max(20, Math.min(40, (macroRemaining?.protein ?? 0) * 0.6));
    return readyRecipes.filter((recipe) => (recipe.macros?.protein_g ?? 0) >= target).length;
  }, [macroRemaining?.protein, readyRecipes]);

  const expiringCandidate = useMemo(() => {
    for (const recipe of readyRecipes) {
      const match = (recipe.available_ingredient_names ?? []).find((name) => expiringNameSet.has(normalizeName(name)));
      if (match) return { recipe, ingredient: match };
    }
    return null;
  }, [expiringNameSet, readyRecipes]);

  const proteinQuickCandidate = useMemo(() => {
    return [...readyRecipes]
      .filter((recipe) => (recipe.macros?.protein_g ?? 0) >= 25)
      .sort((a, b) => {
        const prepDelta = resolvePrepMinutes(a) - resolvePrepMinutes(b);
        if (prepDelta !== 0) return prepDelta;
        return (b.macros?.protein_g ?? 0) - (a.macros?.protein_g ?? 0);
      })[0] ?? null;
  }, [readyRecipes]);

  const headingClassName = useCallback(
    (id: string) =>
      cn(
        "transition-[opacity,transform] duration-300",
        revealedHeadings[id] || forceReveal ? "translate-y-0 opacity-100" : "translate-y-3 opacity-0"
      ),
    [forceReveal, revealedHeadings]
  );

  const modeInsight = mode === "goal_adherent"
    ? `Targeting ~${Math.max(25, Math.round((macroRemaining?.protein ?? 80) * 0.45))}g protein.`
    : "Prioritizing simplicity and low prep effort.";

  const visibleReadyRecipes = useMemo(() => {
    if (showAllReady) return readyRecipes;
    return readyRecipes.slice(0, 4);
  }, [readyRecipes, showAllReady]);

  const stagingInsights = useMemo(() => {
    const primaryPantry = pantryItems[0];
    const secondaryPantry = pantryItems[1];
    const expiring = expiringData?.items?.[0];
    return [
      primaryPantry
        ? `Using ${Math.round(primaryPantry.quantity_grams)}g ${primaryPantry.item_name.toLowerCase()}`
        : "Using your pantry ingredients",
      secondaryPantry
        ? `Balancing carbs with ${secondaryPantry.item_name.toLowerCase()}`
        : "Balancing macros intelligently",
      expiring
        ? `Avoiding waste from ${expiring.item_name.toLowerCase()}`
        : "Reducing waste risk",
      "Optimizing prep flow",
    ];
  }, [expiringData?.items, pantryItems]);

  const heroTitle = useMemo(() => {
    if (kitchenState === "no-recipes") return "You are one ingredient away from something great.";
    if (expiringCandidate?.ingredient) return `Use your ${expiringCandidate.ingredient.toLowerCase()} before it goes to waste.`;
    if (proteinQuickCandidate) return `High-protein meals ready in ${resolvePrepMinutes(proteinQuickCandidate)} minutes.`;
    return "You've got smart options in your kitchen.";
  }, [expiringCandidate?.ingredient, kitchenState, proteinQuickCandidate]);

  const heroSubtext = useMemo(() => {
    if (kitchenState === "no-recipes") return "Let's design something new with what you have.";
    return `${readyRecipes.length} ready now \u00b7 ${proteinOptimizedCount} high-protein`;
  }, [kitchenState, proteinOptimizedCount, readyRecipes.length]);

  const proteinOnTrack = useMemo(() => {
    const macros = summary?.macros_card;
    if (!macros) return false;
    const target = macros.protein_target ?? 0;
    const consumed = macros.protein_consumed ?? 0;
    return target > 0 && consumed >= target;
  }, [summary?.macros_card]);

  const clearAllTimers = useCallback(() => {
    checklistTimersRef.current.forEach((timerId) => window.clearTimeout(timerId));
    if (progressRafRef.current !== null) {
      window.cancelAnimationFrame(progressRafRef.current);
    }
    checklistTimersRef.current = [];
    progressRafRef.current = null;
  }, []);

  useEffect(() => {
    if (kitchenState === "loading" || kitchenState === "no-pantry") return;
    setHeroVisible(false);
    const rafId = window.requestAnimationFrame(() => setHeroVisible(true));
    return () => window.cancelAnimationFrame(rafId);
  }, [kitchenState, readyRecipes.length, almostRecipes.length]);

  useEffect(() => {
    if (kitchenState === "loading") return;
    setBarsMounted(false);
    const rafId = window.requestAnimationFrame(() => setBarsMounted(true));
    return () => window.cancelAnimationFrame(rafId);
  }, [kitchenState, readyRecipes.length, almostRecipes.length]);

  useEffect(() => {
    if (kitchenState === "loading") return;
    const observer = new IntersectionObserver(
      (entries) => {
        setRevealedHeadings((previous) => {
          const next = { ...previous };
          let changed = false;
          for (const entry of entries) {
            if (!entry.isIntersecting) continue;
            const id = (entry.target as HTMLElement).dataset.revealId;
            if (!id || next[id]) continue;
            next[id] = true;
            changed = true;
          }
          return changed ? next : previous;
        });
      },
      { threshold: 0.2 }
    );

    const nodes = Array.from(document.querySelectorAll<HTMLElement>("[data-reveal-id]"));
    nodes.forEach((node) => observer.observe(node));
    return () => observer.disconnect();
  }, [kitchenState, readyRecipes.length, almostRecipes.length]);

  useEffect(() => {
    if (kitchenState === "loading") return;
    setForceReveal(false);
    const timerId = window.setTimeout(() => setForceReveal(true), 350);
    return () => window.clearTimeout(timerId);
  }, [kitchenState, readyRecipes.length, almostRecipes.length]);

  useEffect(() => {
    if (kitchenState !== "has-recipes") return;
    setVisibleReadyBars({});
    const observer = new IntersectionObserver(
      (entries) => {
        setVisibleReadyBars((previous) => {
          const next = { ...previous };
          let changed = false;
          for (const entry of entries) {
            if (!entry.isIntersecting) continue;
            const idRaw = (entry.target as HTMLElement).dataset.readyId;
            const id = idRaw ? Number(idRaw) : NaN;
            if (!Number.isFinite(id) || next[id]) continue;
            next[id] = true;
            changed = true;
          }
          return changed ? next : previous;
        });
      },
      { threshold: 0.25 }
    );
    const nodes = Array.from(document.querySelectorAll<HTMLElement>("[data-ready-id]"));
    nodes.forEach((node) => observer.observe(node));
    return () => observer.disconnect();
  }, [kitchenState, readyRecipes.length]);

  useEffect(() => {
    setShowAllReady(false);
  }, [ingredientFilter, readyRecipes.length]);

  useEffect(() => {
    if (modalPhase !== "staging") return;
    setStagingInsightIndex(0);
    const intervalId = window.setInterval(() => {
      setStagingInsightIndex((previous) => (previous + 1) % stagingInsights.length);
    }, 400);
    return () => window.clearInterval(intervalId);
  }, [modalPhase, stagingInsights.length]);

  useEffect(() => clearAllTimers, [clearAllTimers]);

  const clearStagingAnimations = () => {
    checklistTimersRef.current.forEach((timerId) => window.clearTimeout(timerId));
    checklistTimersRef.current = [];
    if (progressRafRef.current !== null) {
      window.cancelAnimationFrame(progressRafRef.current);
      progressRafRef.current = null;
    }
  };

  const scrollToSection = (sectionId: string) => {
    document.getElementById(sectionId)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const runRecipeGeneration = async () => {
    const runId = generationRunRef.current + 1;
    generationRunRef.current = runId;

    clearStagingAnimations();
    setGenerationError(null);
    setGeneratedRecipe(null);
    setResultVisible(false);
    setModalPhase("staging");
    setVisibleChecklistCount(0);
    setStagingProgress(0);

    aiChecklist.forEach((_, index) => {
      const timerId = window.setTimeout(() => {
        if (generationRunRef.current !== runId) return;
        setVisibleChecklistCount(index + 1);
      }, index * CHECKLIST_STAGGER_MS);
      checklistTimersRef.current.push(timerId);
    });

    const stageStart = performance.now();
    const animateProgress = (frameTime: number) => {
      if (generationRunRef.current !== runId) return;
      const elapsed = frameTime - stageStart;
      const progress = Math.min(100, (elapsed / MIN_STAGING_MS) * 100);
      setStagingProgress(progress);
      if (progress < 100) {
        progressRafRef.current = window.requestAnimationFrame(animateProgress);
      } else {
        progressRafRef.current = null;
      }
    };
    progressRafRef.current = window.requestAnimationFrame(animateProgress);

    const minimumStagingPromise = new Promise<void>((resolve) => {
      const timerId = window.setTimeout(resolve, MIN_STAGING_MS);
      checklistTimersRef.current.push(timerId);
    });

    let recipe: AIRecipeSuggestion | null = null;
    let errorMessage: string | null = null;

    try {
      const payload = await aiRecipesMutation.mutateAsync({ mode });
      recipe = payload.recipes?.[0] ?? null;
      if (!recipe) errorMessage = "No recipe could be generated. Try switching mode.";
    } catch {
      errorMessage = "Recipe generation failed. Please try again.";
    }

    await minimumStagingPromise;
    if (generationRunRef.current !== runId) return;

    setStagingProgress(100);

    if (errorMessage || !recipe) {
      setGenerationError(errorMessage ?? "Recipe generation failed. Please try again.");
      setModalPhase("error");
      return;
    }

    setGeneratedRecipe(recipe);
    setModalPhase("result");
    const revealId = window.setTimeout(() => {
      if (generationRunRef.current !== runId) return;
      setResultVisible(true);
    }, 30);
    checklistTimersRef.current.push(revealId);
  };

  const openGenerationModal = () => {
    setModalOpen(true);
    void runRecipeGeneration();
  };

  const onModalOpenChange = (open: boolean) => {
    setModalOpen(open);
    if (!open) {
      generationRunRef.current += 1;
      clearStagingAnimations();
      setModalPhase("idle");
      setGenerationError(null);
      setVisibleChecklistCount(0);
      setStagingProgress(0);
      setGeneratedRecipe(null);
      setResultVisible(false);
    }
  };

  if (showInitialLoader) {
    return (
      <DashboardLayout>
        <div className="space-y-14">
          <DashboardPageLoader scene="kitchen" isExiting={isLoaderExiting} />
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-14 page-reveal">
        {kitchenState === "loading" && (
          <section className="flex min-h-[55vh] items-center justify-center rounded-3xl border border-emerald-200/70 bg-[linear-gradient(155deg,rgba(232,236,232,0.95),rgba(244,245,240,0.95))] px-8 py-8">
            <div className="text-center">
              <Loader2 className="mx-auto h-7 w-7 animate-spin text-emerald-600" />
              <p className={cn("mt-4 text-slate-600", TYPE_BODY)}>Loading your kitchen intelligence...</p>
            </div>
          </section>
        )}

        {kitchenState === "no-pantry" && (
          <section className="flex min-h-[65vh] items-center justify-center rounded-3xl border border-emerald-200/70 bg-[linear-gradient(165deg,rgba(236,253,245,0.94),rgba(255,251,235,0.92))] px-6 py-14">
            <div className="max-w-2xl text-center">
              <p className={cn("inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-white/80 px-3 py-1 font-semibold uppercase tracking-[0.14em] text-emerald-700", TYPE_META)}>
                <UtensilsCrossed className="h-3.5 w-3.5 kitchen-utensil-pulse" />
                Kitchen Setup
              </p>
              <h1 className={cn("mt-4 tracking-tight text-slate-900", TYPE_H1)}>Let&apos;s build your kitchen.</h1>
              <p className={cn("mx-auto mt-4 max-w-xl text-slate-600", TYPE_BODY)}>
                Add a few ingredients and we&apos;ll instantly suggest meals you can cook.
              </p>
              <div className="mt-8 flex flex-wrap justify-center gap-3">
                <Button asChild size="lg" className="transition-transform duration-200 hover:scale-[1.02]">
                  <Link href="/dashboard/pantry?openAddModal=true">Add Ingredients -&gt;</Link>
                </Button>
                <Button asChild size="lg" variant="outline">
                  <Link href="/dashboard/pantry?openReceiptModal=true">Scan Grocery List -&gt;</Link>
                </Button>
              </div>
              <div className="mt-8 rounded-2xl border border-white/80 bg-white/85 p-5 text-left shadow-[0_14px_24px_-24px_rgba(15,23,42,0.35)]">
                <p className={cn("font-semibold text-slate-900", TYPE_BODY)}>How it works:</p>
                <ul className={cn("mt-4 space-y-4 text-slate-600", TYPE_BODY)}>
                  <li>We match your ingredients</li>
                  <li>We optimize for your goals</li>
                  <li>We reduce food waste</li>
                  <li>We generate new recipes instantly</li>
                </ul>
              </div>
            </div>
          </section>
        )}

        {(kitchenState === "no-recipes" || kitchenState === "has-recipes") && (
          <>
            {(pantryError || recipesError) && (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  Some kitchen data could not be loaded. You can still use AI Studio to generate recipes.
                </AlertDescription>
              </Alert>
            )}

            <section
              className={cn(
                "kitchen-hero-gradient relative overflow-hidden rounded-3xl p-6 md:p-6 transition-[opacity,transform] duration-300",
                heroVisible ? "translate-y-0 opacity-100" : "translate-y-2 opacity-0"
              )}
            >
              <div
                className="pointer-events-none absolute inset-0"
                style={{
                  backgroundImage:
                    "radial-gradient(circle at 15% 85%, rgba(255,255,255,0.05) 1px, transparent 1px), radial-gradient(circle at 85% 15%, rgba(255,255,255,0.05) 1px, transparent 1px)",
                  backgroundSize: "48px 48px",
                }}
              />
              <div className="relative z-[1]">
                <p className={cn("font-semibold uppercase tracking-[0.14em] text-white/45", TYPE_META)}>Kitchen Intelligence</p>
                <h1 className={cn("mt-4 tracking-tight text-white", TYPE_H1)} style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}>
                  {heroTitle}
                </h1>
                <p className={cn("mt-4 text-white/55", TYPE_BODY)}>{heroSubtext}</p>
                {kitchenState === "has-recipes" && proteinOnTrack ? (
                  <p className={cn("mt-2 inline-flex items-center gap-1 rounded-full bg-white/10 px-2.5 py-1 text-white/70", TYPE_META)}>
                    <Check className="h-3.5 w-3.5" />
                    On track for your protein goal
                  </p>
                ) : null}
                {ingredientFilter ? (
                  <Badge className={cn("mt-4 bg-white/15 text-white/80", TYPE_META)}>Filtered by ingredient: {ingredientFilter}</Badge>
                ) : null}
                <div className="mt-8 grid w-full max-w-2xl gap-3 sm:grid-cols-2">
                  <Button
                    type="button"
                    className={cn(
                      "kitchen-hero-cta kitchen-hero-cta-primary h-auto min-h-[52px] justify-start rounded-2xl border border-white/15 bg-white px-5 py-2.5 text-left text-emerald-800 shadow-[0_4px_16px_rgba(0,0,0,0.1)] transition-[transform,box-shadow] duration-200 hover:-translate-y-0.5 hover:shadow-[0_10px_24px_rgba(0,0,0,0.12)]",
                      TYPE_BODY
                    )}
                    onClick={() => scrollToSection(readyRecipes.length > 0 ? "ready-to-cook" : "ai-studio")}
                  >
                    <span className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
                      <ChefHat className="h-3.5 w-3.5" />
                    </span>
                    <span className="ml-2 flex flex-col">
                      <span className="font-medium">Cook Now -&gt;</span>
                      <span className={cn("text-emerald-800/80", TYPE_META)}>
                        {readyRecipes.length > 0 ? `${readyRecipes.length} recipes ready to go` : "Jump into AI Studio"}
                      </span>
                    </span>
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    className={cn(
                      "kitchen-hero-cta kitchen-hero-cta-secondary h-auto min-h-[52px] justify-start rounded-2xl border border-white/12 bg-white/10 px-5 py-2.5 text-left text-white shadow-none backdrop-blur-sm transition-colors duration-200 hover:bg-white/15",
                      TYPE_BODY
                    )}
                    onClick={() => scrollToSection("ai-studio")}
                  >
                    <span className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-white/15 text-white">
                      <WandSparkles className="h-3.5 w-3.5" />
                    </span>
                    <span className="ml-2 flex flex-col">
                      <span className="font-medium text-white">Create Something New -&gt;</span>
                      <span className={cn("text-white/70", TYPE_META)}>Craft a custom recipe from your pantry</span>
                    </span>
                  </Button>
                </div>
              </div>
            </section>

            {kitchenState === "has-recipes" && readyRecipes.length > 0 && (
              <section id="ready-to-cook" className="mt-14">
                <div className={cn("mb-7", headingClassName("ready-heading"))} data-reveal-id="ready-heading">
                  <h2 className={cn("tracking-tight text-slate-900", TYPE_H2)} style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}>Ready to cook</h2>
                  <p className={cn("mt-2 text-slate-600", TYPE_BODY)}>{readyRecipes.length} available now</p>
                </div>
                <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
                  {visibleReadyRecipes.map((recipe) => {
                    const prepMinutes = resolvePrepMinutes(recipe);
                    const protein = Math.round(recipe.macros?.protein_g ?? 0);
                    return (
                      <Card
                        key={recipe.recipe_id}
                        data-ready-id={recipe.recipe_id}
                        className="group overflow-hidden rounded-2xl border border-slate-200/80 bg-white p-5 shadow-[0_1px_3px_rgba(0,0,0,0.03)] transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(0,0,0,0.06)]"
                      >
                        <CardHeader className="space-y-0 p-0">
                          <div className="flex items-start gap-3">
                            <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
                              <ChefHat className="h-4 w-4" />
                            </span>
                            <CardTitle className={cn("truncate text-slate-900 font-semibold", TYPE_H3)}>{recipe.recipe_name}</CardTitle>
                          </div>
                        </CardHeader>
                        <CardContent className="mt-3 space-y-3 p-0">
                          <p className={cn("inline-flex items-center gap-1.5 text-slate-600", TYPE_BODY)}>
                            <Clock className="h-4 w-4" />
                            {prepMinutes} min - {protein}g protein
                          </p>

                          <div className="space-y-2">
                            <p className={cn("font-medium text-slate-600", TYPE_META)}>100% ingredient match</p>
                            <div className="h-[5px] overflow-hidden rounded-full bg-slate-100">
                              <div
                                className="h-full rounded-full transition-[width] duration-300 ease-out"
                                style={{
                                  width: visibleReadyBars[recipe.recipe_id] ? "100%" : "0%",
                                  background: "linear-gradient(90deg, #1B7D5A, #22956B)",
                                }}
                              />
                            </div>
                          </div>

                          <Button
                            asChild
                            className="h-9 w-fit rounded-lg bg-emerald-600 px-5 text-[13px] font-semibold text-white shadow-[0_2px_8px_rgba(27,125,90,0.2)] hover:bg-emerald-700"
                          >
                            <Link href="/dashboard/meals?tab=recipes">Cook -&gt;</Link>
                          </Button>
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
                {readyRecipes.length > 4 ? (
                  <div className="mt-5">
                    <button
                      type="button"
                      className={cn("font-medium text-[#6B7280] transition-colors duration-200 hover:text-[#4B5563]", TYPE_BODY)}
                      onClick={() => setShowAllReady((previous) => !previous)}
                    >
                      {showAllReady ? "Show fewer recipes ->" : `View all ${readyRecipes.length} ->`}
                    </button>
                  </div>
                ) : null}
              </section>
            )}

            {kitchenState === "has-recipes" && almostRecipes.length > 0 && (
              <section className="py-8">
                <div className={cn("mb-8", headingClassName("almost-heading"))} data-reveal-id="almost-heading">
                  <h2 className={cn("tracking-tight text-slate-900", TYPE_H2)} style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}>Almost There</h2>
                  <p className={cn("mt-4 text-slate-600", TYPE_BODY)}>Just 1-2 ingredients missing.</p>
                </div>
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                  {almostRecipes.map((recipe) => {
                    const matchPercent = Math.max(0, Math.min(99, resolveMatchPercentage(recipe)));
                    const missing = (recipe.missing_ingredient_names ?? []).slice(0, 4);
                    return (
                      <Card
                        key={recipe.recipe_id}
                        className="group overflow-hidden rounded-2xl border border-slate-200/80 bg-white p-5 shadow-[0_1px_3px_rgba(0,0,0,0.03)] transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(0,0,0,0.06)]"
                      >
                        <CardHeader className="space-y-4 p-0 pb-4">
                          <CardTitle className={cn("text-slate-900", TYPE_H3)}>{recipe.recipe_name}</CardTitle>
                          <p className={cn("inline-flex items-center gap-1.5 text-muted-foreground", TYPE_BODY)}>
                            <Clock className="h-4 w-4" />
                            {resolvePrepMinutes(recipe)} min
                          </p>
                        </CardHeader>
                        <CardContent className="space-y-4 p-0">
                          <div className="space-y-4">
                            <p className={cn("font-medium text-slate-600", TYPE_META)}>Ingredient match: {matchPercent}%</p>
                            <div className="h-[5px] overflow-hidden rounded-full bg-slate-100">
                              <div
                                className="h-full rounded-full transition-[width] duration-300 ease-out"
                                style={{
                                  width: barsMounted ? `${matchPercent}%` : "0%",
                                  background: "linear-gradient(90deg, #1B7D5A, #22956B)",
                                }}
                              />
                            </div>
                          </div>

                          <div>
                            <p className={cn("font-medium text-slate-700", TYPE_META)}>Missing ingredients</p>
                            <div className="mt-4 flex flex-wrap gap-1.5">
                              {missing.map((ingredient) => (
                                <Badge key={`${recipe.recipe_id}-${ingredient}`} className={cn("rounded-lg border-0 bg-orange-50 text-orange-600", TYPE_META)}>
                                  {ingredient}
                                </Badge>
                              ))}
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              </section>
            )}

            <section id="ai-studio" className="mt-[96px]">
              <div className={cn("mx-auto w-full max-w-[960px]", kitchenState === "no-recipes" ? "max-w-[960px]" : "")}>
                <div
                  className={cn(
                    "kitchen-ai-band relative overflow-hidden rounded-[32px] border px-6 py-12 text-[#ECFDF5] shadow-[0_30px_70px_rgba(6,95,70,0.25)] md:px-[72px] md:py-[88px]",
                    headingClassName("studio-heading")
                  )}
                  data-reveal-id="studio-heading"
                >
                  <div className="relative z-[1]">
                    <h2 className="text-[38px] leading-[1.1] font-semibold tracking-[-0.02em] text-[#E6FFFA] md:text-[44px]" style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}>
                      Design a meal from your pantry.
                    </h2>
                    <p className={cn("mt-3 text-[#D7F3E6]", TYPE_BODY)}>Designed from your pantry and goals.</p>
                    <p
                      key={mode}
                      className={cn(
                        "mt-2 text-[#D1FAE5]/90 transition-opacity duration-150 animate-[kitchen-fade-in_150ms_ease-out]",
                        TYPE_META
                      )}
                    >
                      {modeInsight}
                    </p>

                    <div className="mt-10 inline-flex rounded-full bg-white/15 p-1.5">
                      <button
                        type="button"
                        onClick={() => setMode("goal_adherent")}
                        className={cn(
                          "rounded-lg px-5 py-2 transition-colors duration-200",
                          mode === "goal_adherent" ? "bg-[#10B981] text-[#064E3B]" : "text-[#D1FAE5] hover:text-[#ECFDF5]"
                        )}
                      >
                        <span className={TYPE_BODY}>Goal Focused</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => setMode("guilt_free")}
                        className={cn(
                          "rounded-lg px-5 py-2 transition-colors duration-200",
                          mode === "guilt_free" ? "bg-[#10B981] text-[#064E3B]" : "text-[#D1FAE5] hover:text-[#ECFDF5]"
                        )}
                      >
                        <span className={TYPE_BODY}>Balanced</span>
                      </button>
                    </div>

                    <Button
                      className={cn(
                        "mt-9 h-12 rounded-xl bg-[#10B981] px-8 font-semibold text-[#064E3B] shadow-[0_12px_40px_rgba(16,185,129,0.4)] transition-[transform,box-shadow,filter] duration-200 hover:-translate-y-0.5 hover:shadow-[0_18px_50px_rgba(16,185,129,0.5)] hover:brightness-[1.03]",
                        TYPE_BODY
                      )}
                      onClick={openGenerationModal}
                    >
                      <WandSparkles className="mr-2 h-4 w-4" />
                      Generate with AI -&gt;
                    </Button>
                  </div>
                </div>
              </div>
            </section>
          </>
        )}
      </div>

      <Dialog open={modalOpen} onOpenChange={onModalOpenChange}>
        <DialogContent className="w-[92vw] max-w-[900px] overflow-hidden rounded-2xl border p-0">
          <DialogHeader className="border-b bg-[linear-gradient(160deg,rgba(236,253,245,0.86),rgba(255,251,235,0.9))] px-6 py-4">
            <DialogTitle className={cn(TYPE_H2)}>Crafting something just for you...</DialogTitle>
            <DialogDescription className={cn(TYPE_BODY)}>
              We are designing a recipe from your pantry inventory and your selected mode.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 p-6">
            {modalPhase === "staging" && (
              <div className="space-y-4">
                <div className="space-y-4">
                  {aiChecklist.map((step, index) => {
                    const visible = visibleChecklistCount > index;
                    return (
                      <div
                        key={step}
                        className={cn(
                          "flex items-center gap-2 rounded-xl border bg-white px-4 py-4 transition-[opacity,transform,border-color] duration-200",
                          visible ? "translate-y-0 opacity-100 border-[#CFE2D8]" : "translate-y-1 opacity-0 border-slate-200"
                        )}
                      >
                        <CheckCircle2 className={cn("h-4 w-4", visible ? "text-[#2F6F5E]" : "text-slate-400")} />
                        <p className={cn("text-slate-700", TYPE_BODY)}>{step}</p>
                      </div>
                    );
                  })}
                </div>

                <div className="space-y-4">
                  <p className={cn("text-slate-600", TYPE_META)}>Designing your recipe...</p>
                  <div className="h-2 overflow-hidden rounded-full bg-[#E5E7EB]">
                    <div
                      className="h-full rounded-full bg-[linear-gradient(90deg,#2F6F5E,#5A9A7E)] transition-[width] duration-200 ease-out"
                      style={{ width: `${Math.min(100, Math.max(0, stagingProgress)).toFixed(1)}%` }}
                    />
                  </div>
                  <p
                    key={`insight-${stagingInsightIndex}`}
                    className={cn(
                      "text-[#2F6F5E] transition-[opacity,transform] duration-200 animate-[kitchen-fade-in_200ms_ease-out]",
                      TYPE_META
                    )}
                  >
                    {stagingInsights[stagingInsightIndex]}
                  </p>
                </div>
              </div>
            )}

            {modalPhase === "error" && (
              <div className="space-y-4">
                <Alert variant="destructive">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>{generationError ?? "Recipe generation failed."}</AlertDescription>
                </Alert>
                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => onModalOpenChange(false)}>
                    Close
                  </Button>
                  <Button onClick={() => void runRecipeGeneration()}>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Try Again
                  </Button>
                </div>
              </div>
            )}

            {modalPhase === "result" && generatedRecipe && (
              <Card
                className={cn(
                  "border-slate-200 bg-white transition-[opacity,transform,box-shadow] duration-300",
                  resultVisible
                    ? "translate-y-0 opacity-100 shadow-[0_26px_36px_-26px_rgba(15,23,42,0.38)]"
                    : "translate-y-5 opacity-0 shadow-[0_10px_18px_-18px_rgba(15,23,42,0.3)]"
                )}
              >
                <CardHeader className="space-y-4">
                  <CardTitle className={cn("flex items-center gap-2", TYPE_H3)}>
                    <ChefHat className="h-5 w-5 text-emerald-600" />
                    {generatedRecipe.name}
                  </CardTitle>
                  <p className={cn("text-slate-600", TYPE_BODY)}>{generatedRecipe.description}</p>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className={cn("flex flex-wrap gap-2", TYPE_META)}>
                    <Badge variant="outline" className={TYPE_META}>{generatedRecipe.estimated_prep_time_min} min</Badge>
                    <Badge variant="outline" className={TYPE_META}>P {generatedRecipe.estimated_protein_g}g</Badge>
                    <Badge variant="outline" className={TYPE_META}>C {generatedRecipe.estimated_carbs_g}g</Badge>
                    <Badge variant="outline" className={TYPE_META}>F {generatedRecipe.estimated_fat_g}g</Badge>
                  </div>

                  <p className={cn("text-slate-700", TYPE_BODY)}>Designed using {generatedUsesCount} pantry items.</p>

                  {generatedOptionalBadges.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {generatedOptionalBadges.map((badge) => (
                        <Badge key={badge} className={cn("border border-[#DCE8E2] bg-[#F3F8F5] text-[#476355]", TYPE_META)}>
                          <Sparkles className="mr-1 h-3 w-3" />
                          {badge}
                        </Badge>
                      ))}
                    </div>
                  )}

                  <div>
                    <p className={cn("mb-4 font-medium text-slate-700", TYPE_META)}>Ingredients</p>
                    <div className="flex flex-wrap gap-1.5">
                      {(generatedRecipe.ingredients ?? []).map((ingredient, index) => (
                        <Badge key={`${generatedRecipe.name}-${ingredient.name}-${index}`} className={cn("bg-slate-100 text-slate-700", TYPE_META)}>
                          {ingredient.name}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  <div className="flex flex-wrap justify-end gap-2">
                    <Button variant="outline" className={cn("h-9", TYPE_BODY)} onClick={() => void runRecipeGeneration()}>
                      Generate Another
                    </Button>
                    <Button asChild className={cn("h-9", TYPE_BODY)}>
                      <Link href="/dashboard/meals?tab=recipes" onClick={() => onModalOpenChange(false)}>
                        Cook This -&gt;
                      </Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}

            {modalPhase === "idle" && (
              <div className={cn("flex items-center justify-center py-6 text-slate-600", TYPE_BODY)}>
                Preparing recipe generation...
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      <style jsx>{`
        .kitchen-hero-gradient {
          background: linear-gradient(135deg, #14533c 0%, #166534 30%, #1b7d5a 60%, #22956b 100%);
          box-shadow: 0 10px 30px -12px rgba(20, 83, 60, 0.35);
        }

        .kitchen-ready-tile {
          box-shadow: 0 8px 24px rgba(0, 0, 0, 0.04), inset 0 1px 0 rgba(255, 255, 255, 0.4);
        }

        .kitchen-ready-tile:hover {
          box-shadow: 0 20px 40px rgba(0, 0, 0, 0.06);
        }

        .kitchen-ai-band {
          background: linear-gradient(135deg, #064e3b 0%, #047857 50%, #065f46 100%);
          background-size: 130% 130%;
          border-color: rgba(255, 255, 255, 0.08);
          transition: background-position 240ms ease-out;
        }

        .kitchen-ai-band::before {
          content: "";
          position: absolute;
          inset: -30%;
          background: radial-gradient(circle at 75% 25%, rgba(16, 185, 129, 0.25), transparent 60%);
          filter: blur(90px);
          pointer-events: none;
        }

        .kitchen-ai-band:hover {
          background-position: 85% 25%;
        }

        .kitchen-cook-button {
          position: relative;
          overflow: hidden;
        }

        .kitchen-cook-button::after {
          content: "";
          position: absolute;
          inset: 0;
          background: radial-gradient(circle at center, rgba(255, 255, 255, 0.28) 0%, rgba(255, 255, 255, 0) 65%);
          opacity: 0;
          transform: scale(0.6);
          pointer-events: none;
        }

        .kitchen-cook-button:active::after {
          animation: kitchen-cook-ripple 220ms ease-out;
        }

        .kitchen-utensil-pulse {
          animation: kitchen-utensil-pulse 2s ease-in-out infinite;
          transform-origin: center;
        }

        @keyframes kitchen-hero-shift {
          0% {
            background-position: 0% 50%;
          }
          50% {
            background-position: 100% 50%;
          }
          100% {
            background-position: 0% 50%;
          }
        }

        @keyframes kitchen-utensil-pulse {
          0%,
          100% {
            transform: scale(0.95);
          }
          50% {
            transform: scale(1);
          }
        }

        @keyframes kitchen-fade-in {
          from {
            opacity: 0;
            transform: translateY(6px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        @keyframes kitchen-cook-ripple {
          0% {
            opacity: 0.18;
            transform: scale(0.6);
          }
          100% {
            opacity: 0;
            transform: scale(1.1);
          }
        }

        .page-reveal {
          animation: kitchen-page-reveal 220ms ease-out;
        }

        @keyframes kitchen-page-reveal {
          from {
            opacity: 0;
            transform: translateY(6px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
      `}</style>
    </DashboardLayout>
  );
}

