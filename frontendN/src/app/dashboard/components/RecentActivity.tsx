import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Check, X, Sparkles } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";

interface ActivityItem {
  id: string;
  type: string;
  description: string;
  timestamp: string;
  icon: string;
}

interface RecentActivityProps {
  data?: {
    activities: ActivityItem[];
    total_count: number;
  };
  isLoading: boolean;
}

const activityStyles: Record<string, {
  bg: string;
  iconColor: string;
  icon: React.ReactNode;
  label: string;
  labelColor: string;
}> = {
  meal_logged: {
    bg: "bg-emerald-50",
    iconColor: "text-emerald-600",
    icon: <Check className="h-3.5 w-3.5" />,
    label: "Logged",
    labelColor: "text-emerald-600",
  },
  meal_skipped: {
    bg: "bg-orange-50",
    iconColor: "text-orange-500",
    icon: <X className="h-3.5 w-3.5" />,
    label: "Skipped",
    labelColor: "text-orange-500",
  },
  plan_generated: {
    bg: "bg-blue-50",
    iconColor: "text-blue-500",
    icon: <Sparkles className="h-3.5 w-3.5" />,
    label: "Generated",
    labelColor: "text-blue-500",
  },
};

const defaultStyle = {
  bg: "bg-slate-50",
  iconColor: "text-slate-500",
  icon: <Check className="h-3.5 w-3.5" />,
  label: "",
  labelColor: "text-slate-500",
};

export function RecentActivity({ data, isLoading }: RecentActivityProps) {
  const router = useRouter();

  if (isLoading) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="mb-5">
            <Skeleton className="h-5 w-32" />
          </div>
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex items-center gap-3">
                <Skeleton className="h-9 w-9 rounded-xl" />
                <div className="flex-1">
                  <Skeleton className="h-4 w-3/4 mb-1.5" />
                  <Skeleton className="h-3 w-1/3" />
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!data || data.activities.length === 0) {
    return (
      <Card>
        <CardContent className="p-6">
          <h3
            className="mb-4 text-[17px] font-medium text-slate-900"
            style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
          >
            Recent Activity
          </h3>
          <p className="py-8 text-center text-[13px] text-slate-400">
            No recent activity yet. Start logging meals to see your progress!
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <h3
            className="text-[17px] font-medium text-slate-900"
            style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
          >
            Recent Activity
          </h3>
          {data.total_count > 5 && (
            <button
              type="button"
              className="text-[12.5px] font-semibold text-emerald-600 transition-colors hover:text-emerald-700"
              onClick={() => router.push("/dashboard/meals?tab=history")}
            >
              View All
            </button>
          )}
        </div>

        {/* Activity list */}
        <div className="space-y-1">
          {data.activities.map((activity, i) => {
            const style = activityStyles[activity.type] || defaultStyle;
            const isLast = i === data.activities.length - 1;

            return (
              <div
                key={activity.id}
                className={cn(
                  "group flex items-center gap-3 rounded-xl px-2 py-3 transition-colors hover:bg-slate-50/80",
                  !isLast && "border-b border-slate-100"
                )}
              >
                {/* Icon */}
                <div
                  className={cn(
                    "flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl transition-colors",
                    style.bg,
                    style.iconColor
                  )}
                >
                  {style.icon}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <p className="truncate text-[13.5px] font-medium text-slate-800">
                    {activity.description}
                  </p>
                  <p className="mt-0.5 text-[11.5px] text-slate-400">
                    {formatDistanceToNow(new Date(activity.timestamp), { addSuffix: true })}
                  </p>
                </div>

                {/* Status badge */}
                {style.label && (
                  <span
                    className={cn(
                      "flex-shrink-0 text-[10px] font-semibold uppercase tracking-[0.4px] opacity-60 transition-opacity group-hover:opacity-100",
                      style.labelColor
                    )}
                  >
                    {style.label}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}