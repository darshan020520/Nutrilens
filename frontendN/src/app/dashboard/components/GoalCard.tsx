import { Card } from "@/components/ui/card";
import { Target, Flame } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";

interface GoalCardProps {
  data?: {
    goal_type: string;
    current_weight: number;
    target_weight: number;
    weight_change: number;
    current_streak: number;
    goal_progress_percentage: number;
  };
  isLoading: boolean;
}

export function GoalCard({ data, isLoading }: GoalCardProps) {
  if (isLoading) {
    return (
      <Card className="group overflow-hidden transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(0,0,0,0.06)]">
        <div className="p-5">
          <div className="flex items-center justify-between mb-4">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-8 w-8 rounded-lg" />
          </div>
          <Skeleton className="h-7 w-16 mb-2" />
          <Skeleton className="h-[5px] w-full rounded-full" />
        </div>
      </Card>
    );
  }

  if (!data) return null;

  const formatGoalType = (type: string) =>
    type.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());

  const getWeightChangeText = () => {
    if (data.goal_type.toLowerCase().includes("lose") || data.goal_type.toLowerCase().includes("gain")) {
      return `${Math.abs(data.weight_change).toFixed(1)}kg to go`;
    }
    return "Maintaining";
  };

  const pct = Math.max(0, Math.min(100, data.goal_progress_percentage));

  return (
    <Card className="group overflow-hidden transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(0,0,0,0.06)]">
      <div className="p-5">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <span className="text-[13px] font-semibold text-slate-900">Goal Progress</span>
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-50 text-slate-400 transition-colors group-hover:bg-emerald-50 group-hover:text-emerald-500">
            <Target className="h-[15px] w-[15px]" />
          </div>
        </div>

        {/* Big number */}
        <div
          className="text-[28px] font-semibold leading-none tracking-tight text-slate-900"
          style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
        >
          {Math.round(data.goal_progress_percentage)}
          <span className="text-[16px] font-normal text-slate-300">%</span>
        </div>
        <p className="mt-1.5 text-[11.5px] text-slate-400">
          {data.current_weight.toFixed(1)}kg → {data.target_weight.toFixed(1)}kg
        </p>

        {/* Progress bar */}
        <div className="mt-3 h-[5px] w-full overflow-hidden rounded-full bg-slate-100">
          <div
            className="h-full rounded-full transition-all duration-700 ease-[cubic-bezier(0.4,0,0.2,1)]"
            style={{
              width: `${pct}%`,
              background: pct >= 70
                ? "linear-gradient(90deg, #1B7D5A, #22956B)"
                : pct >= 30
                ? "linear-gradient(90deg, #E8913A, #F0A854)"
                : "linear-gradient(90deg, #EF4444, #F87171)",
            }}
          />
        </div>

        {/* Details */}
        <div className="mt-4 space-y-2.5 border-t border-slate-100 pt-3.5">
          <div className="flex items-center justify-between">
            <span className="text-[11.5px] text-slate-500">Goal</span>
            <span className="text-[11.5px] font-semibold text-slate-800">
              {formatGoalType(data.goal_type)}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[11.5px] text-slate-500">Remaining</span>
            <span className="text-[11.5px] font-semibold text-slate-800">{getWeightChangeText()}</span>
          </div>

          {data.current_streak > 0 && (
            <div className="flex items-center gap-2 pt-1.5">
              <div className="flex h-5 w-5 items-center justify-center rounded-md bg-orange-50">
                <Flame className="h-3 w-3 text-orange-500" />
              </div>
              <span className="text-[12px] font-semibold text-slate-700">
                {data.current_streak} day streak
              </span>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}