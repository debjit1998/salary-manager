export default async function EmployeeDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="mx-auto max-w-7xl space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Employee detail
        </h1>
        <p className="text-sm text-muted-foreground">id: {id}</p>
      </div>
      <div className="rounded-lg border bg-card p-6 text-sm text-muted-foreground">
        Profile, salary timeline, history, equity, edit forms — Task #10.
      </div>
    </div>
  );
}
