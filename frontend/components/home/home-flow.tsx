"use client";

import { SiteHeader } from "@/components/layout/site-header";
import { Hero } from "@/components/landing/hero";
import { Mechanism } from "@/components/landing/mechanism";
import { FreeForeverStrip } from "@/components/landing/free-forever-strip";
import { PitchForm } from "@/components/pitch/pitch-form";
import { FilterFeedback } from "@/components/pitch/filter-feedback";
import { StreamingView } from "@/components/verdict/streaming-view";
import { RecoveringView } from "@/components/verdict/recovering-view";
import { VerdictPresentation } from "@/components/verdict/verdict-presentation";
import { ClaimPrompt } from "@/components/claim/claim-prompt";
import { ErrorState } from "@/components/ui/error-state";
import { useValidationFlow } from "@/lib/hooks/use-validation-flow";

export function HomeFlow() {
  const flow = useValidationFlow();

  if (flow.stage === "idle" || flow.stage === "filtering") {
    return (
      <main id="main-content">
        <SiteHeader />
        <Hero>
          <PitchForm
            initialValue={flow.transcript}
            onSubmit={flow.submitPitch}
            submitting={flow.stage === "filtering"}
          />
        </Hero>
        <Mechanism />
        <FreeForeverStrip />
      </main>
    );
  }

  if (flow.stage === "filter_failed" && flow.filterResult) {
    return (
      <main id="main-content">
        <SiteHeader />
        <div className="mx-auto w-full max-w-2xl px-6 py-16">
          <FilterFeedback
            transcript={flow.transcript}
            filterResult={flow.filterResult}
            onRevise={flow.reviseAndRetry}
          />
        </div>
      </main>
    );
  }

  if (flow.stage === "connecting" || flow.stage === "streaming") {
    return (
      <main id="main-content">
        <SiteHeader />
        <StreamingView
          dimensions={flow.dimensions}
          signalQuality={flow.signalQuality}
          connecting={flow.stage === "connecting"}
        />
      </main>
    );
  }

  if (flow.stage === "recovering") {
    return (
      <main id="main-content">
        <SiteHeader />
        <RecoveringView attempt={flow.recoveryAttempt} maxAttempts={flow.recoveryMaxAttempts} />
      </main>
    );
  }

  if (flow.stage === "verdict" && flow.verdict) {
    return (
      <main id="main-content">
        <SiteHeader />
        <VerdictPresentation verdict={flow.verdict} />
        <ClaimPrompt />
      </main>
    );
  }

  return (
    <main id="main-content">
      <SiteHeader />
      <div className="mx-auto w-full max-w-lg px-6 py-16">
        <ErrorState
          title={flow.errorCopy?.title ?? "Something went wrong"}
          description={flow.errorCopy?.description ?? "Please try again."}
          onRetry={flow.reset}
          retryLabel="Start over"
        />
      </div>
    </main>
  );
}
