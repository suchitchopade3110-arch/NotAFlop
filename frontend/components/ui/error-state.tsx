import { cn } from "@/lib/utils/cn";
import { Button } from "@/components/ui/button";

interface ErrorStateProps {
  title: string;
  description: string;
  onRetry?: () => void;
  retryLabel?: string;
  className?: string;
  compact?: boolean;
}

export function ErrorState({
  title,
  description,
  onRetry,
  retryLabel = "Try again",
  className,
  compact,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-start gap-3 rounded-2xl border border-nogo/30 bg-nogo-wash px-6 py-5",
        compact && "py-4",
        className,
      )}
    >
      <div>
        <p className="text-heading-sm text-ink">{title}</p>
        <p className="mt-1 text-body text-ink-muted">{description}</p>
      </div>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          {retryLabel}
        </Button>
      )}
    </div>
  );
}
