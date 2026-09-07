import { Card } from "@/components/ui/card";
import type { ConflictEntry } from "@/types/api";

/** B3: conflicts[] rendered as its own distinct element — "disagreement
 * between sources is signal, not noise to be smoothed over." Never
 * merged into a dimension card or averaged into the score panel. */
export function ConflictsPanel({ conflicts }: { conflicts: ConflictEntry[] }) {
  if (!conflicts || conflicts.length === 0) return null;

  return (
    <Card elevation="flat" className="border-pivot/30">
      <p className="text-label text-pivot">Sources disagree</p>
      <ul className="mt-3 space-y-3">
        {conflicts.map((conflict, i) => (
          <li key={i} className="text-body text-ink-muted">
            <span className="text-ink">{conflict.dimension ?? "Signal"}:</span>{" "}
            {conflict.description ?? "Two or more sources pointed in different directions."}
            {conflict.sources && conflict.sources.length > 0 && (
              <span className="ml-1.5 text-mono text-ink-faint">({conflict.sources.join(" vs ")})</span>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}
