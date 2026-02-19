import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Target, Flame } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";

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
      <Card className="hover:shadow-lg transition-shadow cursor-pointer">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Goal Progress</CardTitle>
          <Target className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-8 w-24 mb-2" />
          <Skeleton className="h-2 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (!data) {
    return null;
  }

  const formatGoalType = (type: string) => {
    return type
      .replace(/_/g, " ")
      .replace(/\b\w/g, (l) => l.toUpperCase());
  };

  const getWeightChangeText = () => {
    if (data.goal_type.toLowerCase().includes("lose")) {
      return `${Math.abs(data.weight_change).toFixed(1)}kg to go`;
    } else if (data.goal_type.toLowerCase().includes("gain")) {
      return `${Math.abs(data.weight_change).toFixed(1)}kg to go`;
    } else {
      return "Maintaining";
    }
  };

  return (
    <Card className="hover:shadow-lg transition-shadow cursor-pointer">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">Goal Progress</CardTitle>
        <Target className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">
          {Math.round(data.goal_progress_percentage)}%
        </div>
        <p className="text-xs text-muted-foreground">
          {data.current_weight.toFixed(1)}kg → {data.target_weight.toFixed(1)}kg
        </p>

        <Progress 
          value={data.goal_progress_percentage} 
          className="h-2 mt-3"
        />

        <div className="mt-3 pt-3 border-t space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Goal</span>
            <span className="font-medium">
              {formatGoalType(data.goal_type)}
            </span>
          </div>
          
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Remaining</span>
            <span className="font-medium">{getWeightChangeText()}</span>
          </div>

          {data.current_streak > 0 && (
            <div className="flex items-center gap-2 pt-2">
              <Flame className="h-4 w-4 text-orange-500" />
              <span className="text-xs font-medium">
                {data.current_streak} day streak
              </span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}