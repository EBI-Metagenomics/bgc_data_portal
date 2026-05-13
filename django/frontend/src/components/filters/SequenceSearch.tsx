import { useQueryStore } from "@/stores/query-store";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { HelpTooltip } from "@/components/ui/help-tooltip";

const MAX_AA_LENGTH = 5000;

// The slider operates on the negative log10 of the E-value:
//   slider = 0   →  E ≤ 1.0    (very permissive)
//   slider = 5   →  E ≤ 1e-5   (default; HMMER convention for "significant")
//   slider = 50  →  E ≤ 1e-50  (essentially identical)
const SLIDER_MIN = 0;
const SLIDER_MAX = 50;
const SLIDER_STEP = 1;

function sliderToEvalue(slider: number): number {
  return Math.pow(10, -slider);
}

function evalueToSlider(evalue: number): number {
  if (evalue <= 0) return SLIDER_MAX;
  const v = -Math.log10(evalue);
  return Math.max(SLIDER_MIN, Math.min(SLIDER_MAX, Math.round(v)));
}

function formatEvalue(evalue: number): string {
  if (evalue >= 1) return "≤ 1";
  const exponent = Math.round(-Math.log10(evalue));
  return `≤ 1e-${exponent}`;
}

function parseSequenceLength(raw: string): number {
  const lines = raw.trim().split("\n");
  const seqLines = lines.filter((l) => !l.startsWith(">"));
  return seqLines.join("").replace(/\s/g, "").length;
}

export function SequenceSearch() {
  const sequenceQuery = useQueryStore((s) => s.sequenceQuery);
  const setSequenceQuery = useQueryStore((s) => s.setSequenceQuery);
  const sequenceEvalue = useQueryStore((s) => s.sequenceEvalue);
  const setSequenceEvalue = useQueryStore((s) => s.setSequenceEvalue);

  const aaLength = parseSequenceLength(sequenceQuery);
  const isOverLimit = aaLength > MAX_AA_LENGTH;
  const sliderValue = evalueToSlider(sequenceEvalue);

  return (
    <div className="space-y-4 pt-2">
      <div className="space-y-1.5">
        <Label className="text-xs">Protein Sequence</Label>
        <textarea
          placeholder="Paste a protein sequence (FASTA or raw AA)..."
          value={sequenceQuery}
          onChange={(e) => setSequenceQuery(e.target.value)}
          className="vf-form__input w-full rounded-md border bg-background px-3 py-2 text-xs font-mono min-h-[80px] resize-y focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          rows={4}
        />
        <div className="flex items-center justify-between">
          <span
            className={`text-[10px] ${isOverLimit ? "text-destructive font-medium" : "text-muted-foreground"}`}
          >
            {aaLength > 0
              ? `${aaLength.toLocaleString()} / ${MAX_AA_LENGTH.toLocaleString()} AA`
              : ""}
          </span>
          {isOverLimit && (
            <span className="text-[10px] text-destructive">
              Exceeds maximum length
            </span>
          )}
        </div>
      </div>

      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <Label className="flex items-center gap-1 text-xs">E-value cutoff <HelpTooltip tooltipKey="phmmer_evalue" side="right" /></Label>
          <span className="font-mono text-xs text-muted-foreground">
            {formatEvalue(sequenceEvalue)}
          </span>
        </div>
        <Slider
          value={[sliderValue]}
          onValueChange={([v]) => {
            if (v !== undefined) setSequenceEvalue(sliderToEvalue(v));
          }}
          min={SLIDER_MIN}
          max={SLIDER_MAX}
          step={SLIDER_STEP}
          className="w-full"
        />
        <div className="flex justify-between text-[10px] text-muted-foreground">
          <span>permissive (1)</span>
          <span>strict (1e-50)</span>
        </div>
      </div>

      <p className="text-[10px] text-muted-foreground">
        Press "Run Query" above to search by protein similarity (phmmer). Results
        are combined with any active filters and domain conditions.
      </p>
    </div>
  );
}
