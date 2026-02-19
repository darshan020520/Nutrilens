import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Package, AlertTriangle } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";

interface InventoryCardProps {
  data?: {
    expiring_soon_count: number;
    low_stock_count: number;
    out_of_stock_count: number;
    total_items: number;
  };
  isLoading: boolean;
}

export function InventoryCard({ data, isLoading }: InventoryCardProps) {
  if (isLoading) {
    return (
      <Card className="hover:shadow-lg transition-shadow cursor-pointer">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Inventory</CardTitle>
          <Package className="h-4 w-4 text-muted-foreground" />
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

  const alertCount = data.expiring_soon_count + data.low_stock_count;
  const hasAlerts = alertCount > 0;

  return (
    <Card className="hover:shadow-lg transition-shadow cursor-pointer">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">Inventory</CardTitle>
        <Package className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{data.total_items} items</div>
        
        {hasAlerts ? (
          <div className="mt-3 space-y-2">
            {data.expiring_soon_count > 0 && (
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-3 w-3 text-orange-500" />
                <span className="text-xs text-muted-foreground">
                  {data.expiring_soon_count} expiring soon
                </span>
              </div>
            )}
            {data.low_stock_count > 0 && (
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-3 w-3 text-yellow-500" />
                <span className="text-xs text-muted-foreground">
                  {data.low_stock_count} low stock
                </span>
              </div>
            )}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground mt-1">
            ✓ All items well stocked
          </p>
        )}

        {hasAlerts && (
          <Badge variant="destructive" className="mt-3 text-xs">
            {alertCount} Alert{alertCount > 1 ? 's' : ''}
          </Badge>
        )}
      </CardContent>
    </Card>
  );
}