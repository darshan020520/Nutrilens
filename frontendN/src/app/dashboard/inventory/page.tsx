"use client";

import { useState } from "react";
import { Plus, Camera } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DashboardLayout } from "@/components/layouts/DashboardLayout";

import InventoryStatus from "./components/InventoryStatus";
import InventoryList from "./components/InventoryList";
import AddItemsDialog from "./components/AddItemsDialog";
import ReceiptUpload from "./components/ReceiptUpload";
import MakeableRecipes from "./components/MakeableRecipes";
import ExpiringItems from "./components/ExpiringItems";
import RestockList from "./components/RestockList";

import { usePendingItems } from "./hooks/useReceipt";

export default function InventoryPage() {
  const [addItemsOpen, setAddItemsOpen] = useState(false);
  const [receiptUploadOpen, setReceiptUploadOpen] = useState(false);

  const { data: pendingData } = usePendingItems();
  const hasPendingItems = (pendingData?.count ?? 0) > 0;

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Inventory Intelligence</h1>
            <p className="text-muted-foreground">
              Pantry health, expiry risk, and AI-backed action recommendations
            </p>
          </div>

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

        <InventoryStatus />

        <Tabs defaultValue="all" className="space-y-4">
          <TabsList>
            <TabsTrigger value="all">All Items</TabsTrigger>
            <TabsTrigger value="expiring">Expiring Soon</TabsTrigger>
            <TabsTrigger value="recipes">Cookable Recipes</TabsTrigger>
            <TabsTrigger value="shopping">Shopping List</TabsTrigger>
          </TabsList>

          <TabsContent value="all" className="space-y-4">
            <InventoryList />
          </TabsContent>

          <TabsContent value="expiring" className="space-y-4">
            <ExpiringItems />
          </TabsContent>

          <TabsContent value="recipes" className="space-y-4">
            <MakeableRecipes />
          </TabsContent>

          <TabsContent value="shopping" className="space-y-4">
            <RestockList />
          </TabsContent>
        </Tabs>

        <AddItemsDialog open={addItemsOpen} onOpenChange={setAddItemsOpen} />
        <ReceiptUpload open={receiptUploadOpen} onOpenChange={setReceiptUploadOpen} />

        {hasPendingItems && (
          <p className="text-xs text-muted-foreground">
            You have pending receipt items awaiting confirmation.
          </p>
        )}
      </div>
    </DashboardLayout>
  );
}
