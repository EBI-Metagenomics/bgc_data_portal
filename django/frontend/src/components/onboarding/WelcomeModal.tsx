import { useState, type ReactNode } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useOnboardingStore } from "@/stores/onboarding-store";
import { Compass, Search, Pin } from "lucide-react";
import { buildDocsUrl } from "@/lib/router-base";

interface Slide {
  icon: typeof Compass;
  headline: string;
  body: ReactNode;
}

const bodyClass = "text-sm leading-relaxed text-muted-foreground";

const slides: Slide[] = [
  {
    icon: Compass,
    headline: "From a catalogue of thousands to a tested shortlist.",
    body: (
      <p className={bodyClass}>
        The Discovery Platform helps you mine thousands of{" "}
        <strong>(meta)genomic assemblies</strong> — from isolate genomes to
        environmental metagenomes — for <strong>integrated BGCs (iBGCs)</strong>:
        overlapping biosynthetic gene cluster predictions consolidated into
        single candidates.
      </p>
    ),
  },
  {
    icon: Search,
    headline: "Query and triage.",
    body: (
      <>
        <p className={bodyClass}>
          Narrow the catalogue by <strong>metadata</strong> (taxonomy, biome, BGC
          class…) or by <strong>similarity</strong> in domain function, protein
          sequence, and predicted chemistry — or <strong>Load Asset</strong> to
          project your own assembly and compare it against the database. Then{" "}
          <strong>Run Query</strong> and browse the matches as a{" "}
          <strong>roster</strong> or a <strong>map</strong>, sorting by{" "}
          <strong>novelty</strong> (how unlike known validated clusters a
          candidate is), length, or other attributes to surface what's worth
          exploring.
        </p>
        <a
          href={buildDocsUrl()}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-1 inline-block text-xs font-medium text-primary hover:underline"
        >
          Full documentation →
        </a>
      </>
    ),
  },
  {
    icon: Pin,
    headline: "Compare, shortlist, then export.",
    body: (
      <p className={bodyClass}>
        <strong>Right-click</strong> any iBGC to set it as a{" "}
        <strong>reference</strong> or to <strong>find similar</strong> clusters;{" "}
        <strong>left-click</strong> another to compare it against that reference.
        Add the interesting ones to your <strong>shortlist</strong>. When ready,{" "}
        <strong>Generate Report</strong> — summarising core domains and taxonomy
        and biome distribution — and download <strong>GenBank (.gbk)</strong>{" "}
        files, assembly tables, or JSON for your downstream workflows.
      </p>
    ),
  },
];

export function WelcomeModal() {
  const showWelcome = useOnboardingStore((s) => s.showWelcome);
  const dismissWelcome = useOnboardingStore((s) => s.dismissWelcome);
  const startTour = useOnboardingStore((s) => s.startTour);
  const [step, setStep] = useState(0);
  const slide = slides[step]!;
  const Icon = slide.icon;
  const isLast = step === slides.length - 1;

  function handleOpenChange(open: boolean) {
    if (!open) dismissWelcome();
  }

  return (
    <Dialog open={showWelcome} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader className="items-center text-center">
          <div className="mb-3 flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
            <Icon className="h-8 w-8 text-primary" />
          </div>
          <DialogTitle className="text-xl">{slide.headline}</DialogTitle>
          {slide.body && (
            typeof slide.body === "string" ? (
              <p className="text-sm leading-relaxed text-muted-foreground">{slide.body}</p>
            ) : (
              slide.body
            )
          )}
        </DialogHeader>

        <div className="flex justify-center gap-1.5 py-1">
          {slides.map((_, i) => (
            <button
              key={i}
              className={`h-1.5 rounded-full transition-all ${
                i === step
                  ? "w-4 bg-primary"
                  : "w-1.5 bg-muted-foreground/30"
              }`}
              onClick={() => setStep(i)}
              aria-label={`Go to slide ${i + 1}`}
            />
          ))}
        </div>

        <DialogFooter className="gap-2 sm:justify-between">
          {isLast ? (
            <>
              <Button variant="outline" onClick={() => dismissWelcome()}>
                Start exploring
              </Button>
              <Button onClick={() => startTour()}>
                Take interactive tour
              </Button>
            </>
          ) : (
            <>
              <Button variant="ghost" size="sm" onClick={() => dismissWelcome()}>
                Skip
              </Button>
              <div className="flex gap-2">
                {step > 0 && (
                  <Button variant="outline" size="sm" onClick={() => setStep(step - 1)}>
                    Back
                  </Button>
                )}
                <Button size="sm" onClick={() => setStep(step + 1)}>
                  Next
                </Button>
              </div>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
