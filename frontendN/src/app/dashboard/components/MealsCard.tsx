import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { UtensilsCrossed, Clock } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface MealsCardProps {
  data?: {
    meals_planned: number;
    meals_consumed: number;
    meals_skipped: number;
    next_meal: string | null;
    next_meal_time: string | null;
  };
  isLoading: boolean;
  pulseFirstAction?: boolean;
}

export function MealsCard({ data, isLoading, pulseFirstAction = false }: MealsCardProps) {
  if (isLoading) {
    return (
      <Card className="group relative overflow-hidden transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(0,0,0,0.06)]">
        <div className="h-[3px] w-full bg-gradient-to-r from-emerald-500 via-teal-400 to-amber-300" />
        <div className="p-5">
          <div className="flex items-center justify-between mb-4">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-8 w-8 rounded-lg" />
          </div>
          <Skeleton className="h-7 w-28 mb-2" />
          <Skeleton className="h-4 w-full" />
        </div>
      </Card>
    );
  }

  if (!data) return null;

  const isPlateEmpty = data.meals_consumed === 0;
  const progress = data.meals_planned > 0
    ? Math.round((data.meals_consumed / data.meals_planned) * 100)
    : 0;

  return (
    <Card className="group relative overflow-hidden transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(0,0,0,0.06)]">
      {/* Top accent bar */}
      <div className="h-[3px] w-full bg-gradient-to-r from-emerald-500 via-teal-400 to-amber-300" />

      <div className="p-5">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <span className="text-[13px] font-semibold text-slate-900">Today&apos;s Meals</span>
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-50 text-slate-400 transition-colors group-hover:bg-emerald-50 group-hover:text-emerald-500">
            <UtensilsCrossed className="h-[15px] w-[15px]" />
          </div>
        </div>

        {/* Content */}
        {isPlateEmpty ? (
          <div className="space-y-3">
            <p className="text-[14px] font-semibold text-slate-800">Your plate is empty today.</p>
            <Link
              href="/dashboard/meals?tab=today"
              className={cn(
                "inline-flex items-center gap-1 rounded-lg bg-emerald-50 px-3 py-1.5 text-[12.5px] font-semibold text-emerald-700 transition-all duration-200 hover:bg-emerald-100",
                pulseFirstAction ? "animate-[first-cta-pulse_1s_ease-out_1]" : ""
              )}
            >
              Log your first meal
              <span className="ml-0.5 transition-transform duration-200 group-hover:translate-x-0.5">→</span>
            </Link>
          </div>
        ) : (
          <>
            <div
              className="text-[28px] font-semibold leading-none tracking-tight text-slate-900"
              style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
            >
              {data.meals_consumed}
              <span className="text-[16px] font-normal text-slate-300"> / {data.meals_planned}</span>
            </div>
            <p className="mt-2 text-[11.5px] text-slate-500">
              {data.meals_skipped > 0 && (
                <span className="text-amber-600">{data.meals_skipped} skipped · </span>
              )}
              {progress}% complete
            </p>
          </>
        )}

        {/* Next meal */}
        {data.next_meal && (
          <div className="mt-4 flex items-center gap-2 border-t border-slate-100 pt-3">
            <Clock className="h-3 w-3 text-slate-400" />
            <p className="text-[11.5px] text-slate-500">
              Next: <span className="font-medium text-slate-700">{data.next_meal}</span> at {data.next_meal_time}
            </p>
          </div>
        )}
      </div>
    </Card>
  );
}