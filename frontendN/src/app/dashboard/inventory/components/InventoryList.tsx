"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Search,
  Grid3x3,
  List,
  AlertTriangle,
  Calendar,
  Weight,
  MoreVertical,
  Trash2,
  Filter,
} from "lucide-react";
import { useInventoryItems, useDeleteItem } from "../hooks/useInventory";
import { FilterOptions } from "../types";
import { Skeleton } from "@/components/ui/skeleton";

export default function InventoryList() {
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [searchQuery, setSearchQuery] = useState("");
  const [filters, setFilters] = useState<FilterOptions>({
    category: undefined,
    lowStockOnly: false,
    expiringSoon: false,
  });

  const { data, isLoading, error } = useInventoryItems(filters);
  const deleteItem = useDeleteItem();

  // Filter items based on search query (client-side)
  const filteredItems = data?.items.filter((item) =>
    item.item_name.toLowerCase().includes(searchQuery.toLowerCase())
  ) || [];

  const handleDelete = (inventoryId: number, itemName: string) => {
    if (confirm(`Remove "${itemName}" from inventory?`)) {
      deleteItem.mutate(inventoryId);
    }
  };

  const handleFilterChange = (key: keyof FilterOptions, value: any) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const getExpiryStatus = (daysUntilExpiry: number | null) => {
    if (!daysUntilExpiry) return null;
    if (daysUntilExpiry < 0) return { label: "Expired", color: "destructive" };
    if (daysUntilExpiry <= 3) return { label: `${daysUntilExpiry}d left`, color: "destructive" };
    if (daysUntilExpiry <= 7) return { label: `${daysUntilExpiry}d left`, color: "warning" };
    return { label: `${daysUntilExpiry}d left`, color: "secondary" };
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <Skeleton className="h-10 flex-1" />
          <Skeleton className="h-10 w-32" />
          <Skeleton className="h-10 w-24" />
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-5 w-32" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-4 w-24 mb-2" />
                <Skeleton className="h-4 w-20" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription>
          Failed to load inventory items. Please try again.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-4">
      {/* Search and Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        {/* Search */}
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search items..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>

        {/* Category Filter */}
        <Select
          value={filters.category || "all"}
          onValueChange={(value) =>
            handleFilterChange("category", value === "all" ? undefined : value)
          }
        >
          <SelectTrigger className="w-full sm:w-40">
            <SelectValue placeholder="Category" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Categories</SelectItem>
            <SelectItem value="Dairy">Dairy</SelectItem>
            <SelectItem value="Produce">Produce</SelectItem>
            <SelectItem value="Protein">Protein</SelectItem>
            <SelectItem value="Grains">Grains</SelectItem>
            <SelectItem value="Beverages">Beverages</SelectItem>
            <SelectItem value="Other">Other</SelectItem>
          </SelectContent>
        </Select>

        {/* Quick Filters */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="icon">
              <Filter className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem
              onClick={() =>
                handleFilterChange("lowStockOnly", !filters.lowStockOnly)
              }
            >
              {filters.lowStockOnly ? "✓ " : ""}Low Stock Only
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() =>
                handleFilterChange("expiringSoon", !filters.expiringSoon)
              }
            >
              {filters.expiringSoon ? "✓ " : ""}Expiring Soon
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        {/* View Toggle */}
        <div className="flex gap-1 border rounded-md p-1">
          <Button
            variant={viewMode === "grid" ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setViewMode("grid")}
          >
            <Grid3x3 className="h-4 w-4" />
          </Button>
          <Button
            variant={viewMode === "list" ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setViewMode("list")}
          >
            <List className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Results count */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {filteredItems.length} item{filteredItems.length !== 1 ? "s" : ""} found
        </p>
        {(filters.category || filters.lowStockOnly || filters.expiringSoon) && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() =>
              setFilters({
                category: undefined,
                lowStockOnly: false,
                expiringSoon: false,
              })
            }
          >
            Clear filters
          </Button>
        )}
      </div>

      {/* Empty State */}
      {filteredItems.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">
              {searchQuery || filters.category || filters.lowStockOnly || filters.expiringSoon
                ? "No items match your filters"
                : "No items in inventory yet"}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Grid View */}
      {viewMode === "grid" && filteredItems.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredItems.map((item) => {
            const expiryStatus = getExpiryStatus(item.days_until_expiry);
            return (
              <Card key={item.id} className="relative">
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between gap-2">
                    <CardTitle className="text-base font-semibold line-clamp-2">
                      {item.item_name}
                    </CardTitle>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 -mt-1 -mr-2"
                        >
                          <MoreVertical className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          className="text-destructive"
                          onClick={() =>
                            handleDelete(item.id, item.item_name)
                          }
                        >
                          <Trash2 className="mr-2 h-4 w-4" />
                          Remove
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </CardHeader>
                <CardContent className="space-y-2">
                  <div className="flex items-center gap-4 text-sm">
                    <div className="flex items-center gap-1">
                      <Weight className="h-3.5 w-3.5 text-muted-foreground" />
                      {item.is_depleted ? (
                        <span className="font-medium text-muted-foreground italic">
                          Out of stock
                        </span>
                      ) : (
                        <span className="font-medium">
                          {item.quantity_grams >= 1000
                            ? `${(item.quantity_grams / 1000).toFixed(1)} kg`
                            : `${item.quantity_grams} g`}
                        </span>
                      )}
                    </div>
                    {item.category && (
                      <Badge variant="outline" className="text-xs">
                        {item.category}
                      </Badge>
                    )}
                    {item.is_depleted && (
                      <Badge variant="secondary" className="text-xs">
                        Depleted
                      </Badge>
                    )}
                  </div>

                  {item.expiry_date && (
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1 text-xs text-muted-foreground">
                        <Calendar className="h-3.5 w-3.5" />
                        <span>
                          {item.days_until_expiry !== null && item.days_until_expiry < 0
                            ? "Expired"
                            : "Expires"}{" "}
                          {new Date(item.expiry_date).toLocaleDateString("en-US", {
                            year: "numeric",
                            month: "short",
                            day: "numeric",
                          })}
                        </span>
                      </div>
                      {expiryStatus && (
                        <Badge
                          variant={
                            expiryStatus.color as "destructive" | "warning" | "secondary"
                          }
                          className="text-xs"
                        >
                          {expiryStatus.label}
                        </Badge>
                      )}
                    </div>
                  )}

                  {item.is_low_stock && (
                    <Badge variant="warning" className="w-fit text-xs">
                      <AlertTriangle className="mr-1 h-3 w-3" />
                      Low Stock
                    </Badge>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* List View */}
      {viewMode === "list" && filteredItems.length > 0 && (
        <Card>
          <CardContent className="p-0">
            <div className="divide-y">
              {filteredItems.map((item) => {
                const expiryStatus = getExpiryStatus(item.days_until_expiry);
                return (
                  <div
                    key={item.id}
                    className="flex items-center gap-4 p-4 hover:bg-muted/50 transition-colors"
                  >
                    {/* Item Name */}
                    <div className="flex-1 min-w-0">
                      <h4 className="font-semibold truncate">{item.item_name}</h4>
                      <div className="flex items-center gap-2 mt-1">
                        {item.category && (
                          <Badge variant="outline" className="text-xs">
                            {item.category}
                          </Badge>
                        )}
                        {item.is_low_stock && (
                          <Badge variant="warning" className="text-xs">
                            <AlertTriangle className="mr-1 h-3 w-3" />
                            Low Stock
                          </Badge>
                        )}
                      </div>
                    </div>

                    {/* Quantity */}
                    <div className="flex items-center gap-2 text-sm">
                      <Weight className="h-4 w-4 text-muted-foreground" />
                      {item.is_depleted ? (
                        <span className="font-medium text-muted-foreground italic">
                          Out of stock
                        </span>
                      ) : (
                        <span className="font-medium">
                          {item.quantity_grams >= 1000
                            ? `${(item.quantity_grams / 1000).toFixed(1)} kg`
                            : `${item.quantity_grams} g`}
                        </span>
                      )}
                      {item.is_depleted && (
                        <Badge variant="secondary" className="text-xs">
                          Depleted
                        </Badge>
                      )}
                    </div>

                    {/* Expiry */}
                    {item.expiry_date && (
                      <div className="flex items-center gap-2 text-sm">
                        <Calendar className="h-4 w-4 text-muted-foreground" />
                        <span className="text-muted-foreground">
                          {new Date(item.expiry_date).toLocaleDateString()}
                        </span>
                        {expiryStatus && (
                          <Badge
                            variant={
                              expiryStatus.color as "destructive" | "warning" | "secondary"
                            }
                            className="text-xs"
                          >
                            {expiryStatus.label}
                          </Badge>
                        )}
                      </div>
                    )}

                    {/* Actions */}
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon">
                          <MoreVertical className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          className="text-destructive"
                          onClick={() =>
                            handleDelete(item.id, item.item_name)
                          }
                        >
                          <Trash2 className="mr-2 h-4 w-4" />
                          Remove
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
