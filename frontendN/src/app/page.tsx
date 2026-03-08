"use client";

import Link from "next/link";
import {
  useEffect,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
  type ReactNode,
} from "react";
import { motion, useInView, useMotionValue, useSpring } from "framer-motion";
import {
  Activity,
  ArrowRight,
  Clock3,
  HeartHandshake,
  Layers3,
  Package,
  ScanSearch,
  ShieldCheck,
  ShoppingBasket,
  Sparkles,
  WandSparkles,
} from "lucide-react";

const EASE = [0.2, 0, 0, 1] as const;

const problemPoints = [
  {
    icon: Clock3,
    title: "Too many decisions",
    description: "Planning meals, tracking calories, and shopping all compete for your time.",
  },
  {
    icon: Activity,
    title: "Progress feels unclear",
    description: "You put in effort, but daily feedback rarely shows what is actually improving.",
  },
  {
    icon: ShoppingBasket,
    title: "Food waste and rebuys",
    description: "Pantry blind spots cause expiry losses, duplicate purchases, and rushed choices.",
  },
  {
    icon: HeartHandshake,
    title: "Hard to stay consistent",
    description: "Busy days break momentum when systems are rigid or hard to use quickly.",
  },
];

const howItWorks = [
  {
    id: 1,
    icon: ScanSearch,
    title: "Capture your real context",
    description: "Your goals, dietary style, pantry state, and routine become one live profile.",
  },
  {
    id: 2,
    icon: WandSparkles,
    title: "Generate an adaptive plan",
    description: "NutriLens builds meal plans, alternatives, and shopping actions that fit your day.",
  },
  {
    id: 3,
    icon: ShieldCheck,
    title: "Execute and auto-adjust",
    description: "Log meals, swap fast, and use AI guidance to stay on track even when plans shift.",
  },
];

const featureCards = [
  {
    icon: Layers3,
    title: "Unified command center",
    description: "Meals, tracking, inventory, and nutrition insights in one focused workflow.",
  },
  {
    icon: Sparkles,
    title: "Intelligent meal flow",
    description: "Generate, swap, skip, or log external meals with clear impact and recommendations.",
  },
  {
    icon: Package,
    title: "Inventory intelligence",
    description: "Low stock, expiry risk, receipt scanning, fuzzy add-items, and restock automation.",
  },
  {
    icon: Activity,
    title: "Operational analytics",
    description: "Daily adherence and macro trend visibility designed for quick decisions.",
  },
  {
    icon: ShoppingBasket,
    title: "Closed shopping loop",
    description: "From plan to grocery list to inventory update, all connected without manual friction.",
  },
  {
    icon: WandSparkles,
    title: "AI recipe creativity",
    description: "Generate recipes from available inventory in goal-aligned or guilt-free mode.",
  },
];

const testimonials = [
  {
    name: "Aarav",
    role: "Product manager, parent",
    quote:
      "I finally have one calm system that keeps food, goals, and shopping aligned during packed weeks.",
  },
  {
    name: "Maya",
    role: "Consultant, frequent traveler",
    quote:
      "Meal swaps and external logging made consistency realistic for my schedule, not theoretical.",
  },
  {
    name: "Rohan",
    role: "Strength training enthusiast",
    quote:
      "The inventory and meal planning loop removed guesswork and reduced wasted food almost immediately.",
  },
];

function useCountUp(target: number, durationMs = 1200): number {
  const [value, setValue] = useState(0);

  useEffect(() => {
    let rafId = 0;
    const startTime = performance.now();

    const tick = (now: number) => {
      const progress = Math.min((now - startTime) / durationMs, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(target * eased));
      if (progress < 1) {
        rafId = window.requestAnimationFrame(tick);
      }
    };

    rafId = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(rafId);
  }, [target, durationMs]);

  return value;
}

function Reveal({
  children,
  className,
  delay = 0,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const isInView = useInView(ref, { once: true, margin: "-10% 0px -12% 0px" });

  return (
    <motion.div
      ref={ref}
      className={className}
      initial={{ opacity: 0, y: 20 }}
      animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }}
      transition={{ duration: 0.4, ease: EASE, delay }}
    >
      {children}
    </motion.div>
  );
}

export default function Home() {
  const readiness = useCountUp(94, 1300);
  const weeklyAdherence = useCountUp(87, 1500);
  const caloriesLeft = useCountUp(460, 1200);

  const parallaxX = useMotionValue(0);
  const parallaxY = useMotionValue(0);
  const parallaxXSpring = useSpring(parallaxX, { stiffness: 90, damping: 22, mass: 0.6 });
  const parallaxYSpring = useSpring(parallaxY, { stiffness: 90, damping: 22, mass: 0.6 });

  const handleHeroMouseMove = (event: ReactMouseEvent<HTMLDivElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    const xPercent = (event.clientX - bounds.left) / bounds.width - 0.5;
    const yPercent = (event.clientY - bounds.top) / bounds.height - 0.5;

    parallaxX.set(xPercent * 10);
    parallaxY.set(yPercent * 10);
  };

  const resetHeroParallax = () => {
    parallaxX.set(0);
    parallaxY.set(0);
  };

  return (
    <div className="relative min-h-screen overflow-x-hidden bg-[#f6f5ef] text-slate-900">
      <motion.div
        className="pointer-events-none absolute inset-0 opacity-80"
        style={{
          backgroundImage:
            "radial-gradient(75% 90% at 10% 0%, rgba(16, 185, 129, 0.18) 0%, rgba(16,185,129,0) 56%), radial-gradient(65% 85% at 92% 8%, rgba(45, 212, 191, 0.14) 0%, rgba(45,212,191,0) 58%), linear-gradient(155deg, #f8f7f1 0%, #f3f4eb 48%, #f7f4ec 100%)",
          backgroundSize: "180% 180%",
        }}
        animate={{ backgroundPosition: ["0% 35%", "100% 65%", "0% 35%"] }}
        transition={{ duration: 42, repeat: Infinity, ease: "easeInOut" }}
      />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(55%_45%_at_20%_0%,rgba(255,255,255,0.58)_0%,transparent_70%)]" />
      <div className="pointer-events-none absolute -left-28 top-8 h-72 w-72 rounded-full bg-emerald-300/25 blur-3xl" />
      <div className="pointer-events-none absolute -right-28 top-20 h-72 w-72 rounded-full bg-teal-300/25 blur-3xl" />

      <motion.main
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.35, ease: EASE }}
        className="relative mx-auto flex w-full max-w-6xl flex-col px-6 pb-20 pt-12 md:px-8 md:pb-28 md:pt-16"
      >
        <section className="grid items-center gap-12 py-8 md:py-14 lg:grid-cols-[1fr_0.95fr]">
          <div className="space-y-7">
            <motion.div
              className="inline-flex items-center gap-2 rounded-full border border-white/80 bg-white/70 px-4 py-1.5 text-xs font-semibold tracking-[0.12em] text-slate-600 backdrop-blur-md"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.26, ease: EASE }}
            >
              <Sparkles className="h-3.5 w-3.5 text-emerald-600" />
              NUTRILENS FOR BUSY ROUTINES
            </motion.div>

            <div className="relative">
              <div className="pointer-events-none absolute -left-4 top-5 h-32 w-56 rounded-full bg-emerald-300/35 blur-3xl" />
              <h1 className="max-w-2xl text-balance text-[2.35rem] font-semibold leading-[1.04] tracking-[-0.025em] text-slate-950 md:text-[3.65rem]">
                <motion.span
                  className="block"
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.45, ease: EASE }}
                >
                  Stay on track with your eating,
                </motion.span>
                <motion.span
                  className="mt-2 block"
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.45, ease: EASE, delay: 0.12 }}
                >
                  even on your busiest days.
                </motion.span>
              </h1>
            </div>

            <motion.p
              className="max-w-xl text-pretty text-base leading-7 text-slate-600 md:text-lg"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.34, ease: EASE, delay: 0.18 }}
            >
              NutriLens turns meal planning, tracking, pantry management, and nutrition guidance into one calm,
              modern flow so consistency feels easy, not stressful.
            </motion.p>

            <motion.div
              className="flex flex-wrap items-center gap-4"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.34, ease: EASE, delay: 0.24 }}
            >
              <motion.div whileHover={{ scale: 1.03 }} transition={{ duration: 0.2, ease: EASE }}>
                <Link
                  href="/register"
                  className="inline-flex items-center rounded-[16px] bg-gradient-to-r from-emerald-600 to-teal-600 px-6 py-3 text-sm font-semibold text-white shadow-[0_14px_28px_-16px_rgba(5,150,105,0.65)] transition-all duration-200 ease-out hover:shadow-[0_18px_36px_-18px_rgba(5,150,105,0.78)]"
                >
                  Start Free
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </motion.div>

              <Link
                href="#how-it-works"
                className="group relative inline-flex items-center rounded-[14px] px-2 py-2 text-sm font-medium text-slate-700 transition-colors duration-200 hover:text-slate-900"
              >
                See how it works
                <span className="absolute bottom-1 left-2 h-[1.5px] w-0 bg-slate-700 transition-all duration-200 ease-out group-hover:w-[calc(100%-1rem)]" />
              </Link>
            </motion.div>
          </div>

          <motion.div
            className="relative"
            onMouseMove={handleHeroMouseMove}
            onMouseLeave={resetHeroParallax}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.42, ease: EASE, delay: 0.12 }}
          >
            <motion.div
              style={{ x: parallaxXSpring, y: parallaxYSpring }}
              className="relative rounded-[18px] border border-white/75 bg-white/78 p-5 shadow-[0_22px_45px_-30px_rgba(15,23,42,0.45)] backdrop-blur-xl"
            >
              <div className="mb-4 flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Today snapshot</p>
                <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-medium text-emerald-700">
                  On track
                </span>
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div className="rounded-[14px] border border-slate-200/90 bg-slate-50/70 p-3">
                  <p className="text-[11px] text-slate-500">Readiness</p>
                  <p className="text-2xl font-semibold text-slate-900">{readiness}%</p>
                </div>
                <div className="rounded-[14px] border border-slate-200/90 bg-slate-50/70 p-3">
                  <p className="text-[11px] text-slate-500">This week</p>
                  <p className="text-2xl font-semibold text-slate-900">{weeklyAdherence}%</p>
                </div>
                <div className="rounded-[14px] border border-slate-200/90 bg-slate-50/70 p-3">
                  <p className="text-[11px] text-slate-500">Calories left</p>
                  <p className="text-2xl font-semibold text-slate-900">{caloriesLeft}</p>
                </div>
              </div>

              <div className="mt-4 rounded-[14px] border border-slate-200/90 bg-white/80 p-3">
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-xs font-medium text-slate-600">Adherence trend</p>
                  <p className="text-xs text-slate-500">7 days</p>
                </div>
                <div className="flex h-20 items-end gap-1.5">
                  {[0.52, 0.66, 0.62, 0.78, 0.72, 0.86, 0.83].map((scaleY, index) => (
                    <motion.div
                      key={`bar-${index}`}
                      className="h-full w-full max-w-5 origin-bottom rounded-full bg-gradient-to-t from-teal-500 to-emerald-400/90"
                      initial={{ scaleY: 0.25, opacity: 0.45 }}
                      animate={{ scaleY, opacity: 1 }}
                      transition={{ duration: 0.45, ease: EASE, delay: 0.12 + index * 0.05 }}
                    />
                  ))}
                </div>
              </div>

              <motion.div
                whileHover={{ y: -3, scale: 1.01 }}
                transition={{ duration: 0.22, ease: EASE }}
                className="mt-4 rounded-[14px] border border-emerald-200/80 bg-emerald-50/70 p-3"
              >
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-emerald-900">Lunch meal card</p>
                  <span className="text-xs text-emerald-700">Ready to log</span>
                </div>
                <p className="mt-1 text-xs text-emerald-800/90">
                  High-protein bowl, macro aligned, 12 min prep. One tap to log or swap.
                </p>
              </motion.div>
            </motion.div>
          </motion.div>
        </section>

        <section id="problem" className="py-20 md:py-24">
          <div className="mb-8 h-px w-full bg-gradient-to-r from-transparent via-emerald-300 to-transparent" />
          <Reveal className="rounded-[18px] border border-white/75 bg-[linear-gradient(180deg,#f8f6ef_0%,#f2f4ea_100%)] px-6 py-8 shadow-[0_16px_36px_-26px_rgba(15,23,42,0.35)] md:px-8">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">The everyday problem</p>
            <h2 className="mt-2 max-w-3xl text-3xl font-semibold tracking-[-0.02em] text-slate-900 md:text-4xl">
              Healthy intent often fails because the system around it is fragmented.
            </h2>
            <p className="mt-3 max-w-2xl text-base leading-7 text-slate-600">
              NutriLens is built for regular people with real schedules. It reduces friction at each decision point so
              consistency feels calm and practical.
            </p>

            <ul className="mt-8 grid gap-4 md:grid-cols-2">
              {problemPoints.map((point, index) => {
                const Icon = point.icon;
                return (
                  <motion.li
                    key={point.title}
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: "-12% 0px -10% 0px" }}
                    transition={{ duration: 0.4, ease: EASE, delay: index * 0.08 }}
                    className="group rounded-[16px] border border-white/70 bg-white/70 p-4 transition-all duration-200 ease-out hover:border-emerald-200 hover:shadow-[0_12px_24px_-18px_rgba(16,185,129,0.55)]"
                  >
                    <div className="mb-2 inline-flex rounded-[12px] border border-slate-200/90 bg-slate-50 p-2 text-slate-600 transition-colors duration-200 group-hover:border-emerald-200 group-hover:text-emerald-700">
                      <Icon className="h-4 w-4" />
                    </div>
                    <p className="text-sm font-semibold text-slate-900">{point.title}</p>
                    <p className="mt-1 text-sm leading-6 text-slate-600">{point.description}</p>
                  </motion.li>
                );
              })}
            </ul>
          </Reveal>
        </section>

        <section id="how-it-works" className="py-20 md:py-24">
          <Reveal className="mb-8">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">How it works</p>
            <h2 className="mt-2 max-w-3xl text-3xl font-semibold tracking-[-0.02em] text-slate-900 md:text-4xl">
              Three focused steps, designed for speed and consistency.
            </h2>
          </Reveal>

          <div className="grid gap-4 md:grid-cols-3">
            {howItWorks.map((step, index) => {
              const Icon = step.icon;
              return (
                <Reveal key={step.id} delay={index * 0.08}>
                  <article className="group relative h-full rounded-[16px] border border-white/80 bg-white/72 p-5 shadow-[0_12px_30px_-24px_rgba(15,23,42,0.35)] backdrop-blur-sm transition-all duration-200 ease-out hover:-translate-y-1 hover:border-emerald-200 hover:shadow-[0_20px_38px_-24px_rgba(15,23,42,0.45)]">
                    <div className="absolute inset-0 rounded-[16px] border border-transparent transition-colors duration-200 group-hover:border-emerald-300/45" />
                    <div className="mb-3 inline-flex rounded-[12px] border border-slate-200/80 bg-slate-50 p-2.5 text-slate-700 transition-all duration-200 group-hover:rotate-[5deg] group-hover:text-emerald-700">
                      <Icon className="h-5 w-5" />
                    </div>
                    <p className="text-xs font-semibold tracking-[0.11em] text-slate-500">STEP {step.id}</p>
                    <h3 className="mt-1 text-lg font-semibold text-slate-900">{step.title}</h3>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{step.description}</p>

                    {step.id === 2 && (
                      <div className="pointer-events-none absolute -right-3 top-6 hidden w-48 rounded-[14px] border border-emerald-200/80 bg-white/92 p-3 opacity-0 shadow-[0_16px_34px_-24px_rgba(16,185,129,0.58)] transition-all duration-200 group-hover:translate-y-0 group-hover:opacity-100 xl:block">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-emerald-700">
                          Grocery preview
                        </p>
                        <ul className="mt-2 space-y-1 text-xs text-slate-600">
                          <li>Chicken breast x 2</li>
                          <li>Spinach x 1</li>
                          <li>Greek yogurt x 1</li>
                        </ul>
                      </div>
                    )}
                  </article>
                </Reveal>
              );
            })}
          </div>
        </section>

        <section id="features" className="py-20 md:py-24">
          <Reveal className="mb-8">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Capabilities</p>
            <h2 className="mt-2 max-w-3xl text-3xl font-semibold tracking-[-0.02em] text-slate-900 md:text-4xl">
              Premium execution surfaces for every nutrition workflow.
            </h2>
          </Reveal>

          <div className="grid gap-4 md:grid-cols-2">
            {featureCards.map((feature, index) => {
              const Icon = feature.icon;
              return (
                <Reveal key={feature.title} delay={(index % 2) * 0.08}>
                  <article className="group relative overflow-hidden rounded-[16px] border border-white/80 bg-white/55 p-5 shadow-[0_14px_34px_-26px_rgba(15,23,42,0.34)] backdrop-blur-md transition-all duration-200 ease-out hover:-translate-y-1 hover:shadow-[0_18px_40px_-24px_rgba(15,23,42,0.42)]">
                    <div className="pointer-events-none absolute inset-0 rounded-[16px] border border-transparent bg-[linear-gradient(130deg,rgba(16,185,129,0.16),rgba(45,212,191,0.04),rgba(16,185,129,0.0))] opacity-0 transition-opacity duration-200 group-hover:opacity-100" />
                    <div className="relative">
                      <div className="mb-3 inline-flex rounded-[12px] border border-slate-200/80 bg-white/75 p-2.5 text-slate-700 transition-colors duration-200 group-hover:text-emerald-700">
                        <Icon className="h-5 w-5" />
                      </div>
                      <h3 className="text-lg font-semibold text-slate-900">{feature.title}</h3>
                      <p className="mt-2 max-w-md text-sm leading-6 text-slate-600">{feature.description}</p>
                    </div>
                  </article>
                </Reveal>
              );
            })}
          </div>
        </section>

        <section id="social-proof" className="py-20 md:py-24">
          <Reveal className="relative overflow-hidden rounded-[18px] border border-white/75 bg-[linear-gradient(145deg,#f3f6ef_0%,#eef5f2_46%,#f4f4ec_100%)] px-6 py-8 shadow-[0_14px_32px_-22px_rgba(15,23,42,0.35)] md:px-8">
            <div className="pointer-events-none absolute -left-10 top-0 h-52 w-52 rounded-full bg-emerald-300/20 blur-3xl" />
            <div className="pointer-events-none absolute -right-10 bottom-0 h-52 w-52 rounded-full bg-teal-300/20 blur-3xl" />

            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Social proof</p>
            <h2 className="mt-2 max-w-3xl text-3xl font-semibold tracking-[-0.02em] text-slate-900 md:text-4xl">
              Trusted by people who need clarity in real life, not perfect conditions.
            </h2>

            <div className="mt-7 grid gap-4 md:grid-cols-3">
              {testimonials.map((item, index) => (
                <motion.article
                  key={item.name}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, margin: "-12% 0px -10% 0px" }}
                  transition={{ duration: 0.4, ease: EASE, delay: index * 0.08 }}
                  className="rounded-[16px] border border-white/75 bg-white/72 p-4 backdrop-blur-sm"
                >
                  <div className="mb-3 flex items-center gap-2.5">
                    <div className="h-8 w-8 rounded-full bg-gradient-to-br from-emerald-200 to-teal-200" />
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{item.name}</p>
                      <p className="text-xs text-slate-500">{item.role}</p>
                    </div>
                  </div>
                  <p className="text-sm leading-6 text-slate-600">{item.quote}</p>
                </motion.article>
              ))}
            </div>
          </Reveal>
        </section>

        <section className="py-20 md:py-24">
          <Reveal className="relative overflow-hidden rounded-[18px] border border-[#1e2f2c]/20 bg-[#123833] px-6 py-12 text-center text-white shadow-[0_22px_48px_-26px_rgba(18,56,51,0.75)] md:px-8 md:py-14">
            <div className="pointer-events-none absolute inset-x-0 top-0 h-40 bg-[radial-gradient(50%_50%_at_50%_0%,rgba(52,211,153,0.35)_0%,transparent_80%)]" />
            <h2 className="mx-auto max-w-3xl text-3xl font-semibold tracking-[-0.02em] md:text-4xl">
              A modern nutrition system that feels calm, fast, and reliable from day one.
            </h2>
            <p className="mx-auto mt-3 max-w-2xl text-base leading-7 text-emerald-50/85">
              Start free, set your profile, and let NutriLens handle the operational complexity while you focus on
              results.
            </p>

            <motion.div
              className="mt-8 inline-block"
              animate={{
                boxShadow: [
                  "0 0 0 0 rgba(45,212,191,0.18)",
                  "0 0 0 12px rgba(45,212,191,0.03)",
                  "0 0 0 0 rgba(45,212,191,0.18)",
                ],
              }}
              transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
            >
              <motion.div whileHover={{ scale: 1.03 }} transition={{ duration: 0.2, ease: EASE }}>
                <Link
                  href="/register"
                  className="inline-flex items-center rounded-[16px] bg-gradient-to-r from-emerald-400 to-teal-400 px-7 py-3.5 text-sm font-semibold text-slate-950 transition-all duration-200 ease-out hover:shadow-[0_16px_34px_-18px_rgba(16,185,129,0.65)]"
                >
                  Start Free
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </motion.div>
            </motion.div>
          </Reveal>
        </section>
      </motion.main>
    </div>
  );
}
