import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDistanceToNow } from "date-fns";

interface ActivityItem {
  id: number;
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

export function RecentActivity({ data, isLoading }: RecentActivityProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Recent Activity</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex items-center gap-4">
                <Skeleton className="h-10 w-10 rounded-full" />
                <div className="flex-1">
                  <Skeleton className="h-4 w-3/4 mb-2" />
                  <Skeleton className="h-3 w-1/2" />
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
        <CardHeader>
          <CardTitle>Recent Activity</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground text-center py-8">
            No recent activity yet. Start logging meals to see your progress!
          </p>
        </CardContent>
      </Card>
    );
  }

  const getActivityColor = (type: string) => {
    switch (type) {
      case "meal_logged":
        return "bg-green-100 text-green-800";
      case "meal_skipped":
        return "bg-yellow-100 text-yellow-800";
      case "plan_generated":
        return "bg-blue-100 text-blue-800";
      default:
        return "bg-slate-100 text-slate-800";
    }
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Recent Activity</CardTitle>
        {data.total_count > 5 && (
          <button className="text-sm text-primary hover:underline">
            View All
          </button>
        )}
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {data.activities.map((activity) => (
            <div
              key={activity.id}
              className="flex items-start gap-4 pb-4 border-b last:border-0 last:pb-0"
            >
              <div
                className={`flex-shrink-0 h-10 w-10 rounded-full flex items-center justify-center text-lg ${getActivityColor(
                  activity.type
                )}`}
              >
                {activity.icon}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-900 truncate">
                  {activity.description}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  {formatDistanceToNow(new Date(activity.timestamp), {
                    addSuffix: true,
                  })}
                </p>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}