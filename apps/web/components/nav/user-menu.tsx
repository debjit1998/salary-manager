"use client";

import { LogOut } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useLogout, useMe } from "@/lib/hooks/use-auth";

export function UserMenu() {
  const { data: user } = useMe();
  const { mutate: logout, isPending } = useLogout();

  if (!user) return null;
  const initial = user.email[0]?.toUpperCase() ?? "?";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="flex w-full items-center gap-3 rounded-md p-2 text-left hover:bg-slate-200/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <Avatar className="size-8">
            <AvatarFallback>{initial}</AvatarFallback>
          </Avatar>
          <div className="flex-1 truncate text-sm">
            <div className="truncate font-medium">{user.email}</div>
            <div className="truncate text-xs text-muted-foreground">
              HR Manager
            </div>
          </div>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>{user.email}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onSelect={() => logout()}
          disabled={isPending}
          className="text-destructive focus:text-destructive"
        >
          <LogOut className="size-4" /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
