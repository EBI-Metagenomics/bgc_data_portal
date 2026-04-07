import { useQueryStore } from "@/stores/query-store";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";

const MAX_AA_LENGTH = 5000;

function parseSequenceLength(raw: string): number {
  const lines = raw.trim().split("\n");
  const seqLines = lines.filter((l) => !l.startsWith(">"));
  return seqLines.join("").replace(/\s/g, "").length;
}

export function SequenceSearch() {
  const sequenceQuery = useQueryStore((s) => s.sequenceQuery);
  const setSequenceQuery = useQueryStore((s) => s.setSequenceQuery);
  const sequenceThreshold = useQueryStore((s) => s.sequenceThreshold);
  const setSequenceThreshold = useQueryStore((s) => s.setSequenceThreshold);

  const aaLength = parseSequenceLength(sequenceQuery);
  const isOverLimit = aaLength > MAX_AA_LENGTH;

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
          <Label className="text-xs">Similarity Threshold</Label>
          <span className="font-mono text-xs text-muted-foreground">
            {sequenceThreshold.toFixed(2)}
          </span>
        </div>
        <Slider
          value={[sequenceThreshold]}
          onValueChange={([v]) => {
            if (v !== undefined) setSequenceThreshold(v);
          }}
          min={0.5}
          max={1}
          step={0.05}
          className="w-full"
        />
      </div>

      <p className="text-[10px] text-muted-foreground">
        Press "Run Query" above to search by protein similarity. Results are
        combined with any active filters and domain conditions.
      </p>
    </div>
  );
}
