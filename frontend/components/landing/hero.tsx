interface HeroProps {
  children: React.ReactNode; // the pitch form / filter feedback slot
}

export function Hero({ children }: HeroProps) {
  return (
    <section className="mx-auto w-full max-w-2xl px-6 pt-10 pb-16 sm:pt-16 sm:pb-24">
      <h1 className="text-display-xl text-ink">
        Know if it&apos;s worth building<span className="text-gold-bright">.</span>
      </h1>
      <p className="mt-5 text-body-l text-ink-muted">
        Pitch your idea. Get a scored verdict grounded in live market signals, not encouragement.
        Every score cites what backed it, and says plainly when the evidence was thin.
      </p>
      <p className="mt-3 text-body text-ink-faint">Free forever. No account, no card, no catch.</p>

      <div className="mt-8">{children}</div>
    </section>
  );
}
