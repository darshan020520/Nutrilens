"use client";

import { useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ShoppingCart,
  AlertTriangle,
  TrendingDown,
  Lightbulb,
  Download,
  CheckCircle2,
  Copy,
  Package,
  Loader2,
  Plus,
} from "lucide-react";
import { useRestockList } from "../hooks/useTracking";
import { useBulkAddFromRestock } from "../hooks/useInventory";
import { toast } from "sonner";
import { RestockItem } from "../types";

export default function RestockList() {
  const { data, isLoading, error } = useRestockList();
  const bulkAdd = useBulkAddFromRestock();
  const [selectedItems, setSelectedItems] = useState<Set<number>>(new Set());
  const [quantities, setQuantities] = useState<Record<number, number>>({});

  // Combine all items into a single array with their priority
  const allItems = useMemo(() => {
    if (!data) return [];

    const items: (RestockItem & { priorityCategory: string })[] = [];

    data.urgent_items.forEach((item) => {
      items.push({ ...item, priorityCategory: "urgent" });
    });

    data.soon_items.forEach((item) => {
      items.push({ ...item, priorityCategory: "soon" });
    });

    data.routine_items.forEach((item) => {
      items.push({ ...item, priorityCategory: "routine" });
    });

    return items;
  }, [data]);

  const handleToggleSelect = (item: RestockItem) => {
    const newSelected = new Set(selectedItems);
    const newQuantities = { ...quantities };

    if (newSelected.has(item.item_id)) {
      newSelected.delete(item.item_id);
      delete newQuantities[item.item_id];
    } else {
      newSelected.add(item.item_id);
      newQuantities[item.item_id] = item.recommended_quantity;
    }

    setSelectedItems(newSelected);
    setQuantities(newQuantities);
  };

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      const allIds = new Set(allItems.map((item) => item.item_id));
      const allQuantities: Record<number, number> = {};
      allItems.forEach((item) => {
        allQuantities[item.item_id] = item.recommended_quantity;
      });
      setSelectedItems(allIds);
      setQuantities(allQuantities);
    } else {
      setSelectedItems(new Set());
      setQuantities({});
    }
  };

  const handleQuantityChange = (itemId: number, value: number) => {
    setQuantities((prev) => ({
      ...prev,
      [itemId]: Math.max(0, value),
    }));
  };

  const handleBulkAdd = async () => {
    const itemsToAdd = allItems
      .filter((item) => selectedItems.has(item.item_id))
      .map((item) => ({
        item_id: item.item_id,
        quantity_grams: quantities[item.item_id] ?? item.recommended_quantity,
      }));

    if (itemsToAdd.length === 0) {
      toast.error("No items selected");
      return;
    }

    await bulkAdd.mutateAsync({ items: itemsToAdd });
    setSelectedItems(new Set());
    setQuantities({});
  };

  const handleCopyList = () => {
    if (allItems.length === 0) return;

    const listText = allItems
      .map((item) => `${item.item_name} - ${item.recommended_quantity}g (${item.priority})`)
      .join("\n");

    navigator.clipboard.writeText(listText);
    toast.success("Shopping list copied to clipboard!");
  };

  const handleExportList = () => {
    if (allItems.length === 0) return;

    const listText = allItems
      .map((item) => `- ${item.item_name} - ${item.recommended_quantity}g (${item.priority})`)
      .join("\n");

    const blob = new Blob([`Shopping List\n\n${listText}`], {
      type: "text/plain",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `shopping-list-${new Date().toISOString().split("T")[0]}.txt`;
    a.click();
    URL.revokeObjectURL(url);

    toast.success("Shopping list exported!");
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription>
          Failed to load shopping list. Please try again.
        </AlertDescription>
      </Alert>
    );
  }

  if (!data) return null;

  const getPriorityColor = (priority: string) => {
    if (priority === "urgent") return "destructive";
    if (priority === "soon") return "warning";
    return "secondary";
  };

  const getPriorityIcon = (priority: string) => {
    if (priority === "urgent")
      return <AlertTriangle className="h-3.5 w-3.5" />;
    if (priority === "soon")
      return <TrendingDown className="h-3.5 w-3.5" />;
    return <Package className="h-3.5 w-3.5" />;
  };

  const isAllSelected = allItems.length > 0 && selectedItems.size === allItems.length;

  const formatQuantity = (grams: number) => {
    if (grams >= 1000) return `${(grams / 1000).toFixed(1)} kg`;
    return `${Math.round(grams)} g`;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Shopping List</h2>
          <p className="text-sm text-muted-foreground">
            Smart recommendations based on your inventory
          </p>
        </div>
        {allItems.length > 0 && (
          <div className="flex gap-2">
            {selectedItems.size > 0 && (
              <Button
                onClick={handleBulkAdd}
                disabled={bulkAdd.isPending}
                size="sm"
                className="bg-green-600 hover:bg-green-700"
              >
                {bulkAdd.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Adding...
                  </>
                ) : (
                  <>
                    <Plus className="mr-2 h-4 w-4" />
                    Add {selectedItems.size} to Inventory
                  </>
                )}
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={handleCopyList}>
              <Copy className="mr-2 h-4 w-4" />
              Copy List
            </Button>
            <Button variant="outline" size="sm" onClick={handleExportList}>
              <Download className="mr-2 h-4 w-4" />
              Export
            </Button>
          </div>
        )}
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="p-4 text-center">
            <div className="flex items-center justify-center gap-2 mb-1">
              <ShoppingCart className="h-4 w-4 text-muted-foreground" />
              <span className="text-2xl font-bold">{data.total_items}</span>
            </div>
            <p className="text-xs text-muted-foreground">Items to Buy</p>
          </CardContent>
        </Card>

        <Card className="border-red-200 bg-red-50/50">
          <CardContent className="p-4 text-center">
            <div className="flex items-center justify-center gap-2 mb-1">
              <AlertTriangle className="h-4 w-4 text-red-600" />
              <span className="text-2xl font-bold text-red-700">
                {data.urgent_items.length}
              </span>
            </div>
            <p className="text-xs text-red-700">Urgent</p>
          </CardContent>
        </Card>

        <Card className="border-yellow-200 bg-yellow-50/50">
          <CardContent className="p-4 text-center">
            <div className="flex items-center justify-center gap-2 mb-1">
              <TrendingDown className="h-4 w-4 text-yellow-600" />
              <span className="text-2xl font-bold text-yellow-700">
                {data.soon_items.length}
              </span>
            </div>
            <p className="text-xs text-yellow-700">Soon</p>
          </CardContent>
        </Card>

        <Card className="border-green-200 bg-green-50/50">
          <CardContent className="p-4 text-center">
            <div className="flex items-center justify-center gap-2 mb-1">
              <CheckCircle2 className="h-4 w-4 text-green-600" />
              <span className="text-2xl font-bold text-green-700">
                {selectedItems.size}
              </span>
            </div>
            <p className="text-xs text-green-700">Selected</p>
          </CardContent>
        </Card>
      </div>

      {/* AI Recommendations */}
      {data.shopping_strategy && data.shopping_strategy.length > 0 && (
        <Card className="border-blue-200 bg-blue-50/50">
          <CardHeader>
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Lightbulb className="h-4 w-4 text-blue-600" />
              Shopping Strategy
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {data.shopping_strategy.map((recommendation, index) => (
              <div key={index} className="flex items-start gap-2 text-sm">
                <div className="h-1.5 w-1.5 rounded-full bg-blue-600 mt-1.5 flex-shrink-0" />
                <p className="text-gray-700">{recommendation}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Empty State */}
      {allItems.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center">
            <ShoppingCart className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
            <p className="text-lg font-medium mb-1">Your Inventory Looks Good!</p>
            <p className="text-sm text-muted-foreground">
              No items need restocking at the moment
            </p>
          </CardContent>
        </Card>
      )}

      {/* Shopping List */}
      {allItems.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Checkbox
                  checked={isAllSelected}
                  onCheckedChange={(checked) => handleSelectAll(!!checked)}
                />
                <CardTitle className="text-base">
                  Items to Buy ({allItems.length})
                </CardTitle>
              </div>
              {selectedItems.size > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setSelectedItems(new Set());
                    setQuantities({});
                  }}
                >
                  Clear Selection
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {allItems.map((item) => {
                const isSelected = selectedItems.has(item.item_id);
                const currentQty = quantities[item.item_id] ?? item.recommended_quantity;

                return (
                  <div
                    key={item.item_id}
                    className={`flex items-start gap-3 p-3 rounded-lg border transition-all ${
                      isSelected
                        ? "bg-blue-50 border-blue-200"
                        : "hover:bg-muted/30"
                    }`}
                  >
                    <Checkbox
                      checked={isSelected}
                      onCheckedChange={() => handleToggleSelect(item)}
                      className="mt-1"
                    />

                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <h4 className="font-semibold">
                          {item.item_name}
                        </h4>
                        <Badge
                          variant={getPriorityColor(item.priority) as any}
                          className="text-xs flex-shrink-0"
                        >
                          {getPriorityIcon(item.priority)}
                          <span className="ml-1">{item.priority.toUpperCase()}</span>
                        </Badge>
                      </div>

                      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                        {item.category && (
                          <Badge variant="outline" className="text-xs">
                            {item.category}
                          </Badge>
                        )}

                        <span>
                          Current: {formatQuantity(item.current_quantity)}
                        </span>

                        {isSelected ? (
                          <div className="flex items-center gap-1">
                            <span className="text-blue-600 font-medium">Add:</span>
                            <Input
                              type="number"
                              min="0"
                              step="50"
                              value={currentQty}
                              onChange={(e) =>
                                handleQuantityChange(
                                  item.item_id,
                                  parseFloat(e.target.value) || 0
                                )
                              }
                              className="w-24 h-7 text-xs"
                              onClick={(e) => e.stopPropagation()}
                            />
                            <span className="text-blue-600 text-xs">g</span>
                          </div>
                        ) : (
                          <span className="text-blue-600 font-medium">
                            Buy: {formatQuantity(item.recommended_quantity)}
                          </span>
                        )}

                        {item.days_until_depleted !== undefined && item.days_until_depleted > 0 && (
                          <span>
                            {item.days_until_depleted} days supply
                          </span>
                        )}

                        {item.usage_frequency > 0 && (
                          <span>
                            Used {item.usage_frequency}x recently
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Estimated Cost */}
      {data.estimated_total_cost && data.estimated_total_cost > 0 && (
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Estimated Total Cost</span>
              <span className="text-lg font-bold">${data.estimated_total_cost.toFixed(2)}</span>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
