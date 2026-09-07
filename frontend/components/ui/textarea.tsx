import { forwardRef, useId } from "react";
import { cn } from "@/lib/utils/cn";

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  hint?: string;
  error?: string | null;
  maxLength?: number;
  showCount?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { className, label, hint, error, maxLength, showCount, id, value, ...props },
  ref,
) {
  const generatedId = useId();
  const fieldId = id ?? generatedId;
  const hintId = `${fieldId}-hint`;
  const errorId = `${fieldId}-error`;
  const length = typeof value === "string" ? value.length : 0;
  const nearLimit = maxLength ? length >= maxLength * 0.9 : false;
  const overLimit = maxLength ? length > maxLength : false;

  return (
    <div className="w-full">
      {label && (
        <label htmlFor={fieldId} className="text-label mb-2 block text-ink-muted">
          {label}
        </label>
      )}
      <textarea
        ref={ref}
        id={fieldId}
        value={value}
        maxLength={maxLength ? maxLength + 200 : undefined}
        aria-describedby={cn(hint && hintId, error && errorId) || undefined}
        aria-invalid={!!error || overLimit || undefined}
        className={cn(
          "w-full resize-none rounded-xl border bg-charcoal px-4 py-4 text-body-l text-ink placeholder:text-ink-faint",
          "transition-colors duration-150 outline-none",
          error || overLimit ? "border-nogo/60" : "border-border focus:border-gold/60",
          className,
        )}
        {...props}
      />
      <div className="mt-2 flex items-start justify-between gap-4">
        <div>
          {error && (
            <p id={errorId} className="text-body text-nogo">
              {error}
            </p>
          )}
          {!error && hint && (
            <p id={hintId} className="text-body text-ink-faint">
              {hint}
            </p>
          )}
        </div>
        {showCount && maxLength && (
          <p
            className={cn(
              "text-mono shrink-0 whitespace-nowrap",
              overLimit ? "text-nogo" : nearLimit ? "text-pivot" : "text-ink-faint",
            )}
            aria-live="polite"
          >
            {length.toLocaleString()} / {maxLength.toLocaleString()}
          </p>
        )}
      </div>
    </div>
  );
});
