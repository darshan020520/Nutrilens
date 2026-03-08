import { Card } from "@/components/ui/card";
import { Package, AlertTriangle } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";

interface InventoryCardProps {
  data?: {
    expiring_soon_count: number;
    low_stock_count: number;
    out_of_stock_count: number;
    total_items: number;
  };
  isLoading: boolean;
}

export function InventoryCard({ data, isLoading }: InventoryCardProps) {
  if (isLoading) {
    return (
      <Card className="group overflow-hidden transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(0,0,0,0.06)]">
        <div className="p-5">
          <div className="flex items-center justify-between mb-4">
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-8 w-8 rounded-lg" />
          </div>
          <Skeleton className="h-7 w-24 mb-2" />
          <Skeleton className="h-4 w-full" />
        </div>
      </Card>
    );
  }

  if (!data) return null;

  const alertCount = data.expiring_soon_count + data.low_stock_count;
  const hasAlerts = alertCount > 0;

  return (
    <Card className="group overflow-hidden transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(0,0,0,0.06)]">
      <div className="p-5">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <span className="text-[13px] font-semibold text-slate-900">Inventory</span>
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-50 text-slate-400 transition-colors group-hover:bg-emerald-50 group-hover:text-emerald-500">
            <Package className="h-[15px] w-[15px]" />
          </div>
        </div>

        {/* Big number */}
        <div
          className="text-[28px] font-semibold leading-none tracking-tight text-slate-900"
          style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}
        >
          {data.total_items}
          <span className="ml-1.5 text-[14px] font-normal text-slate-300">items</span>
        </div>

        {/* Alerts */}
        {hasAlerts ? (
          <div className="mt-3.5 space-y-2">
            {data.expiring_soon_count > 0 && (
              <div className="flex items-center gap-2">
                <div className="flex h-[18px] w-[18px] items-center justify-center rounded-full bg-amber-50">
                  <AlertTriangle className="h-[10px] w-[10px] text-amber-500" />
                </div>
                <span className="text-[12px] text-slate-500">
                  {data.expiring_soon_count} expiring soon
                </span>
              </div>
            )}
            {data.low_stock_count > 0 && (
              <div className="flex items-center gap-2">
                <div className="flex h-[18px] w-[18px] items-center justify-center rounded-full bg-amber-50">
                  <AlertTriangle className="h-[10px] w-[10px] text-amber-500" />
                </div>
                <span className="text-[12px] text-slate-500">
                  {data.low_stock_count} low stock
                </span>
              </div>
            )}
          </div>
        ) : (
          <p className="mt-2 text-[12px] text-slate-400">All items well stocked</p>
        )}

        {/* Alert badge — warm/soft instead of destructive red */}
        {hasAlerts && (
          <div className="mt-3.5 inline-flex items-center gap-1.5 rounded-lg bg-orange-50 px-2.5 py-1.5 text-[11.5px] font-semibold text-orange-600 ring-1 ring-orange-100">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-orange-400" />
            {alertCount} Alert{alertCount > 1 ? "s" : ""}
          </div>
        )}
      </div>
    </Card>
  );
}