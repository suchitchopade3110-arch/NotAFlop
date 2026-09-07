import { RoadmapPanel } from "@/components/verdict/roadmap-panel";
import { ShareCta } from "@/components/verdict/share-cta";

export function GoVerdict({ publicId }: { publicId: string | null }) {
  return (
    <div className="space-y-6">
      {publicId && <RoadmapPanel reportId={publicId} />}
      <div className="flex justify-end">
        <ShareCta publicId={publicId} variant="secondary" size="sm" label="Share this verdict" />
      </div>
    </div>
  );
}
