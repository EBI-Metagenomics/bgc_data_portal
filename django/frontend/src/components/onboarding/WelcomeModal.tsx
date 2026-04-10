import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useOnboardingStore } from "@/stores/onboarding-store";
import { useModeStore } from "@/stores/mode-store";
import { Compass, Layers, Search, FlaskConical, Pin } from "lucide-react";

const slides = [
  {
    icon: Compass,
    headline: "Find promising organisms for your bioprospecting effort, faster.",
    body: "The Discovery Platform helps you explore thousands of sequenced assemblies \u2014 from isolated bacteria to environmental metagenomes \u2014 to identify samples or type strains worth testing, based on the novelty and diversity of their biosynthetic gene clusters (BGCs).",
  },
  {
    icon: Layers,
    headline: "Start from what you know \u2014 or from what you don\u2019t.",
    body: "Three modes, one platform. Explore Assemblies \u2014 browse and filter the full catalogue. Search BGCs \u2014 search by protein domain, sequence similarity, or chemical structure. Evaluate Asset \u2014 submit your own assembly or BGC for a structured comparison.",
  },
  {
    icon: Search,
    headline: "Two levels, always in view.",
    body: "Each mode shows two linked panels: one for assemblies (organisms or environmental samples) and one for their BGCs (the gene clusters that make natural products). Selecting an assembly populates its BGC panel automatically.",
  },
  {
    icon: Pin,
    headline: "Pin assemblies and BGCs as you explore. Export when ready.",
    body: "Use the Assembly Shortlist (up to 20) for screening decisions \u2014 export as CSV. Use the BGC Shortlist (up to 20) for specific clusters \u2014 export as GenBank (.gbk) files ready for downstream workflows.",
  },
  {
    icon: FlaskConical,
    headline: "Where would you like to begin?",
    body: null,
  },
];

export function WelcomeModal() {
  const showWelcome = useOnboardingStore((s) => s.showWelcome);
  const dismissWelcome = useOnboardingStore((s) => s.dismissWelcome);
  const startTour = useOnboardingStore((s) => s.startTour);
  const setMode = useModeStore((s) => s.setMode);
  const [step, setStep] = useState(0);
  const slide = slides[step]!;
  const Icon = slide.icon;
  const isLast = step === slides.length - 1;

  function handleOpenChange(open: boolean) {
    if (!open) dismissWelcome();
  }

  return (
    <Dialog open={showWelcome} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader className="items-center text-center">
          <div className="mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
            <Icon className="h-6 w-6 text-primary" />
          </div>
          <DialogTitle className="text-lg">{slide.headline}</DialogTitle>
          {slide.body && (
            <DialogDescription className="text-sm leading-relaxed">
              {slide.body}
            </DialogDescription>
          )}
        </DialogHeader>

        {/* Final slide: mode buttons */}
        {isLast && (
          <div className="flex flex-col gap-2 pt-2">
            <Button
              variant="outline"
              className="w-full justify-start gap-2"
              onClick={() => {
                setMode("explore");
                dismissWelcome();
              }}
            >
              <Compass className="h-4 w-4" />
              Explore Assemblies
            </Button>
            <Button
              variant="outline"
              className="w-full justify-start gap-2"
              onClick={() => {
                setMode("query");
                dismissWelcome();
              }}
            >
              <Search className="h-4 w-4" />
              Search BGCs
            </Button>
            <Button
              variant="outline"
              className="w-full justify-start gap-2"
              onClick={() => {
                setMode("assess");
                dismissWelcome();
              }}
            >
              <FlaskConical className="h-4 w-4" />
              Evaluate Asset
            </Button>
          </div>
        )}

        {/* Dot indicators */}
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
              <Button variant="outline" onClick={() => startTour()}>
                Take interactive tour
              </Button>
              <Button onClick={() => dismissWelcome()}>
                Start exploring
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
