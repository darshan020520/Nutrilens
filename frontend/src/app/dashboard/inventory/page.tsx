// frontend/src/app/dashboard/inventory/page.tsx
"use client";

import { useState } from "react";
import { Plus, Camera } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

// Components (will create these step by step)
import InventoryStatus from "./components/InventoryStatus";
import InventoryList from "./components/InventoryList";
import AddItemsDialog from "./components/AddItemsDialog";
import ReceiptUpload from "./components/ReceiptUpload";
import MakeableRecipes from "./components/MakeableRecipes";
import ExpiringItems from "./components/ExpiringItems";
import RestockList from "./components/RestockList";

// Hooks
import { usePendingItems } from "./hooks/useReceipt";

export default function InventoryPage() {
  const [addItemsOpen, setAddItemsOpen] = useState(false);
  const [receiptUploadOpen, setReceiptUploadOpen] = useState(false);

  // Check if there are pending items from receipts
  const { data: pendingData } = usePendingItems();
  const hasPendingItems = (pendingData?.count ?? 0) > 0;

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Inventory</h1>
          <p className="text-muted-foreground">
            Manage your pantry and track ingredients
          </p>
        </div>

        {/* Quick Actions */}
        <div className="flex gap-2">
          <Button onClick={() => setAddItemsOpen(true)} variant="outline">
            <Plus className="mr-2 h-4 w-4" />
            Add Items
          </Button>
          <Button onClick={() => setReceiptUploadOpen(true)}>
            <Camera className="mr-2 h-4 w-4" />
            Scan Receipt
          </Button>
        </div>
      </div>

      {/* Status Overview */}
      <InventoryStatus />

      {/* Main Content Tabs */}
      <Tabs defaultValue="all" className="space-y-4">
        <TabsList>
          <TabsTrigger value="all">All Items</TabsTrigger>
          <TabsTrigger value="expiring">
            Expiring Soon
          </TabsTrigger>
          <TabsTrigger value="recipes">
            Recipes You Can Make
          </TabsTrigger>
          <TabsTrigger value="shopping">
            Shopping List
          </TabsTrigger>
        </TabsList>

        {/* Tab: All Items */}
        <TabsContent value="all" className="space-y-4">
          <InventoryList />
        </TabsContent>

        {/* Tab: Expiring Items */}
        <TabsContent value="expiring" className="space-y-4">
          <ExpiringItems />
        </TabsContent>

        {/* Tab: Recipes */}
        <TabsContent value="recipes" className="space-y-4">
          <MakeableRecipes />
        </TabsContent>

        {/* Tab: Shopping List */}
        <TabsContent value="shopping" className="space-y-4">
          <RestockList />
        </TabsContent>
      </Tabs>

      {/* Dialogs */}
      <AddItemsDialog open={addItemsOpen} onOpenChange={setAddItemsOpen} />
      <ReceiptUpload open={receiptUploadOpen} onOpenChange={setReceiptUploadOpen} />
    </div>
  );
}