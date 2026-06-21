"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Users } from "lucide-react";

import { cn } from "@/lib/utils";

import { UserMenu } from "./user-menu";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/employees", label: "Employees", icon: Users },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col border-r bg-slate-50">
      <div className="flex h-14 items-center border-b px-5">
        <Link href="/dashboard" className="font-semibold tracking-tight">
          Salary Manager
        </Link>
      </div>

      <nav className="flex-1 space-y-1 p-3">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-primary/10 text-primary"
                  : "text-slate-700 hover:bg-slate-200/60 hover:text-slate-900",
              )}
            >
              <Icon className="size-4" />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t p-3">
        <UserMenu />
      </div>
    </aside>
  );
}
