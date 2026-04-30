interface StaleBadgeProps {
  stale: boolean;
  label?: string;
}

export function StaleBadge({ stale, label = "Params changed" }: StaleBadgeProps) {
  if (!stale) return null;
  return (
    <span
      title="The current parameters differ from the run that produced these results. Re-run to refresh."
      className="inline-flex items-center gap-1 rounded-full border border-yellow-400/40 bg-yellow-400/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-yellow-200"
    >
      <span className="h-1.5 w-1.5 rounded-full bg-yellow-300" />
      {label}
    </span>
  );
}
