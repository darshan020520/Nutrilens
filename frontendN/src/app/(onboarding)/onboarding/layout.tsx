'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';

const steps = [
  { number: 1, path: '/onboarding/basic-info' },
  { number: 2, path: '/onboarding/goal-selection' },
  { number: 3, path: '/onboarding/path-selection' },
  { number: 4, path: '/onboarding/preferences' },
];

export default function OnboardingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const currentStepIndex = steps.findIndex((step) => pathname.includes(step.path));
  const activeStep = currentStepIndex >= 0 ? currentStepIndex + 1 : 1;
  const progressPercent = useMemo(() => (activeStep / steps.length) * 100, [activeStep]);

  const [displayedChildren, setDisplayedChildren] = useState<React.ReactNode>(children);
  const [leavingChildren, setLeavingChildren] = useState<React.ReactNode | null>(null);
  const [isEntering, setIsEntering] = useState(false);
  const [isLeaving, setIsLeaving] = useState(false);
  const [direction, setDirection] = useState<1 | -1>(1);

  const previousPathRef = useRef(pathname);
  const previousStepRef = useRef(activeStep);
  const displayedChildrenRef = useRef(children);

  useEffect(() => {
    displayedChildrenRef.current = displayedChildren;
  }, [displayedChildren]);

  useEffect(() => {
    if (pathname === previousPathRef.current) {
      setDisplayedChildren(children);
      displayedChildrenRef.current = children;
      return;
    }

    const nextDirection: 1 | -1 = activeStep >= previousStepRef.current ? 1 : -1;
    setDirection(nextDirection);

    setLeavingChildren(displayedChildrenRef.current);
    setDisplayedChildren(children);
    displayedChildrenRef.current = children;
    setIsEntering(true);
    setIsLeaving(false);

    const rafId = window.requestAnimationFrame(() => {
      setIsEntering(false);
      setIsLeaving(true);
    });

    const timeoutId = window.setTimeout(() => {
      setLeavingChildren(null);
      setIsLeaving(false);
    }, 350);

    previousPathRef.current = pathname;
    previousStepRef.current = activeStep;

    return () => {
      window.cancelAnimationFrame(rafId);
      window.clearTimeout(timeoutId);
    };
  }, [activeStep, children, pathname]);

  return (
    <div className="min-h-screen bg-[radial-gradient(90%_100%_at_12%_0%,#d9f4ea_0%,transparent_56%),radial-gradient(80%_90%_at_92%_8%,#e7efe3_0%,transparent_60%),linear-gradient(160deg,#f7f7f2_0%,#f4f6ef_46%,#f8f8f4_100%)]">
      <header className="border-b border-white/70 bg-white/76 backdrop-blur-md">
        <div className="mx-auto max-w-4xl px-4 py-5 md:px-6 md:py-6">
          <div className="mb-4 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500 to-teal-500 text-xs font-bold text-white shadow-[0_10px_20px_-12px_rgba(5,150,105,0.65)]">
                NL
              </div>
              <div>
                <p className="text-sm font-semibold tracking-[-0.01em] text-slate-900">Profile Setup</p>
                <p className="text-xs text-slate-500">Let&apos;s personalize your nutrition experience</p>
              </div>
            </div>

            <div className="rounded-full border border-slate-200/90 bg-white/90 px-3 py-1 text-xs font-medium text-slate-600">
              Step {activeStep} of {steps.length}
            </div>
          </div>

          <div className="h-1.5 overflow-hidden rounded-full bg-slate-200/70">
            <div
              className="h-full rounded-full bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 transition-[width] duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-8 md:px-6 md:py-10">
        <div className="relative min-h-[560px]">
          {leavingChildren ? (
            <div
              className={cn(
                'pointer-events-none absolute inset-0 transform-gpu transition-[transform,opacity] duration-[350ms] ease-[cubic-bezier(0.4,0,0.2,1)]',
                isLeaving
                  ? direction === 1
                    ? '-translate-x-3 opacity-0'
                    : 'translate-x-3 opacity-0'
                  : 'translate-x-0 opacity-100'
              )}
            >
              {leavingChildren}
            </div>
          ) : null}

          <div
            className={cn(
              'relative transform-gpu transition-[transform,opacity] duration-[350ms] ease-[cubic-bezier(0.4,0,0.2,1)]',
              isEntering
                ? direction === 1
                  ? 'translate-x-3 opacity-0'
                  : '-translate-x-3 opacity-0'
                : 'translate-x-0 opacity-100'
            )}
          >
            {displayedChildren}
          </div>
        </div>
      </main>
    </div>
  );
}
