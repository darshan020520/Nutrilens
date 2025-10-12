// frontend/src/app/dashboard/inventory/page.tsx
"use client";

import { DashboardLayout } from "@/components/layouts/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Package } from "lucide-react";

export default function InventoryPage() {
  return (
    <DashboardLayout>
      <div className="container mx-auto py-6 px-4 md:px-6 space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Inventory</h1>
          <p className="text-muted-foreground mt-1">
            Manage your pantry and track ingredients
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Package className="h-5 w-5" />
              Coming Soon
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">
              Inventory dashboard is under development. This will allow you to:
            </p>
            <ul className="list-disc list-inside mt-4 space-y-2 text-sm text-muted-foreground">
              <li>Track items in your pantry</li>
              <li>Get expiry alerts</li>
              <li>Generate shopping lists</li>
              <li>Scan receipts with OCR</li>
            </ul>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}