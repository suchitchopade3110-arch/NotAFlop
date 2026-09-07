import type { Metadata } from "next";
import Link from "next/link";
import { fetchShareCard } from "@/lib/api/server";
import { ShareCard } from "@/components/share/share-card";
import { Button } from "@/components/ui/button";

interface PageProps {
  params: Promise<{ token: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { token } = await params;
  const card = await fetchShareCard(token);
  if (!card) return { title: "Verdict not found" };

  const title = `${card.keyword || "This idea"} — ${card.verdict.toUpperCase()} (${card.raw_score}/100)`;
  const description = card.top_reasons.slice(0, 2).join(". ") || "A NotAFlop verdict, grounded in live market signals.";

  return {
    title,
    description,
    openGraph: { title, description, images: [`/share/${token}/opengraph-image`] },
    twitter: { card: "summary_large_image", title, description },
  };
}

export default async function SharePage({ params }: PageProps) {
  const { token } = await params;
  const card = await fetchShareCard(token);

  if (!card) {
    return (
      <main id="main-content" className="flex min-h-screen flex-col items-center justify-center px-6 text-center">
        <p className="text-heading-sm text-ink">This verdict isn&apos;t available</p>
        <p className="mt-2 max-w-sm text-body text-ink-muted">
          The link may be wrong, the idea may have been deleted, or you&apos;re requesting too
          quickly — try again shortly.
        </p>
        <Link href="/" className="mt-5">
          <Button variant="secondary">Back to NotAFlop</Button>
        </Link>
      </main>
    );
  }

  return (
    <main id="main-content">
      <ShareCard card={card} />
    </main>
  );
}
