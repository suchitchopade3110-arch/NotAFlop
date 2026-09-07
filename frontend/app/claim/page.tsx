import { Suspense } from "react";
import type { Metadata } from "next";
import { SiteHeader } from "@/components/layout/site-header";
import { ClaimVerify } from "@/components/claim/claim-verify";

export const metadata: Metadata = { title: "Verifying your link" };

export default function ClaimPage() {
  return (
    <main id="main-content" className="flex min-h-screen flex-col">
      <SiteHeader />
      <Suspense fallback={null}>
        <ClaimVerify />
      </Suspense>
    </main>
  );
}
