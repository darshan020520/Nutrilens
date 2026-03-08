"use client";

import { useEffect, useRef, useState } from "react";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface StepTransitionOverlayProps {
  open: boolean;
  ready: boolean;
  title: string;
  description: string;
  checkpoints: string[];
  completionTitle: string;
  completionDescription: string;
  onComplete: () => void;
}

const CARD_EASE = "cubic-bezier(0.4, 0, 0.2, 1)";

export default function StepTransitionOverlay({
  open,
  ready,
  title,
  description,
  checkpoints,
  completionTitle,
  completionDescription,
  onComplete,
}: StepTransitionOverlayProps) {
  const [visibleCount, setVisibleCount] = useState(0);
  const [progress, setProgress] = useState(0);
  const [showCompletion, setShowCompletion] = useState(false);

  const doneTimeoutRef = useRef<number | null>(null);
  const revealTimeoutRef = useRef<number | null>(null);
  const hasCompletedRef = useRef(false);

  useEffect(() => {
    if (!open) {
      setVisibleCount(0);
      setProgress(0);
      setShowCompletion(false);
      hasCompletedRef.current = false;
      if (doneTimeoutRef.current) window.clearTimeout(doneTimeoutRef.current);
      if (revealTimeoutRef.current) window.clearTimeout(revealTimeoutRef.current);
      return;
    }

    setVisibleCount(0);
    setProgress(0);
    setShowCompletion(false);
    hasCompletedRef.current = false;

    let revealTimeout: number | null = null;
    const revealNext = () => {
      setVisibleCount((prev) => {
        if (prev >= checkpoints.length) {
          return prev;
        }
        const nextCompleted = prev + 1;
        const clampedCompleted = Math.min(nextCompleted, checkpoints.length);
        const syncedProgress = checkpoints.length > 0
          ? (clampedCompleted / checkpoints.length) * 90
          : 90;
        setProgress(syncedProgress);
        if (nextCompleted < checkpoints.length) {
          revealTimeout = window.setTimeout(revealNext, 600);
        }
        return nextCompleted;
      });
    };

    revealTimeout = window.setTimeout(revealNext, 220);

    return () => {
      if (revealTimeout) window.clearTimeout(revealTimeout);
      if (doneTimeoutRef.current) window.clearTimeout(doneTimeoutRef.current);
      if (revealTimeoutRef.current) window.clearTimeout(revealTimeoutRef.current);
    };
  }, [checkpoints.length, open]);

  useEffect(() => {
    if (!open || !ready || hasCompletedRef.current) return;
    if (visibleCount < checkpoints.length) return;
    const runCompletion = () => {
      if (hasCompletedRef.current) return;
      hasCompletedRef.current = true;
      setProgress(100);

      revealTimeoutRef.current = window.setTimeout(() => {
        setShowCompletion(true);
      }, 320);

      doneTimeoutRef.current = window.setTimeout(() => {
        onComplete();
      }, 900);
    };
    runCompletion();
  }, [checkpoints.length, onComplete, open, ready, visibleCount]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[75] bg-slate-950/26 backdrop-blur-md">
      <div className="flex h-full w-full items-center justify-center px-6">
        <div
          className={cn(
            "relative w-full max-w-xl overflow-hidden rounded-[18px] border border-white/70 bg-[linear-gradient(165deg,#ffffff_0%,#f6faf7_48%,#f8fcfb_100%)] p-7 shadow-[0_28px_72px_-42px_rgba(15,23,42,0.55)] transition-all duration-[400ms]",
            showCompletion ? "scale-[1.02]" : "scale-100"
          )}
          style={{ transitionTimingFunction: CARD_EASE }}
        >
          <div className="pointer-events-none absolute -left-16 top-0 h-40 w-40 rounded-full bg-emerald-300/25 blur-3xl" />
          <div className="pointer-events-none absolute -right-16 top-8 h-40 w-40 rounded-full bg-teal-300/20 blur-3xl" />

          <div className="relative">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-emerald-700/80">
              Intelligent Personalization
            </p>
            <h3
              className={cn(
                "mt-2 text-2xl font-semibold tracking-[-0.01em] text-slate-900 transition-[opacity,transform] duration-300",
                showCompletion ? "opacity-0 -translate-y-1" : "opacity-100 translate-y-0"
              )}
            >
              {title}
            </h3>
            <p
              className={cn(
                "mt-2 text-sm leading-6 text-slate-600 transition-[opacity,transform] duration-300",
                showCompletion ? "opacity-0 -translate-y-1" : "opacity-100 translate-y-0"
              )}
            >
              {description}
            </p>

            <h4
              className={cn(
                "absolute left-0 top-8 text-2xl font-semibold tracking-[-0.01em] text-slate-900 transition-[opacity,transform] duration-300",
                showCompletion ? "opacity-100 translate-y-0" : "pointer-events-none opacity-0 translate-y-1"
              )}
            >
              {completionTitle}
            </h4>
            <p
              className={cn(
                "absolute left-0 top-20 text-sm text-slate-600 transition-[opacity,transform] duration-300",
                showCompletion ? "opacity-100 translate-y-0" : "pointer-events-none opacity-0 translate-y-1"
              )}
            >
              {completionDescription}
            </p>
          </div>

          <div className={cn("mt-5 space-y-2.5 transition-opacity duration-300", showCompletion ? "opacity-0" : "opacity-100")}>
            {checkpoints.map((checkpoint, index) => {
              const isVisible = index < visibleCount;
              return (
                <div
                  key={checkpoint}
                  className={cn(
                    "flex transform-gpu items-center gap-3 rounded-[14px] border border-slate-200/85 bg-white/78 px-3 py-2.5 transition-[opacity,transform] duration-[400ms]",
                    isVisible ? "translate-y-0 opacity-100" : "translate-y-3 opacity-0"
                  )}
                  style={{ transitionTimingFunction: CARD_EASE }}
                >
                  <div
                    className={cn(
                      "flex h-5 w-5 items-center justify-center rounded-full border transition-all duration-300",
                      isVisible
                        ? "scale-100 border-emerald-300 bg-emerald-100 shadow-[0_0_0_6px_rgba(16,185,129,0.14)]"
                        : "scale-75 border-slate-300 bg-white"
                    )}
                  >
                    <Check className={cn("h-3 w-3", isVisible ? "text-emerald-600" : "text-slate-400")} />
                  </div>
                  <p className="text-sm text-slate-700">{checkpoint}</p>
                </div>
              );
            })}
          </div>

          <div className={cn("mt-6 h-2 overflow-hidden rounded-full bg-slate-200/80", showCompletion ? "opacity-85" : "opacity-100")}>
            <div
              className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-500 transition-[width] duration-300 ease-in-out"
              style={{ width: `${Math.max(0, Math.min(100, progress)).toFixed(1)}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
