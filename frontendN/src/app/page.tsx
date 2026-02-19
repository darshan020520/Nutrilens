import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Activity, Bot, Package, UtensilsCrossed } from "lucide-react";

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-[#f6f5f1] to-white">
      <div className="max-w-6xl mx-auto px-6 py-16 md:py-24 space-y-14">
        <header className="space-y-6 text-center">
          <div className="inline-flex items-center gap-2 rounded-full border px-4 py-1 text-sm bg-white/70">
            <span className="h-2 w-2 rounded-full bg-primary" />
            NutriLens Performance OS
          </div>
          <h1 className="text-5xl md:text-6xl font-bold tracking-tight max-w-4xl mx-auto">
            Plan. Eat. Track. Adapt.
          </h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            AI-powered nutrition workflows combining intelligent meal planning, pantry operations,
            and context-aware coaching.
          </p>
          <div className="flex gap-3 justify-center">
            <Link href="/register">
              <Button size="lg">Get Started</Button>
            </Link>
            <Link href="/login">
              <Button size="lg" variant="outline">Log In</Button>
            </Link>
          </div>
        </header>

        <section className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
          <article className="rounded-xl border bg-white p-5 space-y-3">
            <UtensilsCrossed className="h-6 w-6 text-primary" />
            <h2 className="font-semibold">Meal Command Center</h2>
            <p className="text-sm text-muted-foreground">Daily execution with log, skip, external, and swap flows.</p>
          </article>
          <article className="rounded-xl border bg-white p-5 space-y-3">
            <Package className="h-6 w-6 text-primary" />
            <h2 className="font-semibold">Pantry Intelligence</h2>
            <p className="text-sm text-muted-foreground">Inventory health, receipt scanning, expiry risk, and restock actions.</p>
          </article>
          <article className="rounded-xl border bg-white p-5 space-y-3">
            <Activity className="h-6 w-6 text-primary" />
            <h2 className="font-semibold">Operational Analytics</h2>
            <p className="text-sm text-muted-foreground">Adherence and macro trends to keep your goals on track.</p>
          </article>
          <article className="rounded-xl border bg-white p-5 space-y-3">
            <Bot className="h-6 w-6 text-primary" />
            <h2 className="font-semibold">AI Nutrition Coach</h2>
            <p className="text-sm text-muted-foreground">Context-aware recommendations with direct, actionable guidance.</p>
          </article>
        </section>
      </div>
    </div>
  );
}
