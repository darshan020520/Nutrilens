import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { UtensilsCrossed, Calendar, Package, TrendingUp } from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

export function QuickActions() {
  const router = useRouter();

  const actions = [
    {
      icon: UtensilsCrossed,
      label: "Log Meal",
      description: "Record what you ate",
      onClick: () => {
        toast.info("Meal logging coming soon!");
        // router.push("/dashboard/meals");
      },
      variant: "default" as const,
    },
    {
      icon: Calendar,
      label: "Generate Plan",
      description: "Create meal plan",
      onClick: () => {
        toast.info("Meal planning coming soon!");
        // router.push("/dashboard/meal-plans");
      },
      variant: "outline" as const,
    },
    {
      icon: Package,
      label: "Add Inventory",
      description: "Update your pantry",
      onClick: () => {
        toast.info("Inventory management coming soon!");
        // router.push("/dashboard/inventory");
      },
      variant: "outline" as const,
    },
    {
      icon: TrendingUp,
      label: "View Progress",
      description: "Check your stats",
      onClick: () => {
        toast.info("Progress tracking coming soon!");
        // router.push("/dashboard/progress");
      },
      variant: "outline" as const,
    },
  ];

  return (
    <Card className="mb-8">
      <CardContent className="pt-6">
        <h3 className="text-lg font-semibold mb-4">Quick Actions</h3>
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