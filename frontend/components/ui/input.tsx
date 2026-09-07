import { forwardRef, useId } from "react";
import { cn } from "@/lib/utils/cn";

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  error?: string | null;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, label, hint, error, id, ...props },
  ref,
) {
  const generatedId = useId();
  const fieldId = id ?? generatedId;
  const hintId = `${fieldId}-hint`;
  const errorId = `${fieldId}-error`;

  return (
    <div className="w-full">
      {label && (
        <label htmlFor={fieldId} className="text-label mb-2 block text-ink-muted">
          {label}
        </label>
      )}
      <input
        ref={ref}
        id={fieldId}
        aria-describedby={cn(hint && hintId, error && errorId) || undefined}
        aria-invalid={!!error || undefined}
        className={cn(
          "h-12 w-full rounded-lg border bg-charcoal px-4 text-body text-ink placeholder:text-ink-faint",
          "transition-colors duration-150 outline-none",
          error ? "border-nogo/60" : "border-border focus:border-gold/60",
          className,
        )}
        {...props}
      />
      {error && (
        <p id={errorId} className="mt-2 text-body text-nogo">
          {error}
        </p>
      )}
      {!error && hint && (
        <p id={hintId} className="mt-2 text-body text-ink-faint">
          {hint}
        </p>
      )}
    </div>
  );
});
