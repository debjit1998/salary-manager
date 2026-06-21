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
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  );
}
