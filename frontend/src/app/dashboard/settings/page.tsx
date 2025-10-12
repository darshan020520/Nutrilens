// frontend/src/app/dashboard/settings/page.tsx
"use client";

import { DashboardLayout } from "@/components/layouts/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Settings } from "lucide-react";

export default function SettingsPage() {
  return (
    <DashboardLayout>
      <div className="container mx-auto py-6 px-4 md:px-6 space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
          <p className="text-muted-foreground mt-1">
            Configure your app preferences
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Settings className="h-5 w-5" />
              Coming Soon
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">
              Settings page is under development. This will allow you to:
            </p>
            <ul className="list-disc list-inside mt-4 space-y-2 text-sm text-muted-foreground">
              <li>Notification preferences</li>
              <li>Privacy settings</li>
              <li>Theme customization</li>
              <li>Language preferences</li>
              <li>Data export/import</li>
            </ul>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}