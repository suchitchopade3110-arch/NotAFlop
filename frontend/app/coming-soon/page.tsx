import type { Metadata } from "next";
import { ComingSoonPage } from "@/components/coming-soon/coming-soon-page";

export const metadata: Metadata = { title: "Coming soon" };

export default function Page() {
  return <ComingSoonPage />;
}
