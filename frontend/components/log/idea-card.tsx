import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Badge, toneForVerdict } from "@/components/ui/badge";
import { relativeTime } from "@/lib/utils/format";
import type { IdeaSummary } from "@/types/api";

export function IdeaCard({ idea }: { idea: IdeaSummary }) {
  return (
    <Link href={`/log/${idea.idea_id}`} className="block">
      <Card
        elevation="flat"
        className="transition-colors duration-150 hover:border-gold/40"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="truncate text-heading-sm text-ink">{idea.keyword || "Untitled idea"}</p>
            <p className="mt-1 text-body text-ink-faint">
              {idea.last_snapshot_at ? `Last checked ${relativeTime(idea.last_snapshot_at)}` : "No snapshot yet"}
            </p>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-2">
            {idea.verdict && idea.raw_score !== null && (
              <Badge tone={toneForVerdict(idea.verdict)}>
                {idea.raw_score} · {idea.verdict}
              </Badge>
            )}
            {idea.status !== "active" && <Badge tone="neutral">{idea.status}</Badge>}
          </div>
        </div>
      </Card>
    </Link>
  );
}
