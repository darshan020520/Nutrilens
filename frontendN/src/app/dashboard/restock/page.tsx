"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, Check, Copy, Download, Loader2, Minus, Plus, ShoppingBasket } from "lucide-react";
import { DashboardLayout } from "@/components/layouts/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { DashboardPageLoader, useInitialPageLoader } from "@/shared/components/states/DashboardPageLoader";
import { useBulkAddFromRestock } from "../inventory/hooks/useInventory";
import { useRestockList } from "../inventory/hooks/useTracking";
import { RestockItem } from "../inventory/types";
import { getRestockQueue, unqueueRestockIngredient, unqueueRestockItem } from "../inventory/restockQueue";
import { toast } from "sonner";

type GroupKey = "urgent" | "soon" | "optional";
type FilterKey = "all" | GroupKey;
const AI_SHOWN_SESSION_KEY = "restock_ai_shown";
const LEGACY_AI_SHOWN_SESSION_KEY = "restock_ai_shown_v2";

function formatQuantity(grams: number): string {
  if (grams >= 1000) return `${(grams / 1000).toFixed(1)} kg`;
  return `${Math.round(grams)} g`;
}

function normalize(value: string): string {
  return value.trim().toLowerCase();
}

function formatCategory(category: string): string {
  return category
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function getRunningOutText(item: RestockItem): string {
  const days = item.days_until_depleted;
  if (typeof days !== "number") return "";
  if (days <= 0) return "";
  if (days === 1) return "1 day left";
  return `${days} days left`;
}

function getUrgencyColor(item: RestockItem): string {
  const days = item.days_until_depleted;
  if (typeof days === "number") {
    if (days <= 0) return "#C55E58";
    if (days <= 2) return "#D8A352";
    if (days <= 5) return "#CDBE74";
    return "#6A9C7B";
  }
  if (item.priority === "urgent") return "#C55E58";
  if (item.priority === "soon") return "#D8A352";
  return "#6A9C7B";
}

function getGroupMeta(group: GroupKey): { title: string } {
  if (group === "urgent") {
    return {
      title: "Pick these up first",
    };
  }
  if (group === "soon") {
    return {
      title: "Next up",
    };
  }
  return {
    title: "Good to have",
  };
}

export default function RestockPage() {
  const { data, isLoading, error } = useRestockList();
  const bulkAdd = useBulkAddFromRestock();
  const heroRef = useRef<HTMLElement | null>(null);
  const { showLoader: showInitialLoader, isExiting: isLoaderExiting } = useInitialPageLoader(!isLoading, {
    showDelayMs: 0,
    minVisibleMs: 560,
    exitMs: 200,
  });

  const [activeFilter, setActiveFilter] = useState<FilterKey>("all");
  const [quantityByItemId, setQuantityByItemId] = useState<Record<number, number>>({});
  const [pulsingQuantityIds, setPulsingQuantityIds] = useState<Set<number>>(new Set());
  const [queuedItemIds, setQueuedItemIds] = useState<Set<number>>(new Set());
  const [queuedNames, setQueuedNames] = useState<Set<string>>(new Set());
  const [savingItemIds, setSavingItemIds] = useState<Set<number>>(new Set());
  const [purchasedItemIds, setPurchasedItemIds] = useState<Set<number>>(new Set());
  const [removingItemIds, setRemovingItemIds] = useState<Set<number>>(new Set());
  const [hiddenItemIds, setHiddenItemIds] = useState<Set<number>>(new Set());

  const [isAIActive, setIsAIActive] = useState(false);
  const [isAITabInvite, setIsAITabInvite] = useState(false);
  const [isInstantClosingAI, setIsInstantClosingAI] = useState(false);
  const [aiStreamText, setAiStreamText] = useState("");

  const streamStartTimerRef = useRef<number | null>(null);
  const streamCharTimerRef = useRef<number | null>(null);
  const streamFoldTimerRef = useRef<number | null>(null);
  const streamAutoOpenTimerRef = useRef<number | null>(null);
  const hasAttemptedAutoOpenRef = useRef(false);
  const aiInsightTextRef = useRef("");
  const timeoutRefs = useRef<number[]>([]);

  useEffect(() => {
    const queue = getRestockQueue();
    setQueuedItemIds(new Set(queue.itemIds));
    setQueuedNames(new Set(queue.ingredientNames.map(normalize)));
  }, []);

  useEffect(() => {
    // Keep session gating deterministic on a single key.
    // Legacy key is cleanup-only and must never suppress auto-open.
    sessionStorage.removeItem(LEGACY_AI_SHOWN_SESSION_KEY);
  }, []);

  const groupedItems = useMemo(() => {
    return {
      urgent: data?.urgent_items ?? [],
      soon: data?.soon_items ?? [],
      optional: data?.routine_items ?? [],
    };
  }, [data?.routine_items, data?.soon_items, data?.urgent_items]);

  const visibleItemsByGroup = useMemo(() => {
    return {
      urgent: groupedItems.urgent.filter((item) => !hiddenItemIds.has(item.item_id)),
      soon: groupedItems.soon.filter((item) => !hiddenItemIds.has(item.item_id)),
      optional: groupedItems.optional.filter((item) => !hiddenItemIds.has(item.item_id)),
    };
  }, [groupedItems.optional, groupedItems.soon, groupedItems.urgent, hiddenItemIds]);

  const filteredGroups = useMemo(() => {
    if (activeFilter === "all") return visibleItemsByGroup;
    return {
      urgent: activeFilter === "urgent" ? visibleItemsByGroup.urgent : [],
      soon: activeFilter === "soon" ? visibleItemsByGroup.soon : [],
      optional: activeFilter === "optional" ? visibleItemsByGroup.optional : [],
    };
  }, [activeFilter, visibleItemsByGroup]);

  const remainingItems = visibleItemsByGroup.urgent.length + visibleItemsByGroup.soon.length + visibleItemsByGroup.optional.length;
  const pickedUpCount = hiddenItemIds.size;
  const totalForSession = remainingItems + pickedUpCount;
  const urgentCount = visibleItemsByGroup.urgent.length;
  const progressPercent = totalForSession > 0 ? Math.min(100, (pickedUpCount / totalForSession) * 100) : 0;

  const hasVisibleItems = filteredGroups.urgent.length + filteredGroups.soon.length + filteredGroups.optional.length > 0;

  const filterPills: Array<{ key: FilterKey; label: string; count: number }> = [
    { key: "all", label: "All", count: remainingItems },
    { key: "urgent", label: "Today", count: visibleItemsByGroup.urgent.length },
    { key: "soon", label: "Soon", count: visibleItemsByGroup.soon.length },
    { key: "optional", label: "Later", count: visibleItemsByGroup.optional.length },
  ];

  const aiLines = useMemo(() => {
    const fromBackend = (data?.shopping_strategy ?? [])
      .map((line) => line.trim())
      .filter((line) => line.length > 0)
      .slice(0, 2);

    if (fromBackend.length > 0) return fromBackend;
    if (totalForSession === 0) return ["Your shopping list is clear for now."];

    return [
      `Start with ${urgentCount} urgent item${urgentCount === 1 ? "" : "s"} to prevent stock gaps.`,
      "Pick produce in smaller batches to keep it fresh longer.",
      "Prioritize staples you use daily before optional add-ons.",
    ];
  }, [data?.shopping_strategy, totalForSession, urgentCount]);

  const aiInsightText = useMemo(() => aiLines.join("\n\n"), [aiLines]);

  useEffect(() => {
    aiInsightTextRef.current = aiInsightText;
  }, [aiInsightText]);

  const queueTimeout = (callback: () => void, delay: number) => {
    const timerId = window.setTimeout(callback, delay);
    timeoutRefs.current.push(timerId);
  };

  const showAddedToast = useCallback((itemName: string) => {
    toast.custom(
      () => (
        <div className="flex min-w-[260px] items-center gap-3 rounded-xl border border-[#DDE7E1] bg-[#F7FBF8] px-3 py-2.5 text-[#2F2A24] shadow-[0_10px_24px_rgba(0,0,0,0.08)]">
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-[#E6F3EC] text-[#2F6F5E] animate-pulse">
            <ShoppingBasket className="h-4 w-4" />
          </span>
          <div className="min-w-0">
            <p className="truncate text-[13px] font-semibold text-[#2F6F5E]">Added to pantry</p>
            <p className="truncate text-[12px] text-[#615A4F]">{itemName}</p>
          </div>
          <span className="ml-auto inline-flex h-6 w-6 items-center justify-center rounded-full bg-[#2F6F5E] text-white">
            <Check className="h-3.5 w-3.5" />
          </span>
        </div>
      ),
      { duration: 2000, position: "bottom-center" }
    );
  }, []);

  const clearAITimers = useCallback(() => {
    if (streamStartTimerRef.current !== null) {
      window.clearTimeout(streamStartTimerRef.current);
      streamStartTimerRef.current = null;
    }
    if (streamCharTimerRef.current !== null) {
      window.clearTimeout(streamCharTimerRef.current);
      streamCharTimerRef.current = null;
    }
    if (streamFoldTimerRef.current !== null) {
      window.clearTimeout(streamFoldTimerRef.current);
      streamFoldTimerRef.current = null;
    }
    if (streamAutoOpenTimerRef.current !== null) {
      window.clearTimeout(streamAutoOpenTimerRef.current);
      streamAutoOpenTimerRef.current = null;
    }
  }, []);

  const streamText = useCallback((text: string, onComplete?: () => void) => {
    setAiStreamText("");
    const chars = Array.from(text);
    let idx = 0;

    const writeNext = () => {
      if (idx >= chars.length) {
        streamCharTimerRef.current = null;
        onComplete?.();
        return;
      }

      const ch = chars[idx];
      setAiStreamText((prev) => prev + ch);

      let delay = 5;
      if (ch === ",") delay = 20;
      if (ch === ".") delay = 50;
      if (ch === "\n") delay = 50;
      delay += 1;

      idx += 1;
      streamCharTimerRef.current = window.setTimeout(writeNext, delay);
    };

    writeNext();
  }, []);

  const autoFoldAI = useCallback(() => {
    setIsAIActive(false);
    setIsAITabInvite(true);
  }, []);

  const activateAI = useCallback((auto = false, text?: string) => {
    const textToStream = text ?? aiInsightTextRef.current;
    clearAITimers();
    setIsInstantClosingAI(false);
    setIsAIActive(true);
    setIsAITabInvite(false);
    setAiStreamText("");

    streamStartTimerRef.current = window.setTimeout(() => {
      streamText(textToStream, () => {
        if (auto) {
          streamFoldTimerRef.current = window.setTimeout(() => {
            autoFoldAI();
            streamFoldTimerRef.current = null;
          }, 1000);
        }
      });
      streamStartTimerRef.current = null;
    }, 100);
  }, [autoFoldAI, clearAITimers, streamText]);

  const deactivateAI = useCallback(() => {
    clearAITimers();
    setIsAIActive(false);
    setAiStreamText("");
  }, [clearAITimers]);

  const forceDeactivateAI = useCallback(() => {
    clearAITimers();
    setIsInstantClosingAI(true);
    setIsAIActive(false);
    setAiStreamText("");
    setIsAITabInvite(false);
    window.setTimeout(() => setIsInstantClosingAI(false), 0);
  }, [clearAITimers]);

  useEffect(() => {
    if (isLoading || isAIActive) return;
    if (showInitialLoader) return;
    if (!aiInsightText.trim()) return;
    if (streamAutoOpenTimerRef.current !== null) return;

    const hasShownAI = sessionStorage.getItem(AI_SHOWN_SESSION_KEY) === "true";
    if (hasShownAI) {
      hasAttemptedAutoOpenRef.current = true;
      return;
    }
    if (hasAttemptedAutoOpenRef.current) {
      return;
    }

    streamAutoOpenTimerRef.current = window.setTimeout(() => {
      activateAI(true, aiInsightText);
      sessionStorage.setItem(AI_SHOWN_SESSION_KEY, "true");
      hasAttemptedAutoOpenRef.current = true;
      streamAutoOpenTimerRef.current = null;
    }, 400);
  }, [activateAI, aiInsightText, isAIActive, isLoading, showInitialLoader]);

  useEffect(() => {
    if (!isAIActive) return;
    const heroEl = heroRef.current;
    if (!heroEl) return;

    const handleScroll = () => {
      const rect = heroEl.getBoundingClientRect();
      if (rect.height < 80) return;
      const height = rect.height || 1;
      const visibleHeight = Math.max(0, Math.min(rect.bottom, window.innerHeight) - Math.max(rect.top, 0));
      const visibleRatio = visibleHeight / height;
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
    return () => {
      timeoutRefs.current.forEach((timerId) => window.clearTimeout(timerId));
      timeoutRefs.current = [];
      clearAITimers();
    };
  }, [clearAITimers]);

  const getSelectedQuantity = (item: RestockItem): number => quantityByItemId[item.item_id] ?? item.recommended_quantity;

  const pulseQuantity = (itemId: number) => {
    setPulsingQuantityIds((previous) => {
      const next = new Set(previous);
      next.add(itemId);
      return next;
    });

    queueTimeout(() => {
      setPulsingQuantityIds((previous) => {
        const next = new Set(previous);
        next.delete(itemId);
        return next;
      });
    }, 160);
  };

  const updateQuantity = (item: RestockItem, delta: number) => {
    if (savingItemIds.has(item.item_id) || removingItemIds.has(item.item_id)) return;
    const current = getSelectedQuantity(item);
    const next = Math.max(10, current + delta);

    setQuantityByItemId((previous) => ({
      ...previous,
      [item.item_id]: next,
    }));
    pulseQuantity(item.item_id);
  };

  const copyList = () => {
    const rows = [...visibleItemsByGroup.urgent, ...visibleItemsByGroup.soon, ...visibleItemsByGroup.optional];
    if (rows.length === 0) return;
    const text = rows.map((item) => `${item.item_name} - ${formatQuantity(getSelectedQuantity(item))}`).join("\n");
    navigator.clipboard.writeText(text);
    toast.success("Shopping list copied");
  };

  const exportList = () => {
    const rows = [...visibleItemsByGroup.urgent, ...visibleItemsByGroup.soon, ...visibleItemsByGroup.optional];
    if (rows.length === 0) return;
    const text = rows.map((item) => `- ${item.item_name} - ${formatQuantity(getSelectedQuantity(item))}`).join("\n");
    const blob = new Blob([`Shopping List\n\n${text}`], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `shopping-list-${new Date().toISOString().slice(0, 10)}.txt`;
    anchor.click();
    URL.revokeObjectURL(url);
    toast.success("Shopping list exported");
  };

  const markAsPurchased = async (item: RestockItem) => {
    const itemId = item.item_id;
    if (savingItemIds.has(itemId) || hiddenItemIds.has(itemId)) return;

    const quantity = getSelectedQuantity(item);

    setSavingItemIds((previous) => {
      const next = new Set(previous);
      next.add(itemId);
      return next;
    });
    setPurchasedItemIds((previous) => {
      const next = new Set(previous);
      next.add(itemId);
      return next;
    });

    try {
      await bulkAdd.mutateAsync({
        items: [{ item_id: item.item_id, quantity_grams: quantity }],
        suppressToast: true,
      });

      const normalizedName = normalize(item.item_name);

      if (queuedItemIds.has(item.item_id)) {
        unqueueRestockItem(item.item_id);
        setQueuedItemIds((previous) => {
          const next = new Set(previous);
          next.delete(item.item_id);
          return next;
        });
      }

      if (queuedNames.has(normalizedName)) {
        unqueueRestockIngredient(normalizedName);
        setQueuedNames((previous) => {
          const next = new Set(previous);
          next.delete(normalizedName);
          return next;
        });
      }

      showAddedToast(item.item_name);

      queueTimeout(() => {
        setRemovingItemIds((previous) => {
          const next = new Set(previous);
          next.add(itemId);
          return next;
        });
      }, 120);

      queueTimeout(() => {
        setHiddenItemIds((previous) => {
          const next = new Set(previous);
          next.add(itemId);
          return next;
        });
        setRemovingItemIds((previous) => {
          const next = new Set(previous);
          next.delete(itemId);
          return next;
        });
        setPurchasedItemIds((previous) => {
          const next = new Set(previous);
          next.delete(itemId);
          return next;
        });
      }, 420);
    } catch {
      setPurchasedItemIds((previous) => {
        const next = new Set(previous);
        next.delete(itemId);
        return next;
      });
      setRemovingItemIds((previous) => {
        const next = new Set(previous);
        next.delete(itemId);
        return next;
      });
    } finally {
      setSavingItemIds((previous) => {
        const next = new Set(previous);
        next.delete(itemId);
        return next;
      });
    }
  };

  if (showInitialLoader) {
    return (
      <DashboardLayout>
        <div className="min-h-full bg-[#F7F5F1]">
          <div className="mx-auto max-w-[1200px] space-y-8 px-8 pb-12 pt-2 text-[#2F2A24]">
            <DashboardPageLoader scene="restock" isExiting={isLoaderExiting} />
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="min-h-full bg-[#F7F5F1] page-reveal">
        <div className="mx-auto max-w-[1200px] space-y-8 px-8 pb-12 pt-2 text-[#2F2A24]">
          <section
            ref={heroRef}
            className={`hero-wrapper relative flex flex-col justify-between overflow-hidden rounded-[22px] border border-[#ECE3D6] bg-gradient-to-br from-[#F8F5F0] to-[#EEE8DE] p-8 shadow-[0_6px_20px_rgba(0,0,0,0.05),0_24px_42px_rgba(0,0,0,0.05)] ${
              isInstantClosingAI ? "transition-none" : "transition-[background,box-shadow] duration-300"
            } ${
              isAIActive ? "bg-[linear-gradient(120deg,#F8F4ED_0%,#EFE7DD_100%)] bg-[length:200%_200%] [animation:restock-hero-drift_10s_ease_infinite_alternate]" : ""
            }`}
          >
            <button
              type="button"
              onClick={() => (isAIActive ? deactivateAI() : activateAI(false))}
              className={`absolute right-4 top-1/2 z-20 -translate-y-1/2 rounded-[12px] border px-2 py-3 text-[11px] font-semibold uppercase tracking-[0.12em] transition-all duration-260 [writing-mode:vertical-rl] ${
                isAIActive
                  ? "border-[#2F6F5E] bg-[#EFE9E1] text-[#2F6F5E] shadow-[0_0_0_4px_rgba(47,111,94,0.12)]"
                  : isAITabInvite
                    ? "border-[#2F6F5E] bg-[#F3EFE9] text-[#2F6F5E]"
                    : "border-[#D9D2C8] bg-[#F6F2EC] text-[#455448]"
              }`}
            >
              AI Insight
            </button>

            <div className={`hero-default-layer flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between ${
              isInstantClosingAI ? "transition-none" : "transition-[opacity,transform] duration-260"
            } ${isAIActive ? "pointer-events-none -translate-y-[10px] opacity-0" : "opacity-100"}`}>
              <div>
                <p className="hero-eyebrow text-[12px] uppercase tracking-[0.12em] text-[#6B7280]">Shopping List</p>
                <h1 className="hero-title mt-2 text-[34px] font-semibold tracking-[-0.01em] text-[#2A2A2A]">
                  Everything you need today.
                </h1>
                <p className="hero-meta mt-1.5 text-[13px] font-medium text-[#6B7280]">{remainingItems} items &middot; {urgentCount} urgent</p>
              </div>

              <div className="w-full max-w-[280px] space-y-3">
                <p className="text-[13px] text-[#655E54]">{pickedUpCount} / {totalForSession} picked up</p>
                <div className="h-[6px] overflow-hidden rounded-full bg-[#DDD5C9]">
                  <div
                    className="h-[6px] rounded-full bg-gradient-to-r from-[#2F6F5E] to-[#5A9A7E] transition-[width] duration-300 ease-out"
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>
                <div className="flex justify-start gap-1 pt-1">
                  <Button variant="ghost" className="h-8 rounded-[10px] px-2.5 text-[#5B5348] hover:bg-white/55" onClick={copyList}>
                    <Copy className="mr-1.5 h-4 w-4" />
                    Copy
                  </Button>
                  <Button variant="ghost" className="h-8 rounded-[10px] px-2.5 text-[#5B5348] hover:bg-white/55" onClick={exportList}>
                    <Download className="mr-1.5 h-4 w-4" />
                    Export
                  </Button>
                </div>
              </div>
            </div>

            <div className={`hero-ai-layer absolute inset-0 z-10 flex items-start justify-center px-9 pb-6 pt-5 ${
              isInstantClosingAI ? "transition-none" : "transition-opacity duration-260"
            } ${isAIActive ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"}`}>
              <div className="relative w-full max-w-[820px] pt-1">
                <button
                  type="button"
                  onClick={deactivateAI}
                  className="absolute right-0 top-0 border-b border-[rgba(47,111,94,0.2)] bg-transparent pb-0.5 text-[13px] font-medium text-[#4A4A4A]/60 transition-opacity hover:text-[#4A4A4A]"
                >
                  Close
                </button>
                <p className="text-[12px] font-semibold uppercase tracking-[1px] text-[#2F6F5E]">AI Insight</p>
                <h2 className="mt-1 text-[24px] font-semibold leading-[1.15] tracking-[-0.01em] text-[#2A2A2A]">
                  Smart tips for today
                </h2>
                <div className="mt-2 flex max-w-[820px] items-start">
                  <span className="mr-5 mt-1 h-[130px] w-[4px] shrink-0 rounded-[2px] bg-gradient-to-b from-[#2F6F5E] to-[#4B8F7B] shadow-[0_0_14px_rgba(47,111,94,0.28)]" />
                  <div
                    className="max-w-[580px] whitespace-pre-line text-[14px] leading-[1.3] text-[#374151]"
                  >
                    {aiStreamText}
                  </div>
                </div>
              </div>
            </div>
          </section>

          <div className="flex flex-wrap gap-2 pt-4">
            {filterPills.map((pill) => (
              <button
                key={pill.key}
                type="button"
                onClick={() => setActiveFilter(pill.key)}
                className={`rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-all duration-200 ${
                  activeFilter === pill.key
                    ? "bg-[#2F6F5E] text-white shadow-[0_6px_12px_rgba(47,111,94,0.22)]"
                    : "bg-white/85 text-[#5D554A] hover:bg-white"
                }`}
              >
                {pill.label} <span className="opacity-80">{pill.count}</span>
              </button>
            ))}
          </div>

          {isLoading ? (
            <div className="space-y-3">
              <Skeleton className="h-40 w-full rounded-[16px]" />
              <Skeleton className="h-40 w-full rounded-[16px]" />
            </div>
          ) : error ? (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>Failed to load shopping list.</AlertDescription>
            </Alert>
          ) : (
            <div className="space-y-8">
              {(["urgent", "soon", "optional"] as GroupKey[]).map((groupKey) => {
                const rows = filteredGroups[groupKey];
                if (rows.length === 0) return null;
                const group = getGroupMeta(groupKey);

                return (
                  <section key={groupKey} className="space-y-4">
                    <div className="flex items-end justify-between gap-3">
                      <div>
                        <h2 className="text-[21px] font-semibold tracking-[-0.01em] text-[#2F2A24]">
                          {group.title} <span className="text-[16px] font-medium text-[#7B7468]">({rows.length})</span>
                        </h2>
                      </div>
                    </div>

                    <div className="grid gap-x-6 gap-y-0 md:grid-cols-2">
                      {rows.map((item) => {
                        const quantity = getSelectedQuantity(item);
                        const runningOutText = getRunningOutText(item);
                        const isPulsing = pulsingQuantityIds.has(item.item_id);
                        const isSaving = savingItemIds.has(item.item_id);
                        const isPurchased = purchasedItemIds.has(item.item_id);
                        const isRemoving = removingItemIds.has(item.item_id);
                        const urgencyColor = getUrgencyColor(item);

                        return (
                          <article
                            key={`${groupKey}-${item.item_id}`}
                            className={`restock-item relative mb-5 overflow-hidden rounded-[18px] border border-[#ECE3D6] bg-[#FAF7F2] px-[22px] py-[22px] shadow-[0_8px_20px_rgba(0,0,0,0.05)] transition-[opacity,transform,box-shadow] duration-300 ${
                              isRemoving ? "-translate-y-[6px] opacity-0" : isPurchased ? "opacity-70" : "opacity-100 hover:-translate-y-[2px] hover:shadow-[0_10px_25px_rgba(0,0,0,0.05)]"
                            }`}
                          >
                            <div className="space-y-4">
                              <div className="min-w-0">
                                <div className="flex items-center">
                                  <span className="urgency-dot mr-3 h-2.5 w-2.5 shrink-0 translate-y-px rounded-full" style={{ backgroundColor: urgencyColor }} />
                                  <h3 className="truncate text-[18px] font-semibold text-[#2A2A2A]">
                                    {item.item_name || "Unnamed item"}
                                  </h3>
                                </div>
                                <p className="mt-1 text-[13px] text-[#6C645A]">{formatCategory(item.category)}</p>
                              </div>

                              {runningOutText ? <p className="text-[14px] text-[#4E473F]">{runningOutText}</p> : null}

                              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                                <div>
                                  <p className="mb-1 text-[12px] text-[#7A7165]">Buy</p>
                                  <div className="qty-control inline-flex items-center rounded-full bg-[#F3F4F6] p-1">
                                    <button
                                      type="button"
                                      onClick={() => updateQuantity(item, -10)}
                                      disabled={isSaving || isPurchased}
                                      className="h-8 w-8 rounded-full bg-white text-[#5A5247] shadow-[0_1px_2px_rgba(0,0,0,0.06)] transition-transform duration-150 hover:bg-[#FCFCFC] active:scale-95 disabled:opacity-50"
                                      aria-label={`Decrease ${item.item_name} quantity`}
                                    >
                                      <Minus className="mx-auto h-4 w-4" />
                                    </button>

                                    <span className={`mx-3 inline-block min-w-[78px] text-center text-[14px] font-medium text-[#3E372F] transition-all duration-150 ${isPulsing ? "scale-110 opacity-100" : "scale-100 opacity-90"}`}>
                                      {formatQuantity(quantity)}
                                    </span>

                                    <button
                                      type="button"
                                      onClick={() => updateQuantity(item, 10)}
                                      disabled={isSaving || isPurchased}
                                      className="h-8 w-8 rounded-full bg-white text-[#5A5247] shadow-[0_1px_2px_rgba(0,0,0,0.06)] transition-transform duration-150 hover:bg-[#FCFCFC] active:scale-95 disabled:opacity-50"
                                      aria-label={`Increase ${item.item_name} quantity`}
                                    >
                                      <Plus className="mx-auto h-4 w-4" />
                                    </button>
                                  </div>
                                </div>

                                <Button
                                  onClick={() => void markAsPurchased(item)}
                                  disabled={isSaving || isRemoving || hiddenItemIds.has(item.item_id)}
                                  className={`purchased-btn h-8 rounded-full px-[14px] text-[13px] transition-all duration-200 ${
                                    isPurchased || isSaving
                                      ? "bg-[#2F6F5E] text-white hover:bg-[#2A6254]"
                                      : "border border-[#D9D4CA] bg-white text-[#514A40] hover:bg-[#FBFAF7]"
                                  }`}
                                >
                                  {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Check className="mr-2 h-4 w-4" />}
                                  {isPurchased ? "Added" : "Purchased"}
                                </Button>
                              </div>
                            </div>
                          </article>
                        );
                      })}
                    </div>
                  </section>
                );
              })}

              {!hasVisibleItems ? (
                <div className="rounded-[18px] border border-[#E6DED0] bg-[#FBF8F2] px-6 py-10 text-center">
                  <p className="text-[15px] font-medium text-[#4E463B]">You&apos;re done for now.</p>
                  <p className="mt-1 text-[13px] text-[#71695D]">No items left for this filter.</p>
                </div>
              ) : null}
            </div>
          )}
        </div>
      </div>
      <style jsx>{`
        @keyframes restock-hero-drift {
          from {
            background-position: 0% 50%;
          }
          to {
            background-position: 100% 50%;
          }
        }

        .page-reveal {
          animation: restock-page-reveal 220ms ease-out;
        }

        @keyframes restock-page-reveal {
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
