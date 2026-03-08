"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, Camera, Plus, Search, Trash2, Weight } from "lucide-react";
import { DashboardLayout } from "@/components/layouts/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { DashboardPageLoader, useInitialPageLoader } from "@/shared/components/states/DashboardPageLoader";
import { useDeleteItem, useInventoryItems, useInventoryStatus, useMakeableRecipes } from "../inventory/hooks/useInventory";
import { useExpiringItems, useRestockList } from "../inventory/hooks/useTracking";
import AddItemsDialog from "../inventory/components/AddItemsDialog";
import ReceiptUpload from "../inventory/components/ReceiptUpload";
import { FilterOptions, InventoryItem } from "../inventory/types";

type MakeableResponse = {
  fully_makeable?: unknown[];
};

const AI_SHOWN_SESSION_KEY = "pantry_ai_shown";
const HERO_SHADOW = "shadow-[0_6px_20px_rgba(0,0,0,0.05),0_30px_60px_rgba(0,0,0,0.06)]";
const METRICS_SHADOW = "shadow-[0_6px_18px_rgba(0,0,0,0.04),0_20px_40px_rgba(0,0,0,0.05)]";
const SIGNAL_SHADOW = "shadow-[0_6px_18px_rgba(0,0,0,0.04)]";
const ITEM_SHADOW = "shadow-[0_8px_24px_rgba(0,0,0,0.06)]";
const ITEM_HOVER_SHADOW = "hover:shadow-[0_14px_30px_rgba(0,0,0,0.08)]";
const RING_RADIUS = 18;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;
const CATEGORY_CHIP = "rounded-full bg-[#E7EFEA] px-2.5 py-1 text-[12px] font-medium text-[#2F6F5E]";

function formatWeight(grams: number): string {
  if (grams >= 1000) return `${(grams / 1000).toFixed(1)} kg`;
  return `${Math.round(grams)} g`;
}

function getSignalRingClass(variant: "low" | "soon" | "fresh"): string {
  if (variant === "low") return "bg-[conic-gradient(#E57373_0%_25%,transparent_25%_100%)]";
  if (variant === "soon") return "bg-[conic-gradient(#E6A23C_0%_40%,transparent_40%_100%)]";
  return "bg-[conic-gradient(#5A9A7E_0%_80%,transparent_80%_100%)]";
}

function getUseSoonRingVariant(daysRemaining: number): "low" | "soon" | "fresh" {
  if (daysRemaining <= 1) return "low";
  if (daysRemaining <= 3) return "soon";
  return "fresh";
}

function getFreshnessText(daysUntilExpiry: number | null): string {
  if (daysUntilExpiry === null) return "Freshness window not available";
  if (daysUntilExpiry < 0) {
    const expiredDaysAgo = Math.abs(daysUntilExpiry);
    return `Expired ${expiredDaysAgo} day${expiredDaysAgo === 1 ? "" : "s"} ago`;
  }
  if (daysUntilExpiry === 0) return "Expires today";
  if (daysUntilExpiry === 1) return "Fresh for 1 more day";
  return `Fresh for ${daysUntilExpiry} more days`;
}

function getFreshnessMeta(daysUntilExpiry: number | null): { fillClass: string; width: number } {
  if (daysUntilExpiry === null) return { fillClass: "bg-gradient-to-r from-[#2F6F5E] to-[#5A9A7E]", width: 32 };
  if (daysUntilExpiry < 0) return { fillClass: "bg-gradient-to-r from-[#DC2626] to-[#F97316]", width: 12 };
  if (daysUntilExpiry === 0) return { fillClass: "bg-gradient-to-r from-[#E6A23C] to-[#F59E0B]", width: 20 };
  if (daysUntilExpiry < 3) return { fillClass: "bg-gradient-to-r from-[#2F6F5E] to-[#5A9A7E]", width: Math.max(18, Math.min(36, daysUntilExpiry * 10 + 10)) };
  if (daysUntilExpiry <= 7) return { fillClass: "bg-gradient-to-r from-[#2F6F5E] to-[#5A9A7E]", width: Math.max(42, Math.min(76, (daysUntilExpiry / 7) * 76)) };
  return { fillClass: "bg-gradient-to-r from-[#2F6F5E] to-[#5A9A7E]", width: Math.max(78, Math.min(100, (daysUntilExpiry / 14) * 100)) };
}

function getHealthMessage(score: number): string {
  if (score > 80) return "Stable";
  return "Needs attention";
}

function formatCategoryLabel(category: string): string {
  return category
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export default function PantryPage() {
  const searchParams = useSearchParams();
  const heroRef = useRef<HTMLElement | null>(null);

  const [addItemsOpen, setAddItemsOpen] = useState(false);
  const [receiptUploadOpen, setReceiptUploadOpen] = useState(false);
  const [queryHandled, setQueryHandled] = useState(false);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<string>("all");
  const [showExpiringOnly, setShowExpiringOnly] = useState(false);
  const [expiringDays, setExpiringDays] = useState<number>(3);
  const [animatedScore, setAnimatedScore] = useState(0);
  const [isAIActive, setIsAIActive] = useState(false);
  const [isAITabInvite, setIsAITabInvite] = useState(false);
  const [isInstantClosingAI, setIsInstantClosingAI] = useState(false);
  const [aiStreamText, setAiStreamText] = useState("");
  const [activeRecommendationIdx, setActiveRecommendationIdx] = useState(0);
  const aiStreamStartTimerRef = useRef<number | null>(null);
  const aiStreamCharTimerRef = useRef<number | null>(null);
  const aiFoldTimerRef = useRef<number | null>(null);
  const aiAutoOpenTimerRef = useRef<number | null>(null);
  const hasAttemptedAutoOpenRef = useRef(false);
  const aiShouldAutoFoldRef = useRef(false);
  const aiInsightTextRef = useRef("");

  const queryFilters: FilterOptions = {
    category: category === "all" ? undefined : category,
    lowStockOnly: false,
    expiringSoon: false,
  };

  const { data: inventoryStatus, isLoading: inventoryStatusLoading, error: inventoryStatusError } = useInventoryStatus();
  const { data: inventoryItemsData, isLoading: inventoryItemsLoading, error: inventoryItemsError } = useInventoryItems(queryFilters);
  const { data: expiringData, isLoading: expiringLoading, error: expiringError, refetch: refetchExpiring } = useExpiringItems(expiringDays);
  const { data: restockData, isLoading: restockLoading, error: restockError } = useRestockList();
  const { data: makeableDataRaw } = useMakeableRecipes(8);
  const deleteItem = useDeleteItem();

  const isCoreDataReady =
    !inventoryStatusLoading &&
    !inventoryItemsLoading &&
    !expiringLoading &&
    !restockLoading;
  const { showLoader: showInitialLoader, isExiting: isLoaderExiting } = useInitialPageLoader(isCoreDataReady, {
    showDelayMs: 0,
    minVisibleMs: 560,
    exitMs: 200,
  });

  useEffect(() => {
    if (queryHandled) return;
    if (searchParams.get("openAddModal") === "true") setAddItemsOpen(true);
    if (searchParams.get("openReceiptModal") === "true") setReceiptUploadOpen(true);
    setQueryHandled(true);
  }, [queryHandled, searchParams]);

  const totalWeight = inventoryStatus?.total_weight_g ?? 0;
  const totalItems = inventoryStatus?.total_items ?? 0;
  const expiringSoonCount = (expiringData?.items ?? []).length;
  const runningLowCount = (inventoryStatus?.low_stock ?? []).length;

  const pantryHealthScore = useMemo(() => {
    const expiringSoon = inventoryStatus?.expiring_soon ?? [];
    const oneDayCount = expiringSoon.filter((item) => {
      const d = item.days_until_expiry ?? 99;
      return d <= 1;
    }).length;
    const threeDayCount = expiringSoon.filter((item) => {
      const d = item.days_until_expiry ?? 99;
      return d > 1 && d <= 3;
    }).length;
    const lowStock = inventoryStatus?.low_stock?.length ?? 0;
    const raw = 100 - oneDayCount * 10 - threeDayCount * 5 - lowStock * 2;
    return Math.max(0, Math.min(100, raw));
  }, [inventoryStatus?.expiring_soon, inventoryStatus?.low_stock]);

  useEffect(() => {
    setAnimatedScore(0);
    const rafId = window.requestAnimationFrame(() => setAnimatedScore(pantryHealthScore));
    return () => window.cancelAnimationFrame(rafId);
  }, [pantryHealthScore]);

  const expiringInventoryIds = useMemo(() => {
    return new Set((expiringData?.items ?? []).map((item) => item.inventory_id));
  }, [expiringData?.items]);

  const filteredItems = useMemo(() => {
    let items = inventoryItemsData?.items ?? [];

    if (showExpiringOnly) {
      items = items.filter((item) => expiringInventoryIds.has(item.id));
    }

    if (!search.trim()) return items;
    const needle = search.trim().toLowerCase();
    return items.filter((item) => item.item_name.toLowerCase().includes(needle));
  }, [expiringInventoryIds, inventoryItemsData?.items, search, showExpiringOnly]);

  const categories = useMemo(() => {
    return Object.keys(inventoryStatus?.categories ?? {}).sort((a, b) => a.localeCompare(b));
  }, [inventoryStatus?.categories]);

  const makeableData = makeableDataRaw as MakeableResponse | undefined;
  const readyRecipeCount = Array.isArray(makeableData?.fully_makeable) ? makeableData.fully_makeable.length : 0;

  const expiringPreview = useMemo(() => {
    return [...(expiringData?.items ?? [])].sort((a, b) => a.days_remaining - b.days_remaining).slice(0, 3);
  }, [expiringData?.items]);

  const runningLowPreview = useMemo(() => {
    return (restockData?.urgent_items ?? []).slice(0, 3);
  }, [restockData?.urgent_items]);

  const expiringRecommendations = useMemo(() => {
    return (expiringData?.action_recommendations ?? []).slice(0, 3);
  }, [expiringData?.action_recommendations]);

  const heroAiLines = useMemo(() => {
    const aiLines = (inventoryStatus?.ai_recommendations ?? [])
      .map((line) => line.trim())
      .filter((line) => line.length > 0)
      .slice(0, 4);

    if (aiLines.length > 0) return aiLines;

    const fallback = [
      `${expiringSoonCount} item${expiringSoonCount === 1 ? "" : "s"} need expiry attention soon.`,
      `${runningLowCount} staple${runningLowCount === 1 ? "" : "s"} are running low.`,
      `${totalItems} tracked ingredients are currently shaping your kitchen plan.`,
      `Pantry health is ${pantryHealthScore}% right now.`
    ];

    return fallback;
  }, [expiringSoonCount, inventoryStatus?.ai_recommendations, pantryHealthScore, runningLowCount, totalItems]);

  const aiInsightText = useMemo(() => heroAiLines.join("\n\n"), [heroAiLines]);

  useEffect(() => {
    aiInsightTextRef.current = aiInsightText;
  }, [aiInsightText]);

  useEffect(() => {
    if (!showExpiringOnly || expiringRecommendations.length === 0) {
      setActiveRecommendationIdx(0);
      return;
    }

    const intervalId = window.setInterval(() => {
      setActiveRecommendationIdx((prev) => (prev + 1) % expiringRecommendations.length);
    }, 2800);

    return () => window.clearInterval(intervalId);
  }, [expiringRecommendations.length, showExpiringOnly]);

  const heroHeadline = useMemo(() => {
    if (runningLowCount >= 4) return "You're running low on staples.";
    if (expiringSoonCount > 0) return "A few essentials need attention.";
    if (readyRecipeCount > 0) return "Your kitchen is stocked and ready.";
    if (totalItems > 0) return "Fresh ingredients, ready to cook.";
    return "Your pantry journey starts here.";
  }, [expiringSoonCount, readyRecipeCount, runningLowCount, totalItems]);

  const onDeleteItem = (item: InventoryItem) => {
    if (!confirm(`Remove "${item.item_name}" from pantry?`)) return;
    deleteItem.mutate(item.id);
  };

  const onToggleExpiringFilter = () => {
    const next = !showExpiringOnly;
    setShowExpiringOnly(next);
    if (next) {
      void refetchExpiring();
    }
  };

  const clearAIStreamTimers = useCallback(() => {
    if (aiAutoOpenTimerRef.current !== null) {
      window.clearTimeout(aiAutoOpenTimerRef.current);
      aiAutoOpenTimerRef.current = null;
    }
    if (aiStreamStartTimerRef.current !== null) {
      window.clearTimeout(aiStreamStartTimerRef.current);
      aiStreamStartTimerRef.current = null;
    }
    if (aiStreamCharTimerRef.current !== null) {
      window.clearTimeout(aiStreamCharTimerRef.current);
      aiStreamCharTimerRef.current = null;
    }
    if (aiFoldTimerRef.current !== null) {
      window.clearTimeout(aiFoldTimerRef.current);
      aiFoldTimerRef.current = null;
    }
  }, []);

  const streamText = useCallback((text: string, onComplete?: () => void) => {
    setAiStreamText("");

    let charIndex = 0;
    const chars = Array.from(text);

    const typeNextChar = () => {
      if (charIndex >= chars.length) {
        aiStreamCharTimerRef.current = null;
        onComplete?.();
        return;
      }

      const currentChar = chars[charIndex];
      setAiStreamText((prev) => prev + currentChar);

      let delay = 5;
      if (currentChar === ",") delay = 20;
      if (currentChar === ".") delay = 50;
      if (currentChar === "\n") delay = 50;
      delay += 1;

      charIndex += 1;
      aiStreamCharTimerRef.current = window.setTimeout(typeNextChar, delay);
    };

    typeNextChar();
  }, []);

  const autoFoldAI = useCallback(() => {
    aiShouldAutoFoldRef.current = false;
    setIsAIActive(false);
    setIsAITabInvite(true);
  }, []);

  const deactivateAI = useCallback(() => {
    clearAIStreamTimers();
    aiShouldAutoFoldRef.current = false;
    setIsAIActive(false);
    setAiStreamText("");
  }, [clearAIStreamTimers]);

  const forceDeactivateAI = useCallback(() => {
    clearAIStreamTimers();
    aiShouldAutoFoldRef.current = false;
    setIsInstantClosingAI(true);
    setIsAIActive(false);
    setAiStreamText("");
    setIsAITabInvite(false);
    window.setTimeout(() => setIsInstantClosingAI(false), 0);
  }, [clearAIStreamTimers]);

  const activateAI = useCallback((options?: { auto?: boolean; text?: string }) => {
    const isAutoActivation = options?.auto === true;
    const textToStream = options?.text ?? aiInsightTextRef.current;
    clearAIStreamTimers();
    aiShouldAutoFoldRef.current = isAutoActivation;
    setIsInstantClosingAI(false);
    setIsAIActive(true);
    setIsAITabInvite(false);
    setAiStreamText("");
    aiStreamStartTimerRef.current = window.setTimeout(() => {
      streamText(textToStream, () => {
        if (aiShouldAutoFoldRef.current) {
          aiFoldTimerRef.current = window.setTimeout(() => {
            autoFoldAI();
            aiFoldTimerRef.current = null;
          }, 1000);
        }
      });
      aiStreamStartTimerRef.current = null;
    }, 100);
  }, [autoFoldAI, clearAIStreamTimers, streamText]);

  useEffect(() => {
    return () => {
      clearAIStreamTimers();
    };
  }, [clearAIStreamTimers]);

  useEffect(() => {
    if (!isAIActive) return;
    const heroEl = heroRef.current;
    if (!heroEl) return;

    const handleScroll = () => {
      const rect = heroEl.getBoundingClientRect();
      if (rect.height < 80) return;
      const heroHeight = rect.height || 1;
      const visibleHeight = Math.max(0, Math.min(rect.bottom, window.innerHeight) - Math.max(rect.top, 0));
      const visibleRatio = visibleHeight / heroHeight;

      if (visibleRatio < 0.3) {
        forceDeactivateAI();
      }
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    window.addEventListener("resize", handleScroll);
    const rafId = window.requestAnimationFrame(handleScroll);

    return () => {
      window.cancelAnimationFrame(rafId);
      window.removeEventListener("scroll", handleScroll);
      window.removeEventListener("resize", handleScroll);
    };
  }, [forceDeactivateAI, isAIActive]);

  useEffect(() => {
    if (inventoryStatusLoading || isAIActive) return;
    if (showInitialLoader) return;
    if (!aiInsightText.trim()) return;
    if (aiAutoOpenTimerRef.current !== null) return;

    const hasShownAI = sessionStorage.getItem(AI_SHOWN_SESSION_KEY) === "true";
    if (hasShownAI) {
      hasAttemptedAutoOpenRef.current = true;
      return;
    }
    if (hasAttemptedAutoOpenRef.current) {
      return;
    }

    aiAutoOpenTimerRef.current = window.setTimeout(() => {
      activateAI({ auto: true, text: aiInsightText });
      sessionStorage.setItem(AI_SHOWN_SESSION_KEY, "true");
      hasAttemptedAutoOpenRef.current = true;
      aiAutoOpenTimerRef.current = null;
    }, 400);
  }, [activateAI, aiInsightText, inventoryStatusLoading, isAIActive, showInitialLoader]);

  const scoreOffset = RING_CIRCUMFERENCE * (1 - animatedScore / 100);

  if (showInitialLoader) {
    return (
      <DashboardLayout>
        <div className="min-h-full">
          <div className="mx-auto max-w-[1200px] px-8 pb-12 pt-2 text-[#2F2A24]">
            <DashboardPageLoader scene="pantry" isExiting={isLoaderExiting} />
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="min-h-full page-reveal">
        <div className="mx-auto max-w-[1200px] px-8 pb-12 pt-2 text-[#2F2A24]">
          <section
            ref={heroRef}
            id="hero"
            className={`hero-wrapper relative h-[360px] overflow-hidden rounded-[24px] px-10 py-12 ${isInstantClosingAI ? "transition-none" : "transition-[background,box-shadow] duration-[260ms] ease-out"} ${
              isAIActive
                ? "ai-active bg-[linear-gradient(120deg,#F8F4ED_0%,#EFE7DD_100%)] bg-[length:200%_200%] [animation:pantry-hero-drift_10s_ease_infinite_alternate] shadow-[0_12px_32px_rgba(0,0,0,0.08)]"
                : `bg-gradient-to-br from-[#F8F5F0] to-[#EFE8DE] ${HERO_SHADOW}`
            } flex flex-col items-stretch justify-between gap-10 lg:flex-row`}
          >
            <button
              type="button"
              onClick={() => (isAIActive ? deactivateAI() : activateAI({ auto: false }))}
              className={`ai-tab absolute right-4 top-1/2 z-30 -translate-y-1/2 rounded-[12px] border border-[#D9D2C8] bg-[#F6F2EC] px-2 py-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#455448] transition-all duration-[260ms] [writing-mode:vertical-rl] ${
                isAIActive
                  ? "active border-[#2F6F5E] bg-[#EFE9E1] text-[#2F6F5E] shadow-[0_0_0_4px_rgba(47,111,94,0.12)]"
                  : isAITabInvite
                    ? "invite border-[#2F6F5E] bg-[#F3EFE9] text-[#2F6F5E]"
                    : ""
              }`}
              aria-pressed={isAIActive}
              aria-label={isAIActive ? "Close pantry insight mode" : "Open pantry insight mode"}
            >
              AI Insight
            </button>
            <div
              className={`hero-default-layer space-y-4 lg:w-[62%] ${
                isInstantClosingAI ? "transition-none" : "transition-[opacity,transform] duration-[260ms] ease-out"
              } ${isAIActive ? "pointer-events-none -translate-y-[10px] opacity-0" : "opacity-100"}`}
            >
              <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-[#7A7267]">Your Pantry</p>
              <div className="flex items-start gap-4">
                <span aria-hidden className="mt-1 block h-[56px] w-[6px] rounded-[6px] bg-[#2F6F5E]" />
                <div className="space-y-2">
                  <h1 className="text-[42px] font-bold leading-[1.1] tracking-[-0.02em] text-[#2A2A2A]">{heroHeadline}</h1>
                  <p className="text-[16px] text-[#4B5563]/75">Track freshness, reduce waste, and power smarter meals.</p>
                  <p className="text-[15px] text-[#5F5A51]">You can cook {readyRecipeCount} meals with what you have.</p>
                </div>
              </div>
              <div className="flex gap-3 pl-6 pt-1">
                <Button className="h-10 rounded-[12px] bg-[#2F6F5E] px-[18px] py-[10px] font-medium text-white hover:bg-[#2A6254]" onClick={() => setAddItemsOpen(true)}>
                  <Plus className="mr-2 h-4 w-4" />
                  Add Items
                </Button>
                <Button variant="outline" className="h-10 rounded-[12px] border border-[#E5E0DA] bg-white px-[18px] py-[10px] font-medium text-[#5F574D] hover:bg-[#FCFBF9]" onClick={() => setReceiptUploadOpen(true)}>
                  <Camera className="mr-2 h-4 w-4" />
                  Scan Receipt
                </Button>
              </div>
            </div>

            <div
              className={`metrics-card z-[1] h-full rounded-[20px] border border-[#ECE5DD] bg-[#FBF8F4] p-6 ${
                isInstantClosingAI ? "transition-none" : "transition-[opacity,transform,filter] duration-[260ms] ease-out"
              } ${METRICS_SHADOW} ${isAIActive ? "scale-[0.96] opacity-[0.14] filter saturate-[.85]" : "opacity-100"} lg:w-[38%]`}
            >
              <div className="grid grid-cols-2 gap-x-8 gap-y-4">
                <div className="space-y-1">
                  <p className="text-[12px] text-[#7B7367]">Items</p>
                  <p className="text-[22px] font-bold text-[#312C27]">{totalItems}</p>
                </div>
                <div className="space-y-1">
                  <p className="text-[12px] text-[#7B7367]">Expiring</p>
                  <p className="text-[22px] font-bold text-[#312C27]">{expiringSoonCount}</p>
                </div>
                <div className="space-y-1">
                  <p className="text-[12px] text-[#7B7367]">Weight</p>
                  <p className="text-[22px] font-bold text-[#312C27]">{formatWeight(totalWeight)}</p>
                </div>
                <div className="space-y-1">
                  <p className="text-[12px] text-[#7B7367]">Low</p>
                  <p className="text-[22px] font-bold text-[#312C27]">{runningLowCount}</p>
                </div>
              </div>

              <div className="my-4 h-px bg-[#E5E7EB]" />

              <div className="mt-3 flex items-center gap-3">
                <div className="h-9 w-9 shrink-0">
                  <svg viewBox="0 0 44 44" className="h-9 w-9 -rotate-90">
                    <circle cx="22" cy="22" r={RING_RADIUS} stroke="rgba(125,118,106,0.22)" strokeWidth="5" fill="none" />
                    <circle
                      cx="22"
                      cy="22"
                      r={RING_RADIUS}
                      stroke="#5E7C65"
                      strokeWidth="7"
                      fill="none"
                      strokeLinecap="round"
                      strokeDasharray={RING_CIRCUMFERENCE}
                      strokeDashoffset={scoreOffset}
                      style={{ transition: "stroke-dashoffset 300ms ease-out" }}
                    />
                  </svg>
                </div>
                <p className="text-[13px] text-[#6F685E]">
                  <span className="font-medium text-[#514A41]">Pantry Health:</span> {getHealthMessage(pantryHealthScore)}
                </p>
              </div>
            </div>

            <div
              className={`hero-ai-layer absolute inset-0 z-[2] flex items-center justify-center p-12 ${
                isInstantClosingAI ? "transition-none" : "transition-opacity duration-[260ms] ease-out"
              } ${
                isAIActive ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
              }`}
            >
              <div className="ai-content relative w-full max-w-[820px]">
                <div className="ai-header mb-[6px] flex items-center justify-between">
                  <span className="ai-label text-[12px] font-semibold tracking-[1px] text-[#2F6F5E]">PANTRY INSIGHT</span>
                  <button
                    type="button"
                    onClick={deactivateAI}
                    className="ai-close absolute right-10 top-8 border-b border-[rgba(47,111,94,0.2)] bg-transparent pb-0.5 text-[13px] font-medium text-[#4A4A4A]/60 transition-opacity hover:text-[#4A4A4A]"
                  >
                    Close
                  </button>
                </div>

                <div className="ai-main flex min-h-[220px] max-w-[820px] items-stretch">
                  <div
                    className={`ai-accent mr-5 w-1 rounded-[2px] bg-gradient-to-b from-[#2F6F5E] to-[#4B8F7B] shadow-[0_0_14px_rgba(47,111,94,0.28)] ${
                      isInstantClosingAI ? "transition-none" : "transition-[height] duration-[400ms] ease-out"
                    } ${
                      isAIActive ? "h-full" : "h-0"
                    }`}
                  />
                  <div className="ai-text">
                    <h2 className="ai-title mb-[18px] text-[34px] font-[650] tracking-[-0.2px] text-[#2A2A2A]">Here&apos;s what your pantry is telling you.</h2>
                    <div className="ai-divider mb-[22px] h-px w-20 bg-[rgba(47,111,94,0.2)]" />
                    <div id="ai-stream-container" className="ai-body max-w-[580px] whitespace-pre-line text-[16px] leading-[1.3] text-[#374151]">
                      {aiStreamText}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section className="mt-10 grid gap-6 lg:grid-cols-2">
            <div className={`rounded-[18px] bg-[#F1ECE5] px-6 py-[26px] ${SIGNAL_SHADOW}`}>
              <div className="mb-0.5 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <h2 className="signal-title relative pb-[10px] text-[18px] font-semibold tracking-[-0.01em] text-[#302B25] after:absolute after:bottom-0 after:left-0 after:h-[2px] after:w-8 after:rounded-[2px] after:bg-[rgba(47,111,94,0.35)] after:content-['']">
                    Use Soon
                  </h2>
                  <Select value={String(expiringDays)} onValueChange={(value) => setExpiringDays(Number(value))}>
                    <SelectTrigger className="h-8 w-[96px] rounded-[8px] border-[#DDD4C8] bg-white text-[13px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1">1 day</SelectItem>
                      <SelectItem value="3">3 days</SelectItem>
                      <SelectItem value="7">7 days</SelectItem>
                      <SelectItem value="14">14 days</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <Link href="/dashboard/kitchen" className="text-[13px] text-[#9A9287]">
                  View all
                </Link>
              </div>
              {expiringLoading ? (
                <div className="space-y-2.5">
                  <Skeleton className="h-6 w-full rounded-[10px]" />
                  <Skeleton className="h-6 w-full rounded-[10px]" />
                </div>
              ) : expiringError ? (
                <p className="text-[13px] text-[#7C7468]">Could not load expiring insights.</p>
              ) : expiringPreview.length === 0 ? (
                <div className="signal-empty flex items-center gap-[14px] px-1 py-3">
                  <span className="empty-ring relative h-[18px] w-[18px] shrink-0 rounded-full border-2 border-[#5A9A7E]">
                    <span className="absolute inset-1 rounded-full bg-[#5A9A7E]" />
                  </span>
                  <span className="empty-text min-w-0">
                    <span className="empty-title text-[14px] font-medium text-[#2F6F5E]">All good for now</span>
                    <span className="empty-subtext block text-[14px] text-[#6B7280]">
                      Nothing expiring in the next {expiringDays} day{expiringDays > 1 ? "s" : ""}.
                    </span>
                  </span>
                </div>
              ) : (
                <div className="space-y-3">
                  {expiringPreview.map((item) => {
                    const ringVariant = getUseSoonRingVariant(item.days_remaining);
                    return (
                      <Link
                        key={item.inventory_id}
                        href={`/dashboard/kitchen?ingredient=${encodeURIComponent(item.item_name)}`}
                        className="block"
                      >
                        <div className="signal-item flex items-center justify-between rounded-[14px] px-[14px] py-[10px] transition-[background,transform] duration-150 ease-out hover:translate-x-[2px] hover:bg-black/3">
                          <div className="signal-left flex min-w-0 items-center">
                            <span className="signal-ring relative mr-3 h-4 w-4 shrink-0 -translate-y-px rounded-full bg-[#E5E0DA]">
                              <span className={`absolute inset-0 rounded-full ${getSignalRingClass(ringVariant)}`} />
                              <span className="absolute inset-[3px] rounded-full bg-[#F1ECE5]" />
                            </span>
                            <span className="signal-item-name overflow-hidden text-ellipsis whitespace-nowrap text-[14px] font-medium tracking-[0.2px] text-[#2A2A2A]">
                              {item.item_name}
                            </span>
                          </div>
                          <span className="signal-meta text-[13px] text-[#6B7280]">{item.days_remaining <= 0 ? "Today" : `${item.days_remaining} days`}</span>
                        </div>
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>

            <div className={`running-low-card rounded-[18px] bg-[#F3ECE6] px-6 py-[26px] ${SIGNAL_SHADOW}`}>
              <div className="mb-0.5 flex items-center justify-between">
                <h2 className="signal-title relative pb-[10px] text-[18px] font-semibold tracking-[-0.01em] text-[#302B25] after:absolute after:bottom-0 after:left-0 after:h-[2px] after:w-8 after:rounded-[2px] after:bg-[rgba(47,111,94,0.35)] after:content-['']">
                  Running Low
                </h2>
                <Link href="/dashboard/restock" className="text-[13px] text-[#9A9287]">
                  View all
                </Link>
              </div>
              {restockLoading ? (
                <div className="space-y-2.5">
                  <Skeleton className="h-6 w-full rounded-[10px]" />
                  <Skeleton className="h-6 w-full rounded-[10px]" />
                </div>
              ) : restockError ? (
                <p className="text-[13px] text-[#7C7468]">Could not load stock insights.</p>
              ) : runningLowPreview.length === 0 ? (
                <p className="text-[13px] text-[#7C7468]">You&apos;re stocked up.</p>
              ) : (
                <div className="space-y-3">
                  {runningLowPreview.map((item) => (
                    <Link
                      key={item.item_id}
                      href="/dashboard/restock"
                      className="block"
                    >
                      <div className="signal-item flex items-center justify-between rounded-[14px] px-[14px] py-[10px] transition-[background,transform] duration-150 ease-out hover:translate-x-[2px] hover:bg-black/3">
                        <div className="signal-left flex min-w-0 items-center">
                          <span className="signal-ring relative mr-3 h-4 w-4 shrink-0 -translate-y-px rounded-full bg-[#E5E0DA]">
                            <span className={`absolute inset-0 rounded-full ${getSignalRingClass("low")}`} />
                            <span className="absolute inset-[3px] rounded-full bg-[#F3ECE6]" />
                          </span>
                          <span className="signal-item-name overflow-hidden text-ellipsis whitespace-nowrap text-[14px] font-medium tracking-[0.2px] text-[#2A2A2A]">
                            {item.item_name}
                          </span>
                        </div>
                        <span className="status-low rounded-full border border-[#F9D4D4] bg-[#FDECEC] px-[10px] py-1 text-[12px] font-medium text-[#B42318] opacity-90">
                          Low
                        </span>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </section>

          <section id="all-items" className="mt-14 rounded-[28px] bg-[#F7F3EE] p-8">
            <div className="space-y-1.5">
              <h2 className="text-[19px] font-semibold text-[#2F2A24]">All Ingredients</h2>
              <p className="text-[14px] text-[#6F685E]">Everything currently in your kitchen.</p>
            </div>

            <div className="mt-4 flex flex-col gap-2.5 md:flex-row md:items-center">
              <div className="relative min-w-0 flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#8A8378]" />
                <Input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search pantry items..."
                  className="h-10 rounded-[8px] border-[#DDD4C8] bg-white pl-9 text-[#3E372F] placeholder:text-[#8C8479]"
                />
              </div>
              <Select value={category} onValueChange={setCategory}>
                <SelectTrigger className="h-10 w-full rounded-[8px] border-[#DDD4C8] bg-white md:w-44">
                  <SelectValue placeholder="Category" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All categories</SelectItem>
                  {categories.map((entry) => (
                    <SelectItem key={entry} value={entry}>
                      {entry}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                variant={showExpiringOnly ? "default" : "outline"}
                className={`h-10 rounded-[12px] ${showExpiringOnly ? "bg-[#2F6F5E] text-white hover:bg-[#2A6254]" : "border-[#DDD4C8] bg-white text-[#5E574D]"}`}
                onClick={onToggleExpiringFilter}
              >
                Expiring
              </Button>
            </div>

            {showExpiringOnly && !expiringLoading && !expiringError && expiringRecommendations.length > 0 ? (
              <div className="mt-4 overflow-hidden rounded-[16px] border border-[#DCE9E3] bg-gradient-to-r from-[#FFFFFF] via-[#F7FBF9] to-[#EEF7F2] p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span className="relative flex h-2.5 w-2.5">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#2F6F5E]/35" />
                      <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-[#2F6F5E]" />
                    </span>
                    <p className="text-[12px] font-semibold uppercase tracking-[0.14em] text-[#2F6F5E]">
                      Expiry Intelligence Stream
                    </p>
                  </div>
                  <span className="text-[12px] text-[#5E6A63]">
                    {activeRecommendationIdx + 1}/{expiringRecommendations.length}
                  </span>
                </div>

                <div className="mt-3 grid gap-2">
                  {expiringRecommendations.map((recommendation, index) => {
                    const isActive = index === activeRecommendationIdx;
                    return (
                      <div
                        key={`${recommendation}-${index}`}
                        className={`rounded-[12px] border px-3 py-2 text-[13px] leading-relaxed transition-all duration-300 ${
                          isActive
                            ? "border-[#B7D5C8] bg-white/90 opacity-100 shadow-[0_8px_18px_rgba(47,111,94,0.08)]"
                            : "border-[#E6ECE8] bg-white/55 opacity-80"
                        }`}
                      >
                        <div className="flex items-start gap-2">
                          <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${isActive ? "bg-[#2F6F5E]" : "bg-[#AAB8B0]"}`} />
                          <p className="text-[#2F2A24]">{recommendation}</p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : null}

            <div className="mt-6">
              {(inventoryItemsLoading ||
                inventoryStatusLoading ||
                (showExpiringOnly && expiringLoading)) ? (
                <div className="grid gap-6 lg:grid-cols-2">
                  {[1, 2, 3, 4, 5, 6].map((item) => (
                    <Skeleton key={item} className="h-[176px] w-full rounded-[18px]" />
                  ))}
                </div>
              ) : inventoryItemsError || inventoryStatusError || (showExpiringOnly && expiringError) ? (
                <Alert variant="destructive">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>Failed to load pantry items.</AlertDescription>
                </Alert>
              ) : filteredItems.length === 0 ? (
                <div className="rounded-[18px] bg-white px-6 py-10 text-center text-[13px] text-[#6F685E]">No pantry items match these filters.</div>
              ) : (
                <div className="grid gap-6 lg:grid-cols-2">
                  {filteredItems.map((item) => {
                    const freshness = getFreshnessMeta(item.days_until_expiry);
                    return (
                      <Card
                        key={item.id}
                        className={`group rounded-[18px] border border-[#ECE5DD] bg-white ${ITEM_SHADOW} ${ITEM_HOVER_SHADOW} transition-all duration-150 hover:-translate-y-1`}
                      >
                        <CardContent className="p-5">
                          <div className="mb-5 flex items-start gap-3">
                            <h3 className="min-w-0 flex-1 break-words text-[16px] font-semibold text-[#1F2937] [overflow-wrap:anywhere]">
                              {item.item_name}
                            </h3>
                            <div className="flex items-center gap-2">
                              <Badge className={`${CATEGORY_CHIP} max-w-[120px] overflow-hidden text-ellipsis whitespace-nowrap`}>
                                {formatCategoryLabel(item.category)}
                              </Badge>
                              <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0 rounded-[8px] text-[#6F685E]" onClick={() => onDeleteItem(item)}>
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>
                          </div>

                          <div className="mb-5 flex items-center justify-between gap-2">
                            <p className="inline-flex items-center gap-1 text-[14px] font-medium text-[#6C655A]">
                              <Weight className="h-3.5 w-3.5" />
                              {item.is_depleted ? "Out of stock" : formatWeight(item.quantity_grams)}
                            </p>
                          </div>

                          <div>
                            <p className="mb-1 text-[12px] text-[#1F2937]/75">Freshness</p>
                            <div className="h-[8px] overflow-hidden rounded-[6px] bg-[#E6E1DA]">
                              <div
                                className={`h-[8px] rounded-[6px] ${freshness.fillClass}`}
                                style={{ width: `${freshness.width}%`, transition: "width 400ms ease-out" }}
                              />
                            </div>
                            <p className={`mt-1.5 text-[13px] ${item.days_until_expiry !== null && item.days_until_expiry < 0 ? "text-[#B42318]" : "text-[#6F685E]"}`}>
                              {getFreshnessText(item.days_until_expiry)}
                            </p>
                          </div>
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              )}
            </div>
          </section>
        </div>
      </div>

      <AddItemsDialog open={addItemsOpen} onOpenChange={setAddItemsOpen} />
      <ReceiptUpload open={receiptUploadOpen} onOpenChange={setReceiptUploadOpen} />
      <style jsx>{`
        @keyframes pantry-hero-drift {
          from {
            background-position: 0% 50%;
          }
          to {
            background-position: 100% 50%;
          }
        }

        .page-reveal {
          animation: pantry-page-reveal 220ms ease-out;
        }

        @keyframes pantry-page-reveal {
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

