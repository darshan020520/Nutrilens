"use client";

import { useEffect, useState } from "react";
import { DashboardLayout } from "@/components/layouts/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { User, Mail, Target } from "lucide-react";
import { authAPI } from "@/lib/api";
import { toast } from "sonner";

type MeResponse = {
  data?: {
    user?: {
      email?: string;
      goal_type?: string;
    };
  };
  user?: {
    email?: string;
    goal_type?: string;
  };
};

export default function ProfilePage() {
  const [email, setEmail] = useState("user@example.com");
  const [displayName, setDisplayName] = useState("");
  const [goal, setGoal] = useState("Not set");

  useEffect(() => {
    const savedName = localStorage.getItem("profile_display_name");
    if (savedName) setDisplayName(savedName);

    authAPI
      .getMe()
      .then((data: unknown) => {
        const payload = data as MeResponse;
        const userEmail = payload?.data?.user?.email || payload?.user?.email;
        if (userEmail) setEmail(userEmail);

        const goalType = payload?.data?.user?.goal_type || payload?.user?.goal_type;
        if (goalType) setGoal(goalType);
      })
      .catch(() => {
        // Keep local fallback values.
      });
  }, []);

  const handleSave = () => {
    localStorage.setItem("profile_display_name", displayName.trim());
    toast.success("Profile preferences saved");
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Profile</h1>
          <p className="text-muted-foreground mt-1">Account snapshot and personal display preferences</p>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <Mail className="h-4 w-4" /> Email
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="font-medium break-all">{email}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <User className="h-4 w-4" /> Display Name
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="font-medium">{displayName || "Not set"}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <Target className="h-4 w-4" /> Goal
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Badge variant="outline">{goal}</Badge>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Personalization</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 max-w-lg">
            <div className="space-y-2">
              <Label htmlFor="display-name">Display Name</Label>
              <Input
                id="display-name"
                placeholder="How should we address you?"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
              />
            </div>

            <Button onClick={handleSave}>Save Preferences</Button>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
