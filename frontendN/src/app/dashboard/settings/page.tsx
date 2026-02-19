"use client";

import { useEffect, useState } from "react";
import { DashboardLayout } from "@/components/layouts/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Settings } from "lucide-react";
import { toast } from "sonner";

export default function SettingsPage() {
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [compactMode, setCompactMode] = useState(false);
  const [showHints, setShowHints] = useState(true);

  useEffect(() => {
    const saved = localStorage.getItem("frontendn_settings");
    if (saved) {
      const parsed = JSON.parse(saved);
      setAutoRefresh(!!parsed.autoRefresh);
      setCompactMode(!!parsed.compactMode);
      setShowHints(!!parsed.showHints);
    }
  }, []);

  const saveSettings = () => {
    localStorage.setItem(
      "frontendn_settings",
      JSON.stringify({ autoRefresh, compactMode, showHints })
    );
    toast.success("Settings saved locally");
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
          <p className="text-muted-foreground mt-1">App behavior preferences for your workspace</p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Settings className="h-5 w-5" />
              Experience Controls
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6 max-w-xl">
            <div className="flex items-center justify-between">
              <div>
                <Label htmlFor="auto-refresh">Auto Refresh Data</Label>
                <p className="text-sm text-muted-foreground">Refresh dashboard and module data periodically</p>
              </div>
              <Checkbox id="auto-refresh" checked={autoRefresh} onCheckedChange={(v) => setAutoRefresh(!!v)} />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <Label htmlFor="compact-mode">Compact Layout Mode</Label>
                <p className="text-sm text-muted-foreground">Reduce spacing density for data-heavy views</p>
              </div>
              <Checkbox id="compact-mode" checked={compactMode} onCheckedChange={(v) => setCompactMode(!!v)} />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <Label htmlFor="show-hints">Show Action Hints</Label>
                <p className="text-sm text-muted-foreground">Display helper hints for workflows and recommendations</p>
              </div>
              <Checkbox id="show-hints" checked={showHints} onCheckedChange={(v) => setShowHints(!!v)} />
            </div>

            <Button onClick={saveSettings}>Save Settings</Button>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
