import { Card, CardContent } from "@/components/ui/card";
import { UtensilsCrossed, Calendar, Package, Bot } from "lucide-react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";

export function QuickActions() {
  const router = useRouter();

  const actions = [
    {
      icon: UtensilsCrossed,
      label: "Log Meals",
      description: "Track planned or external meals",
      onClick: () => router.push("/dashboard/meals?tab=today"),
      active: true,
    },
    {
      icon: Calendar,
      label: "Weekly Plan",
      description: "Review and swap upcoming meals",
      onClick: () => router.push("/dashboard/meals?tab=week"),
      active: false,
    },
    {
      icon: Package,
      label: "Pantry Ops",
      description: "Manage inventory and restock",
      onClick: () => router.push("/dashboard/inventory"),
      active: false,
    },
    {
      icon: Bot,
      label: "Ask AI Coach",
      description: "Context-aware nutrition guidance",
      onClick: () => router.push("/dashboard/nutrition/chat"),
      active: false,
    },
  ];

  return (
    <Card>
      <CardContent className="p-6">
        <div className="flex items-center justify-between mb-5">
          <h3
            className="text-[17px] font-medium text-slate-900"
            style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
          >
            Next Actions
          </h3>
          <p className="text-[11.5px] text-slate-400 font-medium">One-click workflows</p>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {actions.map((action) => {
            const Icon = action.icon;
            return (
              <button
                key={action.label}
                type="button"
                onClick={action.onClick}
                className={cn(
                  "group/action flex flex-col items-start gap-3 rounded-[14px] p-4 text-left transition-all duration-250",
                  action.active
                    ? "bg-gradient-to-br from-[#1B7D5A] to-[#22956B] shadow-[0_4px_20px_rgba(27,125,90,0.25)] hover:shadow-[0_6px_24px_rgba(27,125,90,0.3)]"
                    : "border border-slate-150 bg-white hover:-translate-y-0.5 hover:border-emerald-200 hover:shadow-[0_6px_24px_rgba(0,0,0,0.06)]"
                )}
              >
                {/* Icon box */}
                <div
                  className={cn(
                    "flex h-9 w-9 items-center justify-center rounded-[10px] transition-colors",
                    action.active
                      ? "bg-white/20 text-white"
                      : "bg-slate-50 text-slate-500 group-hover/action:bg-emerald-50 group-hover/action:text-emerald-600"
                  )}
                >
                  <Icon className="h-[17px] w-[17px]" />
                </div>

                {/* Text */}
                <div>
                  <div
                    className={cn(
                      "text-[13.5px] font-semibold",
                      action.active ? "text-white" : "text-slate-900"
                    )}
                  >
                    {action.label}
                  </div>
                  <div
                    className={cn(
                      "mt-0.5 text-[11.5px] leading-snug",
                      action.active ? "text-white/65" : "text-slate-400"
                    )}
                  >
                    {action.description}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}