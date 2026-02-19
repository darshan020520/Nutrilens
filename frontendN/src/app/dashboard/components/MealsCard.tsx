import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { UtensilsCrossed, Clock } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";

interface MealsCardProps {
  data?: {
    meals_planned: number;
    meals_consumed: number;
    meals_skipped: number;
    next_meal: string | null;
    next_meal_time: string | null;
  };
  isLoading: boolean;
}

export function MealsCard({ data, isLoading }: MealsCardProps) {
  if (isLoading) {
    return (
      <Card className="hover:shadow-lg transition-shadow cursor-pointer">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Today's Meals</CardTitle>
          <UtensilsCrossed className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-8 w-20 mb-2" />
          <Skeleton className="h-4 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (!data) {
    return null;
  }

  const progress = data.meals_planned > 0
    ? Math.round((data.meals_consumed / data.meals_planned) * 100)
    : 0;

  return (
    <Card className="hover:shadow-lg transition-shadow cursor-pointer">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">Today's Meals</CardTitle>
        <UtensilsCrossed className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">
          {data.meals_consumed} / {data.meals_planned}
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          {data.meals_skipped > 0 && `${data.meals_skipped} skipped • `}
          {progress}% complete
        </p>
        
        {data.next_meal && (
          <div className="mt-3 pt-3 border-t flex items-center gap-2">
            <Clock className="h-3 w-3 text-muted-foreground" />
            <p className="text-xs text-muted-foreground">
              Next: {data.next_meal} at {data.next_meal_time}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}