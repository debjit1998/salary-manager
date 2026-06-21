"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { Sidebar } from "@/components/nav/sidebar";
import { Skeleton } from "@/components/ui/skeleton";
import { useMe } from "@/lib/hooks/use-auth";

export default function AuthedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const { data: user, isLoading, isError } = useMe();

  useEffect(() => {
    if (isError) router.replace("/login");
  }, [isError, router]);

  if (isLoading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Skeleton className="h-8 w-32" />
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      {/* `overflow-auto` lets short pages scroll the main column; pages that
       *  want internal scroll (e.g. /employees) wrap their content in
       *  `flex h-full flex-col` and put `overflow-hidden` on the inner
       *  container so AgGrid manages its own scrollbar. */}
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  );
}
