"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, Utensils, Package, BarChart3, User } from "lucide-react";
import { cn } from "@/lib/utils";

const mobileItems = [
  { href: "/dashboard", label: "Home", icon: Home },
  { href: "/dashboard/meals", label: "Meals", icon: Utensils },
  { href: "/dashboard/inventory", label: "Inventory", icon: Package },
  { href: "/dashboard/nutrition", label: "Nutrition", icon: BarChart3 },
  { href: "/dashboard/profile", label: "Profile", icon: User },
];

export function MobileNav() {
  const pathname = usePathname();

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 border-t bg-background/95 backdrop-blur z-30">
      <div className="grid grid-cols-5 h-16">
        {mobileItems.map((item) => {
          const Icon = item.icon;
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex flex-col items-center justify-center text-[11px] gap-1",
                active ? "text-primary" : "text-muted-foreground"
              )}
            >
              <Icon className="h-4 w-4" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
