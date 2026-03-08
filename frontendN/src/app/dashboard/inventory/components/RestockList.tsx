"use client";

import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { motion as motionTokens } from "@/design/motion";
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

type PriorityBadge = {
  variant: "destructive" | "secondary" | "outline";
  className?: string;
};

export default function RestockList() {
  const { data, isLoading, error } = useRestockList();
  const bulkAdd = useBulkAddFromRestock();
  const [selectedItems, setSelectedItems] = useState<Set<number>>(new Set());
  const [quantities, setQuantities] = useState<Record<number, number>>({});
  const [lastAddedCount, setLastAddedCount] = useState(0);
  const [showAddedFeedback, setShowAddedFeedback] = useState(false);

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
      return;
    }

    setSelectedItems(new Set());
    setQuantities({});
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
    setLastAddedCount(itemsToAdd.length);
    setShowAddedFeedback(true);
    window.setTimeout(() => setShowAddedFeedback(false), 2200);
    setSelectedItems(new Set());
    setQuantities({});
  };

  const handleCopyList = () => {
    if (allItems.length === 0) return;

    const listText = allItems
      .map((item) => `${item.item_name} - ${item.recommended_quantity}g (${item.priority})`)
      .join("\n");

    navigator.clipboard.writeText(listText);
    toast.success("Shopping list copied to clipboard");
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
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `shopping-list-${new Date().toISOString().split("T")[0]}.txt`;
    anchor.click();
    URL.revokeObjectURL(url);

    toast.success("Shopping list exported");
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
        <AlertDescription>Failed to load shopping list. Please try again.</AlertDescription>
      </Alert>
    );
  }

  if (!data) return null;

  const getPriorityBadge = (priority: string): PriorityBadge => {
    if (priority === "urgent") return { variant: "destructive" };
    if (priority === "soon") {
      return {
        variant: "secondary",
        className: "bg-yellow-100 text-yellow-800 hover:bg-yellow-100",
      };
    }
    return {
      variant: "secondary",
      className: "bg-slate-100 text-slate-700 hover:bg-slate-100",
    };
  };

  const getPriorityIcon = (priority: string) => {
    if (priority === "urgent") return <AlertTriangle className="h-3.5 w-3.5" />;
    if (priority === "soon") return <TrendingDown className="h-3.5 w-3.5" />;
    return <Package className="h-3.5 w-3.5" />;
  };

  const isAllSelected = allItems.length > 0 && selectedItems.size === allItems.length;

  const formatQuantity = (grams: number) => {
    if (grams >= 1000) return `${(grams / 1000).toFixed(1)} kg`;
    return `${Math.round(grams)} g`;
  };

  return (
    <div className="space-y-6 pb-24">
      <div className="rounded-2xl border border-amber-200 bg-[linear-gradient(145deg,rgba(251,191,36,0.10),rgba(249,115,22,0.08))] px-5 py-4">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-600">Restock Intelligence</p>
        <h2 className="text-xl font-semibold text-slate-900">Prioritized shopping recommendations with one-click inventory add</h2>
      </div>

      <AnimatePresence>
        {showAddedFeedback && (
          <motion.div
            className="rounded-xl border border-green-200 bg-green-50 px-4 py-3"
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: motionTokens.base, ease: motionTokens.easing }}
          >
            <p className="text-sm font-medium text-green-800 flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4" />
              Added {lastAddedCount} selected item{lastAddedCount > 1 ? "s" : ""} to inventory.
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Shopping List</h2>
          <p className="text-sm text-muted-foreground">Smart recommendations based on inventory and usage risk</p>
        </div>

        {allItems.length > 0 && (
          <div className="flex gap-2">
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

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="p-4 text-center">
            <div className="mb-1 flex items-center justify-center gap-2">
              <ShoppingCart className="h-4 w-4 text-muted-foreground" />
              <span className="text-2xl font-bold">{data.total_items}</span>
            </div>
            <p className="text-xs text-muted-foreground">Items to Buy</p>
          </CardContent>
        </Card>

        <Card className="border-red-200 bg-red-50/50">
          <CardContent className="p-4 text-center">
            <div className="mb-1 flex items-center justify-center gap-2">
              <AlertTriangle className="h-4 w-4 text-red-600" />
              <span className="text-2xl font-bold text-red-700">{data.urgent_items.length}</span>
            </div>
            <p className="text-xs text-red-700">Urgent</p>
          </CardContent>
        </Card>

        <Card className="border-yellow-200 bg-yellow-50/50">
          <CardContent className="p-4 text-center">
            <div className="mb-1 flex items-center justify-center gap-2">
              <TrendingDown className="h-4 w-4 text-yellow-600" />
              <span className="text-2xl font-bold text-yellow-700">{data.soon_items.length}</span>
            </div>
            <p className="text-xs text-yellow-700">Soon</p>
          </CardContent>
        </Card>

        <Card className="border-green-200 bg-green-50/50">
          <CardContent className="p-4 text-center">
            <div className="mb-1 flex items-center justify-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-green-600" />
              <span className="text-2xl font-bold text-green-700">{selectedItems.size}</span>
            </div>
            <p className="text-xs text-green-700">Selected</p>
          </CardContent>
        </Card>
      </div>

      {data.shopping_strategy && data.shopping_strategy.length > 0 && (
        <Card className="border-blue-200 bg-blue-50/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm font-medium">
              <Lightbulb className="h-4 w-4 text-blue-600" />
              Shopping Strategy
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {data.shopping_strategy.map((recommendation, index) => (
              <div key={index} className="flex items-start gap-2 text-sm">
                <div className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-blue-600" />
                <p className="text-gray-700">{recommendation}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {allItems.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center">
            <ShoppingCart className="mx-auto mb-3 h-12 w-12 text-muted-foreground" />
            <p className="mb-1 text-lg font-medium">Your inventory looks good</p>
            <p className="text-sm text-muted-foreground">No items need restocking at the moment</p>
          </CardContent>
        </Card>
      )}

      {allItems.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Checkbox checked={isAllSelected} onCheckedChange={(checked) => handleSelectAll(!!checked)} />
                <CardTitle className="text-base">Items to Buy ({allItems.length})</CardTitle>
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
                const priorityBadge = getPriorityBadge(item.priority);

                return (
                  <motion.div
                    key={item.item_id}
                    layout
                    className={`flex items-start gap-3 rounded-lg border p-3 transition-all ${
                      isSelected ? "border-blue-200 bg-blue-50" : "hover:bg-muted/30"
                    }`}
                    transition={{ duration: motionTokens.base, ease: motionTokens.easing }}
                  >
                    <Checkbox checked={isSelected} onCheckedChange={() => handleToggleSelect(item)} className="mt-1" />

                    <div className="min-w-0 flex-1">
                      <div className="mb-2 flex items-start justify-between gap-2">
                        <h4 className="font-semibold">{item.item_name}</h4>
                        <Badge variant={priorityBadge.variant} className={`text-xs flex-shrink-0 ${priorityBadge.className ?? ""}`}>
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

                        <span>Current: {formatQuantity(item.current_quantity)}</span>

                        {isSelected ? (
                          <div className="flex items-center gap-1">
                            <span className="font-medium text-blue-600">Add:</span>
                            <Input
                              type="number"
                              min="0"
                              step="50"
                              value={currentQty}
                              onChange={(event) => handleQuantityChange(item.item_id, parseFloat(event.target.value) || 0)}
                              className="h-7 w-24 text-xs"
                            />
                            <span className="text-xs text-blue-600">g</span>
                          </div>
                        ) : (
                          <span className="font-medium text-blue-600">Buy: {formatQuantity(item.recommended_quantity)}</span>
                        )}

                        {item.days_until_depleted !== undefined && item.days_until_depleted > 0 && (
                          <span>{item.days_until_depleted} days supply</span>
                        )}

                        {item.usage_frequency > 0 && <span>Used {item.usage_frequency}x recently</span>}
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

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

      <AnimatePresence>
        {selectedItems.size > 0 && (
          <motion.div
            className="fixed bottom-5 left-1/2 z-40 w-[min(92vw,680px)] -translate-x-1/2 rounded-2xl border border-cyan-200 bg-white/95 p-3 shadow-2xl backdrop-blur"
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 24 }}
            transition={{ duration: motionTokens.base, ease: motionTokens.easing }}
          >
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm">
                <span className="font-semibold">{selectedItems.size}</span> item{selectedItems.size > 1 ? "s" : ""} selected for inventory add
              </p>
              <Button
                onClick={handleBulkAdd}
                disabled={bulkAdd.isPending}
                className="sm:min-w-52 bg-gradient-to-r from-teal-600 to-cyan-600 text-white hover:from-teal-500 hover:to-cyan-500"
              >
                {bulkAdd.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Adding selected...
                  </>
                ) : (
                  <>
                    <Plus className="mr-2 h-4 w-4" />
                    Add selected to inventory
                  </>
                )}
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
