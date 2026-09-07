import { cn } from "@/lib/utils/cn";

interface EmptyStateProps {
  title: string;
  description: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
}

export function EmptyState({ title, description, action, icon, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center gap-4 rounded-2xl border border-dashed border-border px-6 py-16 text-center",
        className,
      )}
    >
      {icon && <div className="text-gold/70">{icon}</div>}
      <div className="max-w-sm">
        <p className="text-heading-sm text-ink">{title}</p>
        <p className="mt-2 text-body text-ink-muted">{description}</p>
      </div>
      {action}
    </div>
  );
}
