import { useEffect, useRef } from "react";
import Shepherd from "shepherd.js";
import { useOnboardingStore } from "@/stores/onboarding-store";
import { getTourSteps } from "./tour-steps";
import "./shepherd-theme.css";

export function GuidedTour() {
  const tourActive = useOnboardingStore((s) => s.tourActive);
  const endTour = useOnboardingStore((s) => s.endTour);
  const tourRef = useRef<Shepherd.Tour | null>(null);

  useEffect(() => {
    if (!tourActive) {
      if (tourRef.current) {
        tourRef.current.cancel();
        tourRef.current = null;
      }
      return;
    }

    const tour = new Shepherd.Tour({
      useModalOverlay: true,
      defaultStepOptions: {
        scrollTo: { behavior: "smooth", block: "center" },
        cancelIcon: { enabled: true },
      },
    });

    const steps = getTourSteps();
    steps.forEach((step) => tour.addStep(step));

    tour.on("complete", endTour);
    tour.on("cancel", endTour);

    tourRef.current = tour;

    // Small delay to let any mode switch render
    const timer = setTimeout(() => tour.start(), 300);

    return () => {
      clearTimeout(timer);
      tour.cancel();
      tourRef.current = null;
    };
  }, [tourActive, endTour]);

  return null;
}
