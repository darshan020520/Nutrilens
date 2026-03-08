"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { DashboardLayout } from "@/components/layouts/DashboardLayout";
import { ChevronDown, Loader2 } from "lucide-react";
import { DashboardPageLoader, useInitialPageLoader } from "@/shared/components/states/DashboardPageLoader";
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
  Cell,
} from "recharts";
import { api, getEndpoint } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────────

type HistoryMeal = { status: string };
type HistoryDay = { date: string; meals?: HistoryMeal[] };
type HistoryResponse = {
  history?: HistoryDay[];
  statistics?: { adherence_rate?: number; logged_meals?: number };
};
type TodaySummaryResponse = {
  total_macros?: { calories?: number; protein_g?: number; carbs_g?: number; fat_g?: number };
  target_macros?: { calories?: number; protein_g?: number; carbs_g?: number; fat_g?: number };
};
type DashboardSummaryResponse = {
  macros_card?: { protein_percentage?: number; carbs_percentage?: number; fat_percentage?: number };
};
type NutritionChatResponse = { response?: string };
type ChatMessage = { role: "user" | "assistant"; content: string; timestamp: number };

// ── Helpers ────────────────────────────────────────────────────────────────

const clampPercent = (v: number) => Math.max(0, Math.min(100, v));
const ratioToPercent = (cur: number, tgt: number) => (tgt <= 0 ? 0 : clampPercent((cur / tgt) * 100));

const normalizeAssistantText = (text: string) =>
  text
    .replace(/\r/g, "")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/^\s*[-*]\s+/gm, "- ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();

const hasReasoningContext = (text: string) => {
  const lower = text.toLowerCase();
  if (
    lower.includes("i could not process this request") ||
    lower.includes("how can i help") ||
    lower.startsWith("i am mr nutri")
  )
    return false;
  return /(protein|calorie|carb|fat|target|adherence|macro|swap|meal)/i.test(text);
};

const getContextActions = (text: string): { label: string; query: string }[] => {
  const lower = text.toLowerCase();
  if (lower.includes("protein"))
    return [
      { label: "Protein dinner", query: "Suggest a high-protein dinner that keeps calories controlled." },
      { label: "Protein snack", query: "Give me a high-protein snack option for today." },
      { label: "Swap for protein", query: "What meal swap improves my protein target?" },
    ];
  if (lower.includes("calorie"))
    return [
      { label: "Calorie-safe meal", query: "Suggest a meal under 500 calories with balanced macros." },
      { label: "Lower-calorie swap", query: "What can I swap to reduce calories today?" },
      { label: "Tonight plan", query: "Plan my remaining meals for today within calorie target." },
    ];
  if (lower.includes("swap"))
    return [
      { label: "Swap breakfast", query: "Suggest a breakfast swap with similar protein and fewer calories." },
      { label: "Swap lunch", query: "Suggest a lunch swap that helps macro balance." },
      { label: "Pantry swap", query: "Give me a pantry-based swap for my next meal." },
    ];
  return [
    { label: "Suggest dinner", query: "Suggest a dinner that keeps me on macro target." },
    { label: "High protein snack", query: "Give me a high-protein snack option for today." },
    { label: "Swap meal", query: "What meal should I swap to stay on target?" },
  ];
};

// ── SVG Icons (no emoji fallback risk) ─────────────────────────────────────

const NutriIcons = {
  utensils: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 002-2V2" /><path d="M7 2v20" /><path d="M21 15V2v0a5 5 0 00-5 5v6c0 1.1.9 2 2 2h3zm0 0v7" />
    </svg>
  ),
  target: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><circle cx="12" cy="12" r="6" /><circle cx="12" cy="12" r="2" />
    </svg>
  ),
  box: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z" />
      <polyline points="3.27 6.96 12 12.01 20.73 6.96" /><line x1="12" y1="22.08" x2="12" y2="12" />
    </svg>
  ),
  swap: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="17 1 21 5 17 9" /><path d="M3 11V9a4 4 0 014-4h14" />
      <polyline points="7 23 3 19 7 15" /><path d="M21 13v2a4 4 0 01-4 4H3" />
    </svg>
  ),
};

// ── Sub-components ─────────────────────────────────────────────────────────

function MacroRing({
  value,
  max,
  color,
  size = 52,
  strokeW = 4.5,
}: {
  value: number;
  max: number;
  color: string;
  size?: number;
  strokeW?: number;
}) {
  const pct = max > 0 ? Math.min(value / max, 1) : 0;
  const r = (size - strokeW) / 2;
  const circ = 2 * Math.PI * r;
  return (
    <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#eeede9" strokeWidth={strokeW} />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={strokeW}
        strokeDasharray={circ}
        strokeDashoffset={circ * (1 - pct)}
        strokeLinecap="round"
        style={{ transition: "stroke-dashoffset 0.8s cubic-bezier(.4,0,.2,1)" }}
      />
    </svg>
  );
}

function TypingIndicator() {
  return (
    <div style={{ display: "flex", gap: 5, padding: "10px 0", alignItems: "center" }}>
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          style={{
            width: 7,
            height: 7,
            borderRadius: "50%",
            background: "#1B7D5A",
            opacity: 0.7,
            animation: `nlDotBounce 1.2s ease-in-out ${i * 0.15}s infinite`,
          }}
        />
      ))}
    </div>
  );
}

function SuggestionCard({
  text,
  desc,
  icon,
  onClick,
  delay = 0,
}: {
  text: string;
  desc: string;
  icon: React.ReactNode;
  onClick: () => void;
  delay?: number;
}) {
  const [hovered, setHovered] = useState(false);
  return (
    <button
      type="button"
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: 11,
        padding: "12px 14px",
        border: `1px solid ${hovered ? "#c8ddd3" : "#e8e8e4"}`,
        borderRadius: 14,
        background: hovered ? "#f6faf8" : "#fff",
        cursor: "pointer",
        textAlign: "left",
        transition: "all 0.2s ease",
        fontFamily: "inherit",
        boxShadow: hovered ? "0 4px 16px rgba(27,125,90,0.08)" : "0 1px 3px rgba(0,0,0,0.03)",
        transform: hovered ? "translateY(-2px)" : "none",
        animation: `nlFloatIn 0.4s ease ${delay}s both`,
        width: "100%",
      }}
    >
      <div
        style={{
          width: 34,
          height: 34,
          borderRadius: 9,
          background: hovered ? "rgba(27,125,90,0.1)" : "#f5f5f2",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
          color: "#1B7D5A",
          transition: "background 0.2s",
        }}
      >
        {icon}
      </div>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 13.5, fontWeight: 500, color: "#1a1a1a", lineHeight: 1.4 }}>{text}</div>
        <div style={{ fontSize: 11.5, color: "#aaa", marginTop: 2, lineHeight: 1.35 }}>{desc}</div>
      </div>
    </button>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────

export default function NutritionPage() {
  const [aiQuery, setAiQuery] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [showPanel, setShowPanel] = useState(false);
  const [showAnalytics, setShowAnalytics] = useState(false);
  const [inputFocused, setInputFocused] = useState(false);

  // ✅ FIX 1: Start with empty messages — no initial greeting
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);

  const isEmptyState = chatMessages.length === 0;

  const chatScrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const [aiSessionId] = useState(() => {
    if (typeof window === "undefined") return `nutrition-dashboard-${Date.now()}-ssr`;
    const storageKey = "nutrilens:nutrition-dashboard:session";
    const existing = window.localStorage.getItem(storageKey);
    if (existing) return existing;
    const created = `nutrition-dashboard-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    window.localStorage.setItem(storageKey, created);
    return created;
  });

  // ── Data fetching (unchanged) ──────────────────────────────────────────

  const {
    data: todayData,
    isLoading: todayLoading,
    refetch: refetchToday,
  } = useQuery<TodaySummaryResponse>({
    queryKey: ["tracking", "today"],
    queryFn: async () => (await api.get(getEndpoint("/tracking/today"))).data,
    staleTime: 30 * 1000,
  });

  const {
    data: historyData,
    isLoading: historyLoading,
    refetch: refetchHistory,
  } = useQuery<HistoryResponse>({
    queryKey: ["tracking", "history", 7],
    queryFn: async () => (await api.get(getEndpoint("/tracking/history"), { params: { days: 7 } })).data,
    staleTime: 60 * 1000,
  });

  const {
    data: summaryData,
    isLoading: summaryLoading,
    refetch: refetchSummary,
  } = useQuery<DashboardSummaryResponse>({
    queryKey: ["dashboard-summary"],
    queryFn: async () => (await api.get(getEndpoint("/dashboard/summary"))).data,
    staleTime: 60 * 1000,
  });

  const isNutritionReady = !todayLoading && !historyLoading && !summaryLoading;
  const { showLoader: showInitialLoader, isExiting: isLoaderExiting } = useInitialPageLoader(
    isNutritionReady,
    { showDelayMs: 0, minVisibleMs: 500, exitMs: 200 }
  );

  // ── Derived values ─────────────────────────────────────────────────────

  const macroTrend = useMemo(() => {
    const rows = historyData?.history ?? [];
    return rows.map((day: HistoryDay) => {
      const logged = day.meals?.filter((m) => m.status === "logged")?.length ?? 0;
      const total = day.meals?.length ?? 0;
      const adherence = total > 0 ? Math.round((logged / total) * 100) : 0;
      return {
        date: new Date(day.date).toLocaleDateString("en-US", { weekday: "short" }),
        adherence,
      };
    });
  }, [historyData]);

  const caloriesToday = Math.round(todayData?.total_macros?.calories ?? 0);
  const caloriesTarget = Math.round(todayData?.target_macros?.calories ?? 0);
  const proteinToday = Math.round(todayData?.total_macros?.protein_g ?? 0);
  const proteinTarget = Math.round(todayData?.target_macros?.protein_g ?? 0);
  const carbsToday = Math.round(todayData?.total_macros?.carbs_g ?? 0);
  const carbsTarget = Math.round(todayData?.target_macros?.carbs_g ?? 0);
  const fatToday = Math.round(todayData?.total_macros?.fat_g ?? 0);
  const fatTarget = Math.round(todayData?.target_macros?.fat_g ?? 0);
  const weeklyAdherence = Math.round(historyData?.statistics?.adherence_rate ?? 0);

  const caloriesProgress = ratioToPercent(caloriesToday, caloriesTarget);
  const proteinProgress = ratioToPercent(proteinToday, proteinTarget);

  const macroDistribution = [
    { name: "Protein", value: Math.round(summaryData?.macros_card?.protein_percentage ?? 0), fill: "#34D399" },
    { name: "Carbs", value: Math.round(summaryData?.macros_card?.carbs_percentage ?? 0), fill: "#60A5FA" },
    { name: "Fat", value: Math.round(summaryData?.macros_card?.fat_percentage ?? 0), fill: "#FBBF24" },
  ];
  const hasMacroData = macroDistribution.some((item) => item.value > 0);

  const macros = {
    calories: { current: caloriesToday, target: caloriesTarget, color: "#E8913A", unit: "kcal" },
    protein: { current: proteinToday, target: proteinTarget, color: "#1B7D5A", unit: "g" },
    carbs: { current: carbsToday, target: carbsTarget, color: "#5B8DEF", unit: "g" },
    fats: { current: fatToday, target: fatTarget, color: "#D4638F", unit: "g" },
  };

  // ✅ FIX 3: Richer suggestions with SVG icons + descriptions, 4 items for 2×2 grid
  const suggestions = [
    { text: "What should I eat for dinner?", desc: "Based on remaining macros", icon: NutriIcons.utensils },
    { text: "High-protein meals from my pantry", desc: "Using what's in stock", icon: NutriIcons.box },
    { text: "Am I on track with my macros?", desc: "Today's progress check", icon: NutriIcons.target },
    { text: "Swap a meal for lower calories", desc: "Find lighter alternatives", icon: NutriIcons.swap },
  ];

  const contextTags = ["Meal plan", "Pantry", "Macros", "Goals", "Logs"];

  // ── Chat handlers ──────────────────────────────────────────────────────

  const signalRefresh = () =>
    void Promise.allSettled([refetchToday(), refetchHistory(), refetchSummary()]);

  const runNutritionQuery = async (query: string) => {
    const normalized = query.trim();
    if (!normalized || aiLoading) return;

    setChatMessages((prev) => [...prev, { role: "user", content: normalized, timestamp: Date.now() }]);
    setAiLoading(true);

    try {
      const response = await api.post<NutritionChatResponse>(getEndpoint("/nutrition/chat"), {
        query: normalized,
        include_context: true,
        session_id: aiSessionId,
      });
      setChatMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: normalizeAssistantText(
            response.data?.response?.trim() || "No response available for this query."
          ),
          timestamp: Date.now(),
        },
      ]);
    } catch {
      setChatMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "I could not process this request right now. Please try again.",
          timestamp: Date.now(),
        },
      ]);
    } finally {
      setAiLoading(false);
      signalRefresh();
      textareaRef.current?.focus();
    }
  };

  const onAskSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const submitted = aiQuery;
    setAiQuery("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
    await runNutritionQuery(submitted);
  };

  useEffect(() => {
    if (!chatScrollRef.current) return;
    chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
  }, [chatMessages, aiLoading]);

  // ── Early return: loader ───────────────────────────────────────────────

  if (showInitialLoader) {
    return (
      <DashboardLayout>
        <DashboardPageLoader scene="nutrition" isExiting={isLoaderExiting} />
      </DashboardLayout>
    );
  }

  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <DashboardLayout>
      <style>{`
        @keyframes nlDotBounce {
          0%, 80%, 100% { transform: translateY(0); }
          40% { transform: translateY(-6px); }
        }
        @keyframes nlFadeUp {
          from { opacity: 0; transform: translateY(14px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes nlSlideInRight {
          from { transform: translateX(20px); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
        @keyframes nlFadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes nlFloatIn {
          from { opacity: 0; transform: translateY(8px) scale(0.96); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
        .nl-textarea::placeholder { color: #b0b0a8; }
        .nl-suggestion-card:hover .nl-suggestion-icon { background: rgba(27,125,90,0.1) !important; }
      `}</style>

      {/* Break out of AppShell's p-4 md:p-6 padding */}
      <div className="-m-4 md:-m-6" style={{ display: "flex", height: "calc(100vh - 4rem)", overflow: "hidden", background: "#FAFAF8" }}>

        {/* ── Main Chat Area ── */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>

          {/* ── Top Bar ── */}
          <div style={{
            padding: "12px 28px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderBottom: "1px solid #eeede9",
            background: "rgba(250,250,248,0.9)",
            backdropFilter: "blur(12px)",
            flexShrink: 0,
            minHeight: 56,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 11 }}>
              <div style={{
                width: 32, height: 32, borderRadius: 9,
                background: "linear-gradient(135deg, #1B7D5A, #2AA876)",
                display: "flex", alignItems: "center", justifyContent: "center",
                boxShadow: "0 2px 6px rgba(27,125,90,0.2)",
              }}>
                <span style={{ color: "#fff", fontSize: 14, fontWeight: 700, fontFamily: "Georgia, serif" }}>N</span>
              </div>
              <div>
                <div style={{ fontSize: 14.5, fontWeight: 600, color: "#1a1a1a", letterSpacing: -0.3 }}>Mr Nutri</div>
                <div style={{ fontSize: 11, color: "#999", display: "flex", alignItems: "center", gap: 4, marginTop: -1 }}>
                  <span style={{ width: 5, height: 5, borderRadius: "50%", background: "#2AA876", display: "inline-block" }} />
                  Nutrition Intelligence
                </div>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setShowPanel(!showPanel)}
              style={{
                display: "flex", alignItems: "center", gap: 8,
                padding: "7px 14px",
                border: `1px solid ${showPanel ? "#c8ddd3" : "#e8e8e4"}`,
                borderRadius: 10,
                background: showPanel ? "rgba(27,125,90,0.04)" : "#fff",
                cursor: "pointer", fontSize: 12.5, color: "#555",
                fontFamily: "inherit", fontWeight: 500,
                transition: "all 0.2s",
              }}
            >
              <span style={{ color: "#E8913A", fontWeight: 600 }}>{caloriesToday || "0"}</span>
              <span style={{ color: "#d0d0cc", fontSize: 11 }}>/</span>
              <span style={{ color: "#999", fontSize: 12 }}>{caloriesTarget || "—"} kcal</span>
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" style={{ marginLeft: 2, color: showPanel ? "#1B7D5A" : "#aaa" }}>
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <line x1="15" y1="3" x2="15" y2="21" />
              </svg>
            </button>
          </div>

          {/* ── Chat Body ── */}
          <div
            ref={chatScrollRef}
            style={{
              flex: 1,
              overflowY: "auto",
              display: "flex",
              flexDirection: "column",
              padding: isEmptyState ? "12px 28px" : "28px 28px 12px",
              scrollbarWidth: "thin",
              scrollbarColor: "#d4d4d0 transparent",
            }}
          >
            {/* ✅ FIX 1 + 4 + 6: Clean empty state with branded avatar, heading, 2×2 suggestion grid */}
            {isEmptyState ? (
              <div style={{
                display: "flex", flexDirection: "column",
                alignItems: "center",
                paddingTop: "max(6vh, 24px)",
                paddingBottom: 24,
                maxWidth: 540, margin: "0 auto", width: "100%",
              }}>
                {/* Branded avatar */}
                <div style={{
                  width: 48, height: 48, borderRadius: 14,
                  background: "linear-gradient(135deg, #1B7D5A, #2AA876)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  marginBottom: 16,
                  boxShadow: "0 4px 20px rgba(27,125,90,0.2)",
                  animation: "nlFloatIn 0.4s ease both",
                }}>
                  <span style={{ color: "#fff", fontSize: 20, fontWeight: 700, fontFamily: "Georgia, serif" }}>N</span>
                </div>

                <h1 style={{
                  fontFamily: "Georgia, serif",
                  fontSize: 24, fontWeight: 500,
                  color: "#1a1a1a", letterSpacing: -0.5, marginBottom: 6,
                  textAlign: "center", lineHeight: 1.3,
                  animation: "nlFloatIn 0.4s ease 0.05s both",
                }}>
                  What&apos;s on your plate today?
                </h1>
                <p style={{
                  fontSize: 14, color: "#999", maxWidth: 380, textAlign: "center",
                  lineHeight: 1.55,
                  animation: "nlFloatIn 0.4s ease 0.1s both",
                }}>
                  I know your meal plan, pantry stock, and macro targets. Ask me anything.
                </p>

                {/* ✅ FIX 6: 2×2 grid with SVG icons + descriptions */}
                <div style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: 10,
                  marginTop: 24,
                  width: "100%",
                }}>
                  {suggestions.map((s, i) => (
                    <SuggestionCard
                      key={s.text}
                      text={s.text}
                      desc={s.desc}
                      icon={s.icon}
                      onClick={() => runNutritionQuery(s.text)}
                      delay={0.12 + i * 0.06}
                    />
                  ))}
                </div>
              </div>
            ) : (
              /* ── Active Chat Messages ── */
              <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 22 }}>
                {chatMessages.map((msg, i) => {
                  const isAI = msg.role === "assistant";
                  const isLast = i === chatMessages.length - 1;
                  const showReasoning = isAI && hasReasoningContext(msg.content);
                  const contextualActions = isAI ? getContextActions(msg.content) : [];

                  return (
                    <div
                      key={`${msg.timestamp}-${i}`}
                      style={{
                        display: "flex",
                        gap: 12,
                        maxWidth: 720,
                        marginLeft: isAI ? 0 : "auto",
                        animation: isLast ? "nlFadeUp 0.35s ease" : "none",
                        flexDirection: isAI ? "row" : "row-reverse",
                      }}
                    >
                      {isAI && (
                        <div style={{
                          width: 30, height: 30, borderRadius: 10,
                          background: "linear-gradient(135deg, #1B7D5A, #2AA876)",
                          display: "flex", alignItems: "center", justifyContent: "center",
                          flexShrink: 0, marginTop: 3,
                          boxShadow: "0 2px 8px rgba(27,125,90,0.2)",
                        }}>
                          <span style={{ color: "#fff", fontSize: 13, fontWeight: 700, fontFamily: "Georgia, serif" }}>N</span>
                        </div>
                      )}

                      <div style={{
                        padding: isAI ? "2px 4px" : "11px 16px",
                        background: isAI ? "transparent" : "#1B7D5A",
                        color: isAI ? "#2a2a2a" : "#fff",
                        borderRadius: isAI ? 0 : "18px 18px 4px 18px",
                        fontSize: 14, lineHeight: 1.75, letterSpacing: -0.1,
                        maxWidth: 560,
                        ...(isAI ? {} : { boxShadow: "0 2px 12px rgba(27,125,90,0.18)" }),
                      }}>
                        {isAI ? (
                          <>
                            {msg.content.split(/\n{2,}/).map((block, bi) => (
                              <p key={bi} style={{ marginTop: bi === 0 ? 0 : 8 }}>{block}</p>
                            ))}

                            {showReasoning && (
                              <div style={{ marginTop: 12, display: "flex", flexWrap: "wrap", gap: 8 }}>
                                {contextualActions.map((action) => (
                                  <button
                                    key={action.label}
                                    type="button"
                                    onClick={() => {
                                      setAiQuery("");
                                      void runNutritionQuery(action.query);
                                    }}
                                    style={{
                                      padding: "6px 12px", borderRadius: 20,
                                      background: "#f0f0ec", border: "none",
                                      fontSize: 13, fontWeight: 500, color: "#555",
                                      cursor: "pointer", fontFamily: "inherit",
                                      transition: "background 0.15s",
                                    }}
                                  >
                                    {action.label}
                                  </button>
                                ))}
                              </div>
                            )}
                          </>
                        ) : (
                          msg.content
                        )}
                      </div>
                    </div>
                  );
                })}

                {/* Typing indicator */}
                {aiLoading && (
                  <div style={{ display: "flex", gap: 12, animation: "nlFadeIn 0.2s ease" }}>
                    <div style={{
                      width: 30, height: 30, borderRadius: 10,
                      background: "linear-gradient(135deg, #1B7D5A, #2AA876)",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      flexShrink: 0,
                      boxShadow: "0 2px 8px rgba(27,125,90,0.2)",
                    }}>
                      <span style={{ color: "#fff", fontSize: 13, fontWeight: 700, fontFamily: "Georgia, serif" }}>N</span>
                    </div>
                    <TypingIndicator />
                  </div>
                )}
              </div>
            )}
          </div>

          {/* ✅ FIX 2: Context tags only in active chat state */}
          {!isEmptyState && (
            <div style={{
              padding: "0 28px",
              display: "flex", gap: 5, flexWrap: "wrap",
              marginBottom: 6, flexShrink: 0,
              animation: "nlFadeIn 0.3s ease",
            }}>
              {contextTags.map((tag) => (
                <span
                  key={tag}
                  style={{
                    display: "inline-flex", alignItems: "center", gap: 4,
                    padding: "3px 9px", borderRadius: 6,
                    background: "rgba(27,125,90,0.06)",
                    color: "#1B7D5A",
                    fontSize: 11, fontWeight: 500, letterSpacing: 0.15,
                  }}
                >
                  <span style={{ width: 4, height: 4, borderRadius: "50%", background: "#2AA876" }} />
                  {tag}
                </span>
              ))}
            </div>
          )}

          {/* ── Input Area ── ✅ FIX 5: Focus state with green border + glow */}
          <div style={{
            padding: isEmptyState ? "0 28px 20px" : "10px 28px 20px",
            flexShrink: 0,
          }}>
            <div style={{ maxWidth: isEmptyState ? 540 : "none", margin: "0 auto" }}>
              <form onSubmit={onAskSubmit}>
                <div style={{
                  display: "flex", alignItems: "flex-end", gap: 8,
                  background: "#fff",
                  border: `1.5px solid ${inputFocused ? "#1B7D5A" : "#e2e2de"}`,
                  borderRadius: 16,
                  padding: "5px 5px 5px 18px",
                  boxShadow: inputFocused
                    ? "0 0 0 3px rgba(27,125,90,0.08), 0 4px 24px rgba(0,0,0,0.04)"
                    : "0 2px 12px rgba(0,0,0,0.03)",
                  transition: "all 0.2s ease",
                }}>
                  <textarea
                    ref={textareaRef}
                    className="nl-textarea"
                    value={aiQuery}
                    onFocus={() => setInputFocused(true)}
                    onBlur={() => setInputFocused(false)}
                    onChange={(e) => {
                      setAiQuery(e.target.value);
                      e.target.style.height = "auto";
                      e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px";
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        void onAskSubmit(e as unknown as FormEvent);
                      }
                    }}
                    placeholder="Ask about meals, swaps, macros..."
                    rows={1}
                    disabled={aiLoading}
                    style={{
                      flex: 1, border: "none", outline: "none", resize: "none",
                      fontFamily: "inherit", fontSize: 14.5, lineHeight: 1.55,
                      padding: "10px 0", color: "#1a1a1a", background: "transparent",
                      minHeight: 22, maxHeight: 120,
                    }}
                  />
                  <button
                    type="submit"
                    disabled={!aiQuery.trim() || aiLoading}
                    style={{
                      width: 38, height: 38, borderRadius: 11,
                      border: "none",
                      cursor: aiQuery.trim() && !aiLoading ? "pointer" : "default",
                      background:
                        aiQuery.trim() && !aiLoading
                          ? "linear-gradient(135deg, #1B7D5A, #2AA876)"
                          : "#eeede9",
                      color: aiQuery.trim() && !aiLoading ? "#fff" : "#c0c0b8",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      transition: "all 0.25s ease", flexShrink: 0,
                      boxShadow: aiQuery.trim() && !aiLoading ? "0 2px 10px rgba(27,125,90,0.25)" : "none",
                      transform: aiQuery.trim() && !aiLoading ? "scale(1)" : "scale(0.95)",
                    }}
                  >
                    {aiLoading ? (
                      <Loader2 size={16} className="animate-spin" />
                    ) : (
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M22 2L11 13" /><path d="M22 2L15 22L11 13L2 9L22 2Z" />
                      </svg>
                    )}
                  </button>
                </div>
              </form>
              <p style={{ textAlign: "center", marginTop: 8, fontSize: 11, color: "#c4c4bc", letterSpacing: 0.1 }}>
                Mr Nutri uses your meal plan &amp; pantry data for personalised advice
              </p>
            </div>
          </div>
        </div>

        {/* ── Side Panel ── */}
        {showPanel && (
          <div style={{
            width: 310,
            borderLeft: "1px solid #eeede9",
            background: "#fff",
            overflowY: "auto",
            animation: "nlSlideInRight 0.25s ease",
            flexShrink: 0,
            display: "flex",
            flexDirection: "column",
            scrollbarWidth: "thin",
            scrollbarColor: "#d4d4d0 transparent",
          }}>

            {/* Panel Header */}
            <div style={{
              padding: "14px 18px",
              borderBottom: "1px solid #f2f2ee",
              display: "flex", alignItems: "center", justifyContent: "space-between",
              flexShrink: 0, minHeight: 56,
            }}>
              <span style={{ fontSize: 13.5, fontWeight: 600, color: "#1a1a1a" }}>Today&apos;s Nutrition</span>
              <button
                type="button"
                onClick={() => setShowPanel(false)}
                style={{
                  width: 26, height: 26, borderRadius: 7, border: "none",
                  background: "#f5f5f2", cursor: "pointer",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  color: "#999", transition: "all 0.15s",
                }}
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>

            {/* Macro Rings — 2×2 */}
            <div style={{ padding: "20px 18px 14px" }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                {(Object.entries(macros) as [string, { current: number; target: number; color: string; unit: string }][]).map(
                  ([key, m]) => (
                    <div
                      key={key}
                      style={{
                        display: "flex", flexDirection: "column", alignItems: "center",
                        padding: "14px 6px 12px", borderRadius: 12, background: "#FAFAF8", gap: 6,
                      }}
                    >
                      <div style={{ position: "relative" }}>
                        <MacroRing value={m.current} max={m.target} color={m.color} size={48} strokeW={4} />
                        <div style={{
                          position: "absolute", top: "50%", left: "50%",
                          transform: "translate(-50%, -50%)",
                          fontSize: 10.5, fontWeight: 700, color: m.color,
                          whiteSpace: "nowrap",
                        }}>
                          {m.target > 0 ? Math.round((m.current / m.target) * 100) : 0}%
                        </div>
                      </div>
                      <div style={{ textAlign: "center" }}>
                        <div style={{ fontSize: 12.5, fontWeight: 600, color: "#1a1a1a" }}>
                          {m.current}
                          <span style={{ color: "#c0c0b8", fontWeight: 400, fontSize: 11.5 }}>/{m.target}</span>
                        </div>
                        <div style={{ fontSize: 10.5, color: "#aaa", textTransform: "capitalize", marginTop: 1 }}>
                          {key} ({m.unit})
                        </div>
                      </div>
                    </div>
                  )
                )}
              </div>
            </div>

            {/* Quick stats row */}
            <div style={{ padding: "0 18px 14px", display: "flex", gap: 10 }}>
              {[
                { label: "Calories", value: `${Math.round(caloriesProgress)}%`, sub: `${caloriesToday} / ${caloriesTarget}` },
                { label: "Protein", value: `${Math.round(proteinProgress)}%`, sub: `${proteinToday}g / ${proteinTarget}g` },
              ].map((stat) => (
                <div
                  key={stat.label}
                  style={{
                    flex: 1, padding: "10px 12px", borderRadius: 10,
                    background: "#FAFAF8", border: "1px solid #f0f0ec",
                  }}
                >
                  <p style={{ fontSize: 9.5, fontWeight: 600, color: "#aaa", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 3 }}>
                    {stat.label}
                  </p>
                  <p style={{ fontSize: 17, fontWeight: 700, color: "#1a1a1a", lineHeight: 1 }}>{stat.value}</p>
                  <p style={{ fontSize: 10, color: "#c0c0b8", marginTop: 3 }}>{stat.sub}</p>
                </div>
              ))}
            </div>

            {/* Adherence */}
            <div style={{ padding: "0 18px 18px" }}>
              <div style={{ padding: "14px 16px", borderRadius: 12, background: "#FAFAF8", border: "1px solid #f0f0ec" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                  <span style={{ fontSize: 12, fontWeight: 600, color: "#1a1a1a" }}>Weekly Adherence</span>
                  <span style={{
                    fontSize: 18, fontWeight: 700,
                    color: weeklyAdherence >= 70 ? "#1B7D5A" : "#E8913A",
                    fontFamily: "Georgia, serif",
                  }}>
                    {weeklyAdherence}%
                  </span>
                </div>
                <div style={{ height: 5, borderRadius: 3, background: "#eeede9", overflow: "hidden" }}>
                  <div style={{
                    height: "100%", borderRadius: 3,
                    width: `${clampPercent(weeklyAdherence)}%`,
                    background:
                      weeklyAdherence >= 70
                        ? "linear-gradient(90deg, #1B7D5A, #2AA876)"
                        : "linear-gradient(90deg, #E8913A, #F0A854)",
                    transition: "width 0.8s ease",
                  }} />
                </div>
                <div style={{ fontSize: 10.5, color: "#aaa", marginTop: 7 }}>
                  {historyData?.statistics?.logged_meals ?? 0} meals logged · 7 day window
                </div>

                {/* Day dots */}
                {(() => {
                  const loggedCount = historyData?.statistics?.logged_meals ?? 0;
                  return (
                    <div style={{ display: "flex", gap: 4, marginTop: 12, justifyContent: "space-between" }}>
                      {["M", "T", "W", "T", "F", "S", "S"].map((d, i) => {
                        const logged = i < loggedCount;
                        const isToday = i === 6;
                        return (
                          <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 3 }}>
                            <div style={{
                              width: 26, height: 26, borderRadius: 7,
                              background: logged ? "rgba(27,125,90,0.08)" : isToday ? "#fff" : "#f5f5f2",
                              border: isToday
                                ? "1.5px dashed #1B7D5A"
                                : logged
                                ? "1px solid rgba(27,125,90,0.15)"
                                : "1px solid #eeede9",
                              display: "flex", alignItems: "center", justifyContent: "center",
                              color: logged ? "#1B7D5A" : "#ddd",
                            }}>
                              {logged && (
                                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round">
                                  <polyline points="20 6 9 17 4 12" />
                                </svg>
                              )}
                            </div>
                            <span style={{
                              fontSize: 9.5,
                              color: isToday ? "#1B7D5A" : "#c0c0b8",
                              fontWeight: isToday ? 600 : 400,
                            }}>
                              {d}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  );
                })()}
              </div>
            </div>

            {/* Deep Analytics */}
            <div style={{ padding: "0 18px 20px", marginTop: "auto" }}>
              <button
                type="button"
                onClick={() => setShowAnalytics(!showAnalytics)}
                style={{
                  width: "100%", padding: "11px 14px", borderRadius: 10,
                  border: "1px solid #e8e8e4", background: "#FAFAF8",
                  cursor: "pointer",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  gap: 7, fontSize: 12.5, fontWeight: 500, color: "#666",
                  fontFamily: "inherit", transition: "all 0.15s",
                }}
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 12c0 1.2-4 6-9 6s-9-4.8-9-6c0-1.2 4-6 9-6s9 4.8 9 6z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
                {showAnalytics ? "Hide Analytics" : "Deep Analytics"}
                <ChevronDown
                  size={14}
                  style={{ transition: "transform 0.2s", transform: showAnalytics ? "rotate(180deg)" : "none" }}
                />
              </button>

              {showAnalytics && (
                <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 16, animation: "nlFadeIn 0.25s ease" }}>
                  <div>
                    <p style={{ fontSize: 12, fontWeight: 600, color: "#1a1a1a", marginBottom: 2 }}>Adherence Pattern</p>
                    <p style={{ fontSize: 11, color: "#999", marginBottom: 8 }}>Last 7 days</p>
                    <div style={{ height: 160 }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={macroTrend}>
                          <CartesianGrid strokeDasharray="4 4" stroke="#E2E8F0" />
                          <XAxis dataKey="date" tick={{ fill: "#64748B", fontSize: 10 }} axisLine={{ stroke: "#E2E8F0" }} tickLine={false} />
                          <YAxis domain={[0, 100]} tick={{ fill: "#64748B", fontSize: 10 }} axisLine={{ stroke: "#E2E8F0" }} tickLine={false} />
                          <Tooltip />
                          <Line type="monotone" dataKey="adherence" stroke="#0F766E" strokeWidth={2} dot={{ r: 2 }} activeDot={{ r: 3 }} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </div>

                  <div>
                    <p style={{ fontSize: 12, fontWeight: 600, color: "#1a1a1a", marginBottom: 2 }}>Macro Distribution</p>
                    <p style={{ fontSize: 11, color: "#999", marginBottom: 8 }}>Today</p>
                    <div style={{ height: 160, position: "relative" }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={macroDistribution}>
                          <CartesianGrid strokeDasharray="4 4" stroke="#E2E8F0" />
                          <XAxis dataKey="name" tick={{ fill: "#64748B", fontSize: 10 }} axisLine={{ stroke: "#E2E8F0" }} tickLine={false} />
                          <YAxis domain={[0, 120]} tick={{ fill: "#64748B", fontSize: 10 }} axisLine={{ stroke: "#E2E8F0" }} tickLine={false} />
                          <Tooltip />
                          <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                            {macroDistribution.map((item) => (
                              <Cell key={`macro-${item.name}`} fill={item.fill} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                      {!hasMacroData && (
                        <div style={{
                          position: "absolute", inset: 0,
                          display: "flex", alignItems: "center", justifyContent: "center",
                          fontSize: 11, color: "#bbb", pointerEvents: "none",
                        }}>
                          No macro data logged yet.
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}