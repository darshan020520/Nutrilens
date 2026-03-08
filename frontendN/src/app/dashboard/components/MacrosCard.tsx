import { Card } from "@/components/ui/card";
import { Activity } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";

interface MacrosCardProps {
  data?: {
    calories_consumed: number;
    calories_target: number;
    calories_percentage: number;
    protein_consumed: number;
    protein_target: number;
    protein_percentage: number;
    carbs_consumed: number;
    carbs_target: number;
    carbs_percentage: number;
    fat_consumed: number;
    fat_target: number;
    fat_percentage: number;
  };
  isLoading: boolean;
}

function MacroBar({
  label,
  consumed,
  target,
  pct,
  color,
}: {
  label: string;
  consumed: number;
  target: number;
  pct: number;
  color: string;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[11.5px] text-slate-500">{label}</span>
        <span className="text-[11.5px] font-medium text-slate-700">
          {Math.round(consumed)}g / {Math.round(target)}g
        </span>
      </div>
      <div className="h-[5px] w-full overflow-hidden rounded-full bg-slate-100">
        <div
          className="h-full rounded-full transition-all duration-700 ease-[cubic-bezier(0.4,0,0.2,1)]"
          style={{
            width: `${Math.min(pct, 100)}%`,
            background: color,
          }}
        />
      </div>
    </div>
  );
}

export function MacrosCard({ data, isLoading }: MacrosCardProps) {
  if (isLoading) {
    return (
      <Card className="group overflow-hidden transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(0,0,0,0.06)]">
        <div className="p-5">
          <div className="flex items-center justify-between mb-4">
            <Skeleton className="h-4 w-28" />
            <Skeleton className="h-8 w-8 rounded-lg" />
          </div>
          <Skeleton className="h-7 w-20 mb-2" />
          <Skeleton className="h-3 w-32 mb-4" />
          <div className="space-y-3">
            <Skeleton className="h-[5px] w-full rounded-full" />
            <Skeleton className="h-[5px] w-full rounded-full" />
            <Skeleton className="h-[5px] w-full rounded-full" />
          </div>
        </div>
      </Card>
    );
  }

  if (!data) return null;

  return (
    <Card className="group overflow-hidden transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(0,0,0,0.06)]">
      <div className="p-5">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <span className="text-[13px] font-semibold text-slate-900">Macros Progress</span>
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-50 text-slate-400 transition-colors group-hover:bg-emerald-50 group-hover:text-emerald-500">
            <Activity className="h-[15px] w-[15px]" />
          </div>
        </div>

        {/* Big number */}
        <div
          className="text-[28px] font-semibold leading-none tracking-tight text-slate-900"
          style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
        >
          {Math.round(data.calories_consumed)}
          <span className="ml-1.5 text-[14px] font-normal text-slate-300">cal</span>
        </div>
        <p className="mt-1.5 text-[11.5px] text-slate-400">
          of {Math.round(data.calories_target).toLocaleString()}
          <span className="mx-1.5 text-slate-300">|</span>
          {Math.round(data.calories_percentage)}%
        </p>

        {/* Macro bars */}
        <div className="mt-4 space-y-3">
          <MacroBar
            label="Protein"
            consumed={data.protein_consumed}
            target={data.protein_target}
            pct={data.protein_percentage}
            color="#1B7D5A"
          />
          <MacroBar
            label="Carbs"
            consumed={data.carbs_consumed}
            target={data.carbs_target}
            pct={data.carbs_percentage}
            color="#5B8DEF"
          />
          <MacroBar
            label="Fat"
            consumed={data.fat_consumed}
            target={data.fat_target}
            pct={data.fat_percentage}
            color="#E8913A"
          />
        </div>
      </div>
    </Card>
  );
}