export function EmptyState({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded border border-dashed border-rule bg-panel p-6">
      <h2 className="text-lg font-semibold">{title}</h2>
      <div className="mt-2 max-w-prose text-sm leading-relaxed text-ink-soft">{children}</div>
    </section>
  );
}
