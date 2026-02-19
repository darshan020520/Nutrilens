import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { UtensilsCrossed, Calendar, Package, Bot } from "lucide-react";
import { useRouter } from "next/navigation";

export function QuickActions() {
  const router = useRouter();

  const actions = [
    {
      icon: UtensilsCrossed,
      label: "Log Meals",
      description: "Track planned or external meals",
      onClick: () => router.push("/dashboard/meals?tab=today"),
      variant: "default" as const,
    },
    {
      icon: Calendar,
      label: "Weekly Plan",
      description: "Review and swap upcoming meals",
      onClick: () => router.push("/dashboard/meals?tab=week"),
      variant: "outline" as const,
    },
    {
      icon: Package,
      label: "Pantry Ops",
      description: "Manage inventory and restock",
      onClick: () => router.push("/dashboard/inventory"),
      variant: "outline" as const,
    },
    {
      icon: Bot,
      label: "Ask AI Coach",
      description: "Context-aware nutrition guidance",
      onClick: () => router.push("/dashboard/nutrition/chat"),
      variant: "outline" as const,
    },
  ];

  return (
    <Card className="mb-8">
      <CardContent className="pt-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Next Actions</h3>
          <p className="text-xs text-muted-foreground">One-click workflows</p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {actions.map((action) => {
            const Icon = action.icon;
            return (
              <Button
                key={action.label}
                variant={action.variant}
                className="h-auto flex-col items-start p-4 gap-2"
                onClick={action.onClick}
              >
                <Icon className="h-5 w-5 mb-1" />
                <div className="text-left">
                  <div className="font-medium">{action.label}</div>
                  <div className="text-xs text-muted-foreground font-normal">
                    {action.description}
                  </div>
                </div>
              </Button>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
