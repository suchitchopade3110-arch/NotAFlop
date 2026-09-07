/**
 * The "how it's different" section — two asymmetric blocks in a zigzag,
 * never three equal cards. Collapses to a single stacked column below
 * 768px (each block already spans full width there; the md:grid-cols-2
 * + alternating md:order utilities are what create the zigzag, and both
 * simply drop away under the sm breakpoint).
 */
export function Mechanism() {
  return (
    <section className="mx-auto w-full max-w-4xl px-6 py-16 sm:py-24">
      <div className="grid gap-10 md:grid-cols-2 md:gap-16">
        <div className="md:pt-10">
          <p className="text-mono text-gold-bright">2 / 5</p>
          <p className="mt-2 text-heading text-ink">Sources have to show up live</p>
          <p className="mt-3 text-body-l text-ink-muted">
            When fewer than two data sources return real, current information, the report says so
            plainly instead of quietly filling the gap with a confident-sounding guess.
          </p>
        </div>
        <div className="border-t border-border-soft pt-10 md:border-t-0 md:border-l md:pl-16 md:pt-0">
          <p className="text-mono text-pivot">conflict</p>
          <p className="mt-2 text-heading text-ink">Disagreement is shown, not smoothed over</p>
          <p className="mt-3 text-body-l text-ink-muted">
            When sources point different directions, that tension is surfaced as its own signal
            instead of averaged away into a single tidy number.
          </p>
        </div>
      </div>
    </section>
  );
}
