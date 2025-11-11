"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  AlertTriangle,
  Clock,
  Calendar,
  ChefHat,
  Lightbulb,
  Weight,
  Trash2,
} from "lucide-react";
import { useExpiringItems } from "../hooks/useTracking";
import { useDeleteItem } from "../hooks/useInventory";

export default function ExpiringItems() {
  const [days, setDays] = useState(3);
  const { data, isLoading, error } = useExpiringItems(days);
  const deleteItem = useDeleteItem();

  const handleDelete = (inventoryId: number, itemName: string) => {
    if (confirm(`Remove "${itemName}" from inventory?`)) {
      deleteItem.mutate(inventoryId);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription>
          Failed to load expiring items. Please try again.
        </AlertDescription>
      </Alert>
    );
  }

  if (!data) return null;

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case "urgent":
        return "destructive";
      case "high":
        return "warning";
      case "medium":
        return "secondary";
      default:
        return "outline";
    }
  };

  const getPriorityIcon = (priority: string) => {
    if (priority === "urgent") return <AlertTriangle className="h-4 w-4" />;
    return <Clock className="h-4 w-4" />;
  };

  return (
    <div className="space-y-6">
      {/* Header with Filter */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Expiring Soon</h2>
          <p className="text-sm text-muted-foreground">
            Items that need your attention
          </p>
        </div>
        <Select
          value={days.toString()}
          onValueChange={(value) => setDays(parseInt(value))}
        >
          <SelectTrigger className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="3">Next 3 days</SelectItem>
            <SelectItem value="7">Next 7 days</SelectItem>
            <SelectItem value="14">Next 14 days</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card className="border-red-200 bg-red-50/50">
          <CardContent className="p-4 text-center">
            <div className="flex items-center justify-center gap-2 mb-1">
              <AlertTriangle className="h-4 w-4 text-red-600" />
              <span className="text-2xl font-bold text-red-700">
                {data.urgent_count}
              </span>
            </div>
            <p className="text-xs text-red-700">Urgent (0-1 days)</p>
          </CardContent>
        </Card>

        <Card className="border-orange-200 bg-orange-50/50">
          <CardContent className="p-4 text-center">
            <div className="flex items-center justify-center gap-2 mb-1">
              <Clock className="h-4 w-4 text-orange-600" />
              <span className="text-2xl font-bold text-orange-700">
                {data.high_priority_count}
              </span>
            </div>
            <p className="text-xs text-orange-700">High (2-3 days)</p>
          </CardContent>
        </Card>

        <Card className="border-yellow-200 bg-yellow-50/50">
          <CardContent className="p-4 text-center">
            <div className="flex items-center justify-center gap-2 mb-1">
              <Calendar className="h-4 w-4 text-yellow-600" />
              <span className="text-2xl font-bold text-yellow-700">
                {data.medium_priority_count}
              </span>
            </div>
            <p className="text-xs text-yellow-700">Medium (4+ days)</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 text-center">
            <div className="flex items-center justify-center gap-2 mb-1">
              <ChefHat className="h-4 w-4 text-muted-foreground" />
              <span className="text-2xl font-bold">{data.total_expiring}</span>
            </div>
            <p className="text-xs text-muted-foreground">Total Items</p>
          </CardContent>
        </Card>
      </div>

      {/* Action Recommendations */}
      {data.action_recommendations && data.action_recommendations.length > 0 && (
        <Card className="border-blue-200 bg-blue-50/50">
          <CardHeader>
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Lightbulb className="h-4 w-4 text-blue-600" />
              AI Recommendations
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {data.action_recommendations.map((recommendation, index) => (
              <div key={index} className="flex items-start gap-2 text-sm">
                <div className="h-1.5 w-1.5 rounded-full bg-blue-600 mt-1.5 flex-shrink-0" />
                <p className="text-gray-700">{recommendation}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Empty State */}
      {data.items.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center">
            <ChefHat className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
            <p className="text-lg font-medium mb-1">All Clear!</p>
            <p className="text-sm text-muted-foreground">
              No items expiring in the next {days} days
            </p>
          </CardContent>
        </Card>
      )}

      {/* Expiring Items List */}
      {data.items.length > 0 && (
        <div className="space-y-3">
          {data.items.map((item) => (
            <Card
              key={item.inventory_id}
              className={`${
                item.priority === "urgent"
                  ? "border-red-200"
                  : item.priority === "high"
                  ? "border-orange-200"
                  : "border-yellow-200"
              }`}
            >
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-4 mb-3">
                  {/* Item Info */}
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <h3 className="font-semibold">{item.item_name}</h3>
                      <Badge
                        variant={getPriorityColor(item.priority) as any}
                        className="text-xs"
                      >
                        {getPriorityIcon(item.priority)}
                        <span className="ml-1">{item.priority.toUpperCase()}</span>
                      </Badge>
                    </div>

                    <div className="flex items-center gap-4 text-sm text-muted-foreground">
                      <div className="flex items-center gap-1">
                        <Weight className="h-3.5 w-3.5" />
                        <span>
                          {item.quantity_grams >= 1000
                            ? `${(item.quantity_grams / 1000).toFixed(1)} kg`
                            : `${item.quantity_grams} g`}
                        </span>
                      </div>
                      <div className="flex items-center gap-1">
                        <Calendar className="h-3.5 w-3.5" />
                        <span>
                          {item.days_remaining === 0
                            ? "Expires today"
                            : item.days_remaining === 1
                            ? "Expires tomorrow"
                            : item.days_remaining < 0
                            ? `Expired ${Math.abs(item.days_remaining)} days ago`
                            : `Expires in ${item.days_remaining} days`}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Expiry Date */}
                  <div className="text-right flex flex-col items-end gap-2">
                    <div>
                      <p className="text-xs text-muted-foreground">Expiry Date</p>
                      <p className="text-sm font-medium">
                        {new Date(item.expiry_date).toLocaleDateString()}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 text-destructive hover:text-destructive hover:bg-destructive/10"
                      onClick={() => handleDelete(item.inventory_id, item.item_name)}
                    >
                      <Trash2 className="h-4 w-4 mr-1" />
                      Remove
                    </Button>
                  </div>
                </div>

                {/* Recipe Suggestions */}
                {item.recipe_suggestions && item.recipe_suggestions.length > 0 && (
                  <div className="border-t pt-3 mt-3">
                    <p className="text-xs font-medium text-muted-foreground mb-2 flex items-center gap-1">
                      <ChefHat className="h-3.5 w-3.5" />
                      Recipes you can make with this ingredient:
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {item.recipe_suggestions.slice(0, 5).map((recipe) => (
                        <Button
                          key={recipe.recipe_id}
                          variant="outline"
                          size="sm"
                          className="text-xs h-7"
                        >
                          {recipe.recipe_name}
                          {recipe.match_percentage && (
                            <Badge
                              variant="secondary"
                              className="ml-2 text-xs px-1 py-0"
                            >
                              {Math.round(recipe.match_percentage)}%
                            </Badge>
                          )}
                        </Button>
                      ))}
                      {item.recipe_suggestions.length > 5 && (
                        <Button variant="ghost" size="sm" className="text-xs h-7">
                          +{item.recipe_suggestions.length - 5} more
                        </Button>
                      )}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
