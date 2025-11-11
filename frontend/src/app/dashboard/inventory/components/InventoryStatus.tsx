"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import {
  Package,
  AlertTriangle,
  TrendingDown,
  Grid3x3,
  Lightbulb,
  Weight,
} from "lucide-react";
import { useInventoryStatus } from "../hooks/useInventory";

export default function InventoryStatus() {
  const { data: status, isLoading, error } = useInventoryStatus();

  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <Card key={i}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-4 rounded-full" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-8 w-16 mb-2" />
              <Skeleton className="h-3 w-32" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription>
          Failed to load inventory status. Please try again.
        </AlertDescription>
      </Alert>
    );
  }

  if (!status) return null;

  const hasExpiringItems = status.expiring_soon && status.expiring_soon.length > 0;
  const hasLowStock = status.low_stock && status.low_stock.length > 0;

  return (
    <div className="space-y-4">
      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Total Items */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Items</CardTitle>
            <Package className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{status.total_items}</div>
            <p className="text-xs text-muted-foreground mt-1">
              {(status.total_weight_g / 1000).toFixed(1)} kg total weight
            </p>
          </CardContent>
        </Card>

        {/* Expiring Soon */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Expiring Soon</CardTitle>
            <AlertTriangle className="h-4 w-4 text-orange-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {status.expiring_soon?.length || 0}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {hasExpiringItems ? (
                <span className="text-orange-600 font-medium">
                  Needs attention
                </span>
              ) : (
                "All items fresh"
              )}
            </p>
          </CardContent>
        </Card>

        {/* Low Stock */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Low Stock</CardTitle>
            <TrendingDown className="h-4 w-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {status.low_stock?.length || 0}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {hasLowStock ? (
                <span className="text-yellow-600 font-medium">
                  Consider restocking
                </span>
              ) : (
                "Stock levels good"
              )}
            </p>
          </CardContent>
        </Card>

        {/* Categories */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Categories</CardTitle>
            <Grid3x3 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {Object.keys(status.categories || {}).length}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {status.estimated_days_remaining ? (
                <>~{status.estimated_days_remaining} days supply</>
              ) : (
                "Diverse inventory"
              )}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* AI Recommendations - Always visible if present */}
      {status.ai_recommendations && status.ai_recommendations.length > 0 && (
        <Card className="border-blue-200 bg-blue-50/50">
          <CardHeader>
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Lightbulb className="h-4 w-4 text-blue-600" />
              AI Recommendations
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {status.ai_recommendations.map((recommendation, index) => (
              <div
                key={index}
                className="flex items-start gap-2 text-sm"
              >
                <div className="h-1.5 w-1.5 rounded-full bg-blue-600 mt-1.5 flex-shrink-0" />
                <p className="text-gray-700">{recommendation}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Nutritional Capacity (if available) */}
      {status.nutritional_capacity && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Weight className="h-4 w-4 text-muted-foreground" />
              Available Nutrients
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <p className="text-xs text-muted-foreground">Calories</p>
                <p className="text-lg font-semibold">
                  {Math.round(status.nutritional_capacity.calories || 0)}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Protein</p>
                <p className="text-lg font-semibold">
                  {Math.round(status.nutritional_capacity.protein_g || 0)}g
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Carbs</p>
                <p className="text-lg font-semibold">
                  {Math.round(status.nutritional_capacity.carbs_g || 0)}g
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Fats</p>
                <p className="text-lg font-semibold">
                  {Math.round(status.nutritional_capacity.fat_g || 0)}g
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Category Breakdown */}
      {status.categories && Object.keys(status.categories).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">
              Items by Category
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {Object.entries(status.categories).map(([category, count]) => (
                <Badge key={category} variant="secondary">
                  {category}: {count}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
