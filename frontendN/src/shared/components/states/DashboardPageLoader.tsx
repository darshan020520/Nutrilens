"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

export type DashboardLoaderScene = "home" | "meals" | "nutrition" | "kitchen" | "pantry" | "restock";

type LoaderCopy = {
  eyebrow: string;
  title: string;
  subtitle: string;
};

const COPY: Record<DashboardLoaderScene, LoaderCopy> = {
  home: {
    eyebrow: "HOME",
    title: "Loading your dashboard...",
    subtitle: "Syncing today summary, macros, and quick actions.",
  },
  meals: {
    eyebrow: "MEALS",
    title: "Setting up your meal workspace...",
    subtitle: "Preparing today, week plan, and recipe views.",
  },
  nutrition: {
    eyebrow: "NUTRITION",
    title: "Building your nutrition insights...",
    subtitle: "Collecting trends, adherence, and macro signals.",
  },
  kitchen: {
    eyebrow: "KITCHEN",
    title: "Warming up your kitchen view...",
    subtitle: "Prepping recipe matches and your AI cooking studio.",
  },
  pantry: {
    eyebrow: "PANTRY",
    title: "Opening your pantry...",
    subtitle: "Checking freshness, stock signals, and inventory state.",
  },
  restock: {
    eyebrow: "RESTOCK",
    title: "Preparing your shopping run...",
    subtitle: "Prioritizing pickups and syncing your list.",
  },
};

type InitialLoaderOptions = {
  showDelayMs?: number;
  minVisibleMs?: number;
  maxVisibleMs?: number | null;
  exitMs?: number;
};

type InitialLoaderState = {
  showLoader: boolean;
  isExiting: boolean;
};

export function useInitialPageLoader(
  isDataReady: boolean,
  options?: InitialLoaderOptions
): InitialLoaderState {
  const showDelayMs = options?.showDelayMs ?? 120;
  const minVisibleMs = options?.minVisibleMs ?? 560;
  const maxVisibleMs = options?.maxVisibleMs ?? null;
  const exitMs = options?.exitMs ?? 200;

  const [loaderVisible, setLoaderVisible] = useState(() => (showDelayMs === 0 ? !isDataReady : false));
  const [isExiting, setIsExiting] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  const loaderVisibleRef = useRef(loaderVisible);
  const dismissedRef = useRef(dismissed);
  const exitStartedRef = useRef(false);
  const visibleAtRef = useRef<number | null>(null);

  useEffect(() => {
    loaderVisibleRef.current = loaderVisible;
  }, [loaderVisible]);

  useEffect(() => {
    dismissedRef.current = dismissed;
  }, [dismissed]);

  const beginExit = useCallback(() => {
    if (dismissedRef.current || exitStartedRef.current) return;
    exitStartedRef.current = true;

    if (!loaderVisibleRef.current) {
      setDismissed(true);
      return;
    }

    setIsExiting(true);
    window.setTimeout(() => {
      setDismissed(true);
      setIsExiting(false);
    }, exitMs);
  }, [exitMs]);

  useEffect(() => {
    if (dismissed) return;

    if (!isDataReady && showDelayMs === 0) {
      if (!loaderVisible) {
        visibleAtRef.current = performance.now();
        setLoaderVisible(true);
      }
      return;
    }

    if (isDataReady && !loaderVisible) {
      setDismissed(true);
      return;
    }

    const delayId = window.setTimeout(() => {
      if (dismissedRef.current || isDataReady) return;
      visibleAtRef.current = performance.now();
      setLoaderVisible(true);
    }, showDelayMs);

    let maxId: number | null = null;
    if (typeof maxVisibleMs === "number" && maxVisibleMs > 0) {
      maxId = window.setTimeout(() => {
        beginExit();
      }, maxVisibleMs);
    }

    return () => {
      window.clearTimeout(delayId);
      if (maxId !== null) window.clearTimeout(maxId);
    };
  }, [beginExit, dismissed, isDataReady, loaderVisible, maxVisibleMs, showDelayMs]);

  useEffect(() => {
    if (dismissed || isExiting) return;
    if (!isDataReady) return;
    if (!loaderVisible) return;

    const elapsed = visibleAtRef.current ? performance.now() - visibleAtRef.current : 0;
    const remaining = Math.max(0, minVisibleMs - elapsed);
    const timerId = window.setTimeout(() => {
      beginExit();
    }, remaining);

    return () => window.clearTimeout(timerId);
  }, [beginExit, dismissed, isDataReady, isExiting, loaderVisible, minVisibleMs]);

  return {
    showLoader: !dismissed && (loaderVisible || isExiting),
    isExiting,
  };
}

export function DashboardPageLoader({
  scene,
  className,
  isExiting = false,
}: {
  scene: DashboardLoaderScene;
  className?: string;
  isExiting?: boolean;
}) {
  const copy = COPY[scene];

  return (
    <section
      className={cn(
        "relative overflow-hidden rounded-[24px] border border-[#E6DFD3] bg-[linear-gradient(160deg,#F8F5F0,#F1ECE4)] px-8 py-8 transition-[opacity,transform] duration-200 md:px-10 md:py-9",
        isExiting ? "translate-y-1 opacity-0" : "translate-y-0 opacity-100",
        className
      )}
      aria-live="polite"
      aria-busy="true"
    >
      <div className="pointer-events-none absolute inset-0 opacity-60">
        <div className="loader-sheen h-full w-full" />
      </div>

      <div className="relative z-[1] flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
        <div className="max-w-[560px]">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#5E7C65]">{copy.eyebrow}</p>
          <h2 className="mt-3 text-[30px] font-semibold leading-[1.15] tracking-[-0.02em] text-[#2A2A2A]">{copy.title}</h2>
          <p className="mt-3 text-[14px] leading-[1.45] text-[#665F54]">{copy.subtitle}</p>
          <div className="mt-5 h-1.5 w-56 overflow-hidden rounded-full bg-[#E4DDD1]">
            <div className="loader-sweep h-full w-[38%] rounded-full bg-[linear-gradient(90deg,#2F6F5E,#5A9A7E)]" />
          </div>
        </div>

        {scene === "kitchen" ? (
          <div className="scene-shell h-[136px] w-[236px]" aria-hidden>
            <div className="kitchen-pot">
              <span className="kitchen-lid" />
              <span className="kitchen-body" />
              <span className="kitchen-handle" />
            </div>
            <div className="kitchen-steam">
              <span />
              <span />
              <span />
            </div>
            <div className="kitchen-utensils">
              <span />
              <span />
            </div>
          </div>
        ) : null}

        {scene === "home" ? (
          <div className="scene-shell h-[136px] w-[236px]" aria-hidden>
            <div className="home-grid">
              <span className="home-cell home-cell-a" />
              <span className="home-cell home-cell-b" />
              <span className="home-cell home-cell-c" />
              <span className="home-cell home-cell-d" />
              <span className="home-scan" />
            </div>
          </div>
        ) : null}

        {scene === "meals" ? (
          <div className="scene-shell h-[136px] w-[236px]" aria-hidden>
            <div className="meals-plate">
              <span className="meals-rim" />
              <span className="meals-core" />
            </div>
            <span className="meals-fork" />
            <span className="meals-spoon" />
          </div>
        ) : null}

        {scene === "nutrition" ? (
          <div className="scene-shell h-[136px] w-[236px]" aria-hidden>
            <div className="nutrition-chart">
              <span className="nutrition-bar nutrition-bar-a" />
              <span className="nutrition-bar nutrition-bar-b" />
              <span className="nutrition-bar nutrition-bar-c" />
              <span className="nutrition-line" />
            </div>
          </div>
        ) : null}

        {scene === "pantry" ? (
          <div className="scene-shell h-[136px] w-[236px]" aria-hidden>
            <div className="pantry-fridge">
              <span className="pantry-door" />
              <span className="pantry-seam" />
              <span className="pantry-handle" />
            </div>
          </div>
        ) : null}

        {scene === "restock" ? (
          <div className="scene-shell h-[136px] w-[236px]" aria-hidden>
            <div className="restock-track" />
            <div className="restock-cart">
              <span className="restock-basket" />
              <span className="restock-handle" />
              <span className="restock-wheel restock-wheel-left" />
              <span className="restock-wheel restock-wheel-right" />
            </div>
          </div>
        ) : null}
      </div>

      <style jsx>{`
        .loader-sheen {
          background: linear-gradient(105deg, rgba(255, 255, 255, 0) 20%, rgba(255, 255, 255, 0.32) 48%, rgba(255, 255, 255, 0) 72%);
          transform: translateX(-30%);
          animation: loader-sheen 1.8s ease-in-out infinite;
        }

        .loader-sweep {
          transform: translateX(-125%);
          animation: loader-sweep 1.2s ease-in-out infinite;
        }

        .scene-shell {
          position: relative;
          transform: scale(1.1);
          transform-origin: center right;
        }

        .home-grid {
          position: absolute;
          left: 70px;
          bottom: 20px;
          width: 126px;
          height: 96px;
          border-radius: 14px;
          background: #f3f6f8;
          border: 1px solid #d8dfe4;
          padding: 10px;
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 8px;
          overflow: hidden;
        }

        .home-cell {
          border-radius: 8px;
          background: linear-gradient(145deg, #dce7dd, #e7efea);
        }

        .home-cell-a {
          animation: home-cell-pulse 1.2s ease-in-out infinite;
        }

        .home-cell-b {
          animation: home-cell-pulse 1.2s ease-in-out infinite 0.15s;
        }

        .home-cell-c {
          animation: home-cell-pulse 1.2s ease-in-out infinite 0.3s;
        }

        .home-cell-d {
          animation: home-cell-pulse 1.2s ease-in-out infinite 0.45s;
        }

        .home-scan {
          position: absolute;
          left: 8px;
          right: 8px;
          height: 2px;
          border-radius: 999px;
          background: rgba(47, 111, 94, 0.5);
          animation: home-scan 1.5s ease-in-out infinite;
        }

        .meals-plate {
          position: absolute;
          left: 78px;
          bottom: 18px;
          width: 104px;
          height: 104px;
          border-radius: 999px;
          background: #f3f6f8;
          border: 1px solid #d8dfe4;
          display: grid;
          place-items: center;
        }

        .meals-rim {
          position: absolute;
          inset: 11px;
          border-radius: 999px;
          border: 4px solid #9cb4a5;
        }

        .meals-core {
          width: 34px;
          height: 34px;
          border-radius: 999px;
          background: linear-gradient(145deg, #dce7dd, #e7efea);
          animation: meals-core 1.2s ease-in-out infinite;
        }

        .meals-fork,
        .meals-spoon {
          position: absolute;
          top: 24px;
          width: 4px;
          height: 46px;
          border-radius: 999px;
          background: #7f9b8d;
          transform-origin: bottom center;
          animation: meals-cutlery 1.15s ease-in-out infinite;
        }

        .meals-fork {
          left: 56px;
        }

        .meals-spoon {
          left: 192px;
          animation-delay: 0.2s;
        }

        .nutrition-chart {
          position: absolute;
          left: 68px;
          bottom: 20px;
          width: 136px;
          height: 102px;
          border-radius: 12px;
          border: 1px solid #d8dfe4;
          background: #f7f9fa;
          padding: 10px 10px 8px;
          display: flex;
          align-items: flex-end;
          gap: 9px;
          overflow: hidden;
        }

        .nutrition-bar {
          width: 24px;
          border-radius: 8px 8px 3px 3px;
          background: linear-gradient(180deg, #7fa594, #4f6f5b);
        }

        .nutrition-bar-a {
          height: 40px;
          animation: nutrition-bar-a 1.3s ease-in-out infinite;
        }

        .nutrition-bar-b {
          height: 64px;
          animation: nutrition-bar-b 1.3s ease-in-out infinite 0.15s;
        }

        .nutrition-bar-c {
          height: 52px;
          animation: nutrition-bar-c 1.3s ease-in-out infinite 0.3s;
        }

        .nutrition-line {
          position: absolute;
          left: 12px;
          right: 12px;
          top: 40px;
          height: 2px;
          border-radius: 999px;
          background: rgba(47, 111, 94, 0.45);
          transform-origin: left center;
          animation: nutrition-line 1.4s ease-in-out infinite;
        }

        .kitchen-pot {
          position: absolute;
          left: 52px;
          bottom: 24px;
          width: 116px;
          height: 82px;
          animation: kitchen-pot 1.1s ease-in-out infinite;
        }

        .kitchen-lid {
          position: absolute;
          left: 14px;
          top: 2px;
          width: 88px;
          height: 14px;
          border-radius: 10px;
          background: #739081;
          transform-origin: center center;
          animation: kitchen-lid 0.7s ease-in-out infinite;
        }

        .kitchen-body {
          position: absolute;
          left: 0;
          top: 16px;
          width: 116px;
          height: 50px;
          border-radius: 12px;
          background: linear-gradient(145deg, #4f6f5b, #355547);
        }

        .kitchen-handle {
          position: absolute;
          right: -16px;
          top: 28px;
          width: 22px;
          height: 12px;
          border-radius: 10px;
          border: 3px solid #5d7168;
        }

        .kitchen-steam span {
          position: absolute;
          bottom: 84px;
          width: 6px;
          height: 26px;
          border-radius: 999px;
          background: rgba(102, 114, 122, 0.48);
          animation: kitchen-steam 1.2s ease-in-out infinite;
        }

        .kitchen-steam span:nth-child(1) {
          left: 96px;
        }

        .kitchen-steam span:nth-child(2) {
          left: 112px;
          animation-delay: 0.18s;
        }

        .kitchen-steam span:nth-child(3) {
          left: 128px;
          animation-delay: 0.34s;
        }

        .kitchen-utensils span {
          position: absolute;
          top: 28px;
          right: 26px;
          width: 4px;
          height: 48px;
          border-radius: 999px;
          background: #7f9b8d;
          transform-origin: bottom center;
          animation: kitchen-utensil 1.1s ease-in-out infinite;
        }

        .kitchen-utensils span:nth-child(1) {
          transform: rotate(20deg);
        }

        .kitchen-utensils span:nth-child(2) {
          transform: rotate(-14deg);
          animation-delay: 0.2s;
        }

        .pantry-fridge {
          position: absolute;
          left: 78px;
          bottom: 18px;
          width: 92px;
          height: 116px;
          border-radius: 14px;
          background: linear-gradient(150deg, #f7f8f9, #e9edf0);
          border: 1px solid #d5dce1;
          overflow: hidden;
        }

        .pantry-door {
          position: absolute;
          inset: 0;
          background: linear-gradient(150deg, #ffffff, #eff3f5);
          transform-origin: left center;
          animation: pantry-door 1.8s ease-in-out infinite;
        }

        .pantry-seam {
          position: absolute;
          left: 0;
          right: 0;
          top: 58px;
          height: 1px;
          background: #d2d8de;
        }

        .pantry-handle {
          position: absolute;
          right: 16px;
          top: 46px;
          width: 4px;
          height: 24px;
          border-radius: 999px;
          background: #afbcc4;
        }

        .restock-track {
          position: absolute;
          left: 28px;
          right: 18px;
          bottom: 38px;
          height: 3px;
          border-radius: 999px;
          background: #cdc4b6;
        }

        .restock-cart {
          position: absolute;
          left: 30px;
          bottom: 38px;
          width: 98px;
          height: 66px;
          animation: restock-cart 1.6s ease-in-out infinite;
        }

        .restock-basket {
          position: absolute;
          left: 8px;
          top: 10px;
          width: 62px;
          height: 34px;
          border: 3px solid #4f6f5b;
          border-radius: 8px;
          border-top-width: 4px;
        }

        .restock-handle {
          position: absolute;
          right: 4px;
          top: 8px;
          width: 18px;
          height: 3px;
          border-radius: 999px;
          background: #4f6f5b;
          transform: rotate(-26deg);
          transform-origin: left center;
        }

        .restock-wheel {
          position: absolute;
          bottom: 0;
          width: 12px;
          height: 12px;
          border-radius: 999px;
          background: #7a7d7f;
        }

        .restock-wheel-left {
          left: 14px;
        }

        .restock-wheel-right {
          left: 54px;
        }

        @keyframes loader-sheen {
          from {
            transform: translateX(-40%);
            opacity: 0;
          }
          25% {
            opacity: 1;
          }
          to {
            transform: translateX(45%);
            opacity: 0;
          }
        }

        @keyframes loader-sweep {
          0% {
            transform: translateX(-125%);
          }
          100% {
            transform: translateX(255%);
          }
        }

        @keyframes kitchen-pot {
          0%,
          100% {
            transform: translateX(0) rotate(0deg);
          }
          50% {
            transform: translateX(1px) rotate(0.8deg);
          }
        }

        @keyframes home-cell-pulse {
          0%,
          100% {
            opacity: 0.8;
            transform: scale(1);
          }
          50% {
            opacity: 1;
            transform: scale(1.03);
          }
        }

        @keyframes home-scan {
          0% {
            top: 10px;
            opacity: 0;
          }
          30% {
            opacity: 0.8;
          }
          100% {
            top: 82px;
            opacity: 0;
          }
        }

        @keyframes meals-core {
          0%,
          100% {
            transform: scale(0.96);
          }
          50% {
            transform: scale(1);
          }
        }

        @keyframes meals-cutlery {
          0%,
          100% {
            transform: translateX(0);
          }
          50% {
            transform: translateX(2px);
          }
        }

        @keyframes nutrition-bar-a {
          0%,
          100% {
            height: 40px;
          }
          50% {
            height: 56px;
          }
        }

        @keyframes nutrition-bar-b {
          0%,
          100% {
            height: 64px;
          }
          50% {
            height: 48px;
          }
        }

        @keyframes nutrition-bar-c {
          0%,
          100% {
            height: 52px;
          }
          50% {
            height: 66px;
          }
        }

        @keyframes nutrition-line {
          0% {
            transform: scaleX(0.25);
            opacity: 0.35;
          }
          100% {
            transform: scaleX(1);
            opacity: 0.8;
          }
        }

        @keyframes kitchen-lid {
          0%,
          100% {
            transform: translateY(0);
          }
          50% {
            transform: translateY(-2px);
          }
        }

        @keyframes kitchen-steam {
          0% {
            opacity: 0;
            transform: translateY(8px);
          }
          35% {
            opacity: 0.55;
          }
          100% {
            opacity: 0;
            transform: translateY(-10px);
          }
        }

        @keyframes kitchen-utensil {
          0%,
          100% {
            opacity: 0.75;
            transform: translateX(0);
          }
          50% {
            opacity: 1;
            transform: translateX(2px);
          }
        }

        @keyframes pantry-door {
          0%,
          100% {
            transform: rotate(0deg);
          }
          40% {
            transform: rotate(-14deg);
          }
        }

        @keyframes restock-cart {
          0% {
            transform: translateX(0);
          }
          50% {
            transform: translateX(76px);
          }
          100% {
            transform: translateX(0);
          }
        }

        @media (prefers-reduced-motion: reduce) {
          .loader-sheen,
          .loader-sweep,
          .kitchen-pot,
          .kitchen-lid,
          .kitchen-steam span,
          .kitchen-utensils span,
          .home-cell-a,
          .home-cell-b,
          .home-cell-c,
          .home-cell-d,
          .home-scan,
          .meals-core,
          .meals-fork,
          .meals-spoon,
          .nutrition-bar-a,
          .nutrition-bar-b,
          .nutrition-bar-c,
          .nutrition-line,
          .pantry-door,
          .restock-cart {
            animation: none !important;
          }

          .scene-shell {
            transform: none;
          }
        }
      `}</style>
    </section>
  );
}
