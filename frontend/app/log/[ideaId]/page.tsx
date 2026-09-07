import { SiteHeader } from "@/components/layout/site-header";
import { IdeaDetailView } from "@/components/log/idea-detail/idea-detail-view";

export default async function IdeaDetailPage({ params }: { params: Promise<{ ideaId: string }> }) {
  const { ideaId } = await params;
  return (
    <main id="main-content">
      <SiteHeader />
      <section className="mx-auto w-full max-w-3xl px-6 py-10 sm:py-14">
        <IdeaDetailView ideaId={ideaId} />
      </section>
    </main>
  );
}
