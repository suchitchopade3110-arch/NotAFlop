import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { dimensionLabel } from "@/lib/utils/dimensions";
import { formatDateTime } from "@/lib/utils/format";
import type { SnapshotDeltas, TimelineEntry } from "@/types/api";

function DeltaValue({ value }: { value: number }) {
  if (value === 0) return <span className="text-mono text-ink-faint">0</span>;
  const sign = value > 0 ? "+" : "";
  return (
    <span className={`text-mono font-semibold ${value > 0 ? "text-go" : "text-nogo"}`}>
      {sign}
      {value}
    </span>
  );
}

function SnapshotEntry({ payload }: { payload: Record<string, unknown> }) {
  const trigger = String(payload.trigger ?? "initial");
  const rawScore = Number(payload.raw_score ?? 0);
  const verdict = String(payload.verdict ?? "");
  const versionCrossing = Boolean(payload.version_crossing);
  const deltas = (payload.deltas ?? {}) as SnapshotDeltas;
  const hasDelta = typeof deltas.raw_score === "number";
  const dimensionDeltas = Object.entries(deltas.dimensions ?? {}).filter(([, v]) => v !== 0);

  return (
    <Card elevation="flat">
      <div className="flex flex-wrap items-center gap-3">
        <Badge tone="neutral">{trigger}</Badge>
        <Badge tone={verdict === "go" ? "go" : verdict === "pivot" ? "pivot" : "nogo"}>
          {rawScore} · {verdict}
        </Badge>
        {versionCrossing && (
          <Badge tone="gold" title="Scoring weights changed between these two snapshots">
            weights changed — not like-for-like
          </Badge>
        )}
      </div>

      <div className="mt-3">
        {hasDelta ? (
          <div className="flex items-baseline gap-2">
            <span className="text-body text-ink-muted">Score moved</span>
            <DeltaValue value={deltas.raw_score!} />
          </div>
        ) : (
          <p className="text-body text-ink-muted">Baseline score set.</p>
        )}

        {dimensionDeltas.length > 0 && (
          <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
            {dimensionDeltas.map(([dim, value]) => (
              <li key={dim} className="flex items-center gap-1.5 text-body text-ink-muted">
                {dimensionLabel(dim)}
                <DeltaValue value={value} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}

function SimpleEntry({ type, payload }: { type: string; payload: Record<string, unknown> }) {
  if (type === "evidence") {
    return (
      <Card elevation="flat">
        <p className="text-body text-ink">
          Evidence submitted: <span className="font-medium">{String(payload.evidence_type ?? "").replace(/_/g, " ")}</span>
        </p>
        {payload.triggered_snapshot_id ? (
          <p className="mt-1 text-body text-ink-faint">Triggered a re-score.</p>
        ) : (
          <p className="mt-1 text-body text-ink-faint">Recorded, no re-score triggered.</p>
        )}
      </Card>
    );
  }

  if (type === "criterion") {
    const status = String(payload.status ?? "pending");
    return (
      <Card elevation="flat">
        <p className="text-body text-ink">{String(payload.statement ?? "Kill criterion")}</p>
        <Badge tone={status === "met" ? "go" : status === "failed" || status === "lapsed" ? "nogo" : "neutral"} className="mt-2">
          {status}
        </Badge>
      </Card>
    );
  }

  return (
    <Card elevation="flat">
      <p className="text-body text-ink">
        Milestone {payload.completed ? "completed" : "updated"}: {String(payload.block_title ?? "")}
      </p>
    </Card>
  );
}

interface DeltaTimelineProps {
  entries: TimelineEntry[];
}

/** C2: the merged, chronological feed across every event type — deltas
 * carry the most visual weight (direction, magnitude, which dimension
 * moved) since they're the reason a founder comes back. */
export function DeltaTimeline({ entries }: DeltaTimelineProps) {
  if (entries.length === 0) {
    return (
      <EmptyState
        title="Nothing has happened yet"
        description="Re-runs, evidence, and kill-criteria outcomes will show up here as they happen."
      />
    );
  }

  const ordered = [...entries].sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime());

  return (
    <div className="space-y-4">
      {ordered.map((entry, i) => (
        <div key={i} className="relative pl-6">
          <span
            className="absolute left-1 top-2 size-1.5 rounded-full bg-gold/60"
            aria-hidden="true"
          />
          {i < ordered.length - 1 && (
            <span className="absolute left-[7px] top-4 bottom-[-1rem] w-px bg-border-soft" aria-hidden="true" />
          )}
          <p className="mb-1.5 text-mono text-ink-faint">{formatDateTime(entry.at)}</p>
          {entry.type === "snapshot" ? (
            <SnapshotEntry payload={entry.payload} />
          ) : (
            <SimpleEntry type={entry.type} payload={entry.payload} />
          )}
        </div>
      ))}
    </div>
  );
}
