// frontend/src/app/dashboard/nutrition/page.tsx
"use client";

import { useRouter } from "next/navigation";
import { DashboardLayout } from "@/components/layouts/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { BarChart3, Bot, Sparkles, MessageCircle } from "lucide-react";

export default function NutritionPage() {
  const router = useRouter();

  return (
    <DashboardLayout>
      <div className="container mx-auto py-6 px-4 md:px-6 space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Nutrition Analytics</h1>
          <p className="text-muted-foreground mt-1">
            Track your progress and analyze your nutrition
          </p>
        </div>

        {/* AI Nutrition Assistant Card */}
        <Card className="border-primary/20 bg-gradient-to-br from-primary/5 via-background to-background">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bot className="h-6 w-6 text-primary" />
              AI Nutrition Assistant
              <Badge variant="outline" className="ml-auto">
                <Sparkles className="h-3 w-3 mr-1" />
                LLM-Powered
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-muted-foreground">
              Chat with your personal AI nutrition assistant that has complete access to your nutrition data,
              goals, and preferences. Get instant answers without having to explain your context every time!
            </p>

            <div className="bg-muted/50 rounded-lg p-4 space-y-2">
              <p className="text-sm font-medium">Try asking questions like:</p>
              <ul className="text-sm text-muted-foreground space-y-1">
                <li className="flex items-center gap-2">
                  <MessageCircle className="h-3 w-3" />
                  "How is my protein intake today?"
                </li>
                <li className="flex items-center gap-2">
                  <MessageCircle className="h-3 w-3" />
                  "What if I eat 2 samosas?"
                </li>
                <li className="flex items-center gap-2">
                  <MessageCircle className="h-3 w-3" />
                  "Suggest a high-protein lunch"
                </li>
                <li className="flex items-center gap-2">
                  <MessageCircle className="h-3 w-3" />
                  "What can I make with my current inventory?"
                </li>
              </ul>
            </div>

            <Button
              onClick={() => router.push('/dashboard/nutrition/chat')}
              size="lg"
              className="w-full"
            >
              <Bot className="h-4 w-4 mr-2" />
              Start Chatting with AI
            </Button>
          </CardContent>
        </Card>

        {/* Coming Soon Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5" />
              Analytics Dashboard
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">
              Advanced analytics features are under development. Coming soon:
            </p>
            <ul className="list-disc list-inside mt-4 space-y-2 text-sm text-muted-foreground">
              <li>Macro trends over time</li>
              <li>Goal progress charts</li>
              <li>Adherence heatmaps</li>
              <li>AI-powered insights</li>
              <li>Weight tracking</li>
            </ul>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}