import type { Metadata } from "next";
import { SiteHeader } from "@/components/layout/site-header";
import { LogList } from "@/components/log/log-list";

export const metadata: Metadata = { title: "Your log" };

export default function LogPage() {
  return (
    <main id="main-content">
      <SiteHeader />
      <section className="mx-auto w-full max-w-2xl px-6 py-10 sm:py-14">
        <h1 className="text-display-l text-ink">Your log</h1>
        <p className="mt-2 text-body-l text-ink-muted">
          Every idea you&apos;ve chosen to keep, with its current score and when it last moved.
        </p>
        <div className="mt-8">
          <LogList />
        </div>
      </section>
    </main>
  );
}
