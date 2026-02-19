import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Activity } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";

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

export function MacrosCard({ data, isLoading }: MacrosCardProps) {
  if (isLoading) {
    return (
      <Card className="hover:shadow-lg transition-shadow cursor-pointer">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Macros Progress</CardTitle>
          <Activity className="h-4 w-4 text-muted-foreground" />
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

  const getProgressColor = (percentage: number) => {
    if (percentage >= 90 && percentage <= 110) return "bg-green-500";
    if (percentage >= 80 && percentage <= 120) return "bg-yellow-500";
    return "bg-red-500";
  };

  return (
    <Card className="hover:shadow-lg transition-shadow cursor-pointer">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">Macros Progress</CardTitle>
        <Activity className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">
          {Math.round(data.calories_consumed)} cal
        </div>
        <p className="text-xs text-muted-foreground">
          of {Math.round(data.calories_target)} • {Math.round(data.calories_percentage)}%
        </p>

        <div className="mt-3 space-y-2">
          {/* Protein */}
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-muted-foreground">Protein</span>
              <span className="font-medium">
                {Math.round(data.protein_consumed)}g / {Math.round(data.protein_target)}g
              </span>
            </div>
            <Progress 
              value={Math.min(data.protein_percentage, 100)} 
              className="h-1.5"
            />
          </div>

          {/* Carbs */}
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-muted-foreground">Carbs</span>
              <span className="font-medium">
                {Math.round(data.carbs_consumed)}g / {Math.round(data.carbs_target)}g
              </span>
            </div>
            <Progress 
              value={Math.min(data.carbs_percentage, 100)} 
              className="h-1.5"
            />
          </div>

          {/* Fat */}
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-muted-foreground">Fat</span>
              <span className="font-medium">
                {Math.round(data.fat_consumed)}g / {Math.round(data.fat_target)}g
              </span>
            </div>
            <Progress 
              value={Math.min(data.fat_percentage, 100)} 
              className="h-1.5"
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}