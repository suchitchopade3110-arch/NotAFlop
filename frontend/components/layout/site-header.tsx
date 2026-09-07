import Link from "next/link";
import { LogoMark } from "@/components/layout/logo-mark";

export function SiteHeader() {
  return (
    <header className="flex items-center justify-between px-6 py-5 sm:px-10">
      <LogoMark />
      <Link
        href="/log"
        className="text-body text-ink-muted underline-offset-4 hover:text-gold-bright hover:underline"
      >
        Your log
      </Link>
    </header>
  );
}
