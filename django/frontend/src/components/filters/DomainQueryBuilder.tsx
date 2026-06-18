import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Slider } from "@/components/ui/slider";
import { useQueryStore } from "@/stores/query-store";
import { HelpTooltip } from "@/components/ui/help-tooltip";

const INTERPRO_URL = "https://www.ebi.ac.uk/interpro/";

/** Count comma/whitespace-separated tokens, ignoring blanks. */
function countTokens(text: string): number {
  return text.split(/[,\s]+/).filter((t) => t.trim().length > 0).length;
}

/**
 * Domain query: a Boolean (AND/OR containment) section and an Architecture
 * (composite-Dice) section. Both are independent — whichever has accessions is
 * applied, and when both do their result sets are intersected.
 */
export function DomainQueryBuilder() {
  const domainText = useQueryStore((s) => s.domainText);
  const setDomainText = useQueryStore((s) => s.setDomainText);
  const domainThreshold = useQueryStore((s) => s.domainThreshold);
  const setDomainThreshold = useQueryStore((s) => s.setDomainThreshold);
  const domainLogic = useQueryStore((s) => s.domainLogic);
  const setDomainLogic = useQueryStore((s) => s.setDomainLogic);
  const architectureText = useQueryStore((s) => s.domainArchitectureText);
  const setArchitectureText = useQueryStore((s) => s.setDomainArchitectureText);
  const architectureWeight = useQueryStore((s) => s.architectureWeight);
  const setArchitectureWeight = useQueryStore((s) => s.setArchitectureWeight);
  const architectureThreshold = useQueryStore((s) => s.architectureThreshold);
  const setArchitectureThreshold = useQueryStore(
    (s) => s.setArchitectureThreshold,
  );

  const bothActive =
    domainText.trim().length > 0 && architectureText.trim().length > 0;

  return (
    <div className="space-y-4" data-tour="domain-query">
      {bothActive && (
        <p className="rounded bg-muted px-2 py-1 text-[10px] leading-tight text-muted-foreground">
          Both queries are active — results are the{" "}
          <span className="font-medium text-foreground">intersection</span>{" "}
          (iBGCs matching the Boolean <em>and</em> the architecture query).
        </p>
      )}

      <BooleanSection
        logic={domainLogic}
        onLogicChange={setDomainLogic}
        text={domainText}
        onTextChange={setDomainText}
        threshold={domainThreshold}
        onThresholdChange={setDomainThreshold}
      />

      <ArchitectureSection
        text={architectureText}
        onTextChange={setArchitectureText}
        weight={architectureWeight}
        onWeightChange={setArchitectureWeight}
        threshold={architectureThreshold}
        onThresholdChange={setArchitectureThreshold}
      />
    </div>
  );
}

interface BooleanSectionProps {
  logic: "and" | "or";
  onLogicChange: (v: "and" | "or") => void;
  text: string;
  onTextChange: (v: string) => void;
  threshold: number;
  onThresholdChange: (v: number) => void;
}

function BooleanSection({
  logic,
  onLogicChange,
  text,
  onTextChange,
  threshold,
  onThresholdChange,
}: BooleanSectionProps) {
  const includeCount = countTokens(
    text
      .split(/[,\s]+/)
      .filter((t) => t.trim() && !/^[-!]/.test(t.trim()))
      .join(" "),
  );
  const pct = Math.round(threshold * 100);
  // Mirror the backend: need = ceil(threshold × N_include), min 1.
  const need =
    includeCount > 0 ? Math.max(1, Math.ceil(threshold * includeCount)) : 0;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1 text-sm font-medium">
          Boolean <HelpTooltip tooltipKey="domain_containment" side="right" />
        </span>
        <ToggleGroup
          type="single"
          value={logic}
          onValueChange={(v) => {
            if (v === "and" || v === "or") onLogicChange(v);
          }}
          className="h-7"
        >
          <ToggleGroupItem value="and" className="h-6 px-2 text-xs">
            AND
          </ToggleGroupItem>
          <ToggleGroupItem value="or" className="h-6 px-2 text-xs">
            OR
          </ToggleGroupItem>
        </ToggleGroup>
      </div>

      <textarea
        value={text}
        onChange={(e) => onTextChange(e.target.value)}
        placeholder="IPR000873, PF00501, G3DSA:3.30.559.30, -PF00067"
        rows={2}
        className="w-full resize-y rounded-md border bg-background px-2 py-1.5 font-mono text-xs leading-snug placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-ring"
      />
      <p className="text-[10px] leading-tight text-muted-foreground">
        {includeCount} domain(s).{" "}
        <a
          href={INTERPRO_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          InterPro
        </a>{" "}
        entries (IPR…) or signature accessions (PF…, G3DSA:…, TIGR…). Prefix a
        token with <code>-</code> to exclude it.
      </p>

      {logic === "and" && (
        <div className="space-y-1">
          <div className="flex items-center justify-between text-[11px] uppercase tracking-wide text-muted-foreground">
            <span>Min match</span>
            <span className="font-mono text-foreground">
              {pct}%{includeCount > 0 ? ` · ≥${need}/${includeCount}` : ""}
            </span>
          </div>
          <Slider
            min={0}
            max={1}
            step={0.01}
            value={[threshold]}
            onValueChange={(v) => onThresholdChange(v[0] ?? 1)}
          />
          <div className="flex justify-between text-[10px] text-muted-foreground">
            <span>← any one</span>
            <span>all present →</span>
          </div>
        </div>
      )}

      {text.trim().length > 0 && (
        <button
          className="text-[10px] text-muted-foreground hover:text-foreground hover:underline"
          onClick={() => onTextChange("")}
        >
          Clear Boolean domains
        </button>
      )}
    </div>
  );
}

interface ArchitectureSectionProps {
  text: string;
  onTextChange: (v: string) => void;
  weight: number;
  onWeightChange: (v: number) => void;
  threshold: number;
  onThresholdChange: (v: number) => void;
}

function ArchitectureSection({
  text,
  onTextChange,
  weight,
  onWeightChange,
  threshold,
  onThresholdChange,
}: ArchitectureSectionProps) {
  const tokenCount = countTokens(text);
  const adjacency = (1 - weight).toFixed(2);
  const dice = weight.toFixed(2);

  return (
    <div className="space-y-2 border-t pt-3">
      <span className="flex items-center gap-1 text-sm font-medium">
        Architecture{" "}
        <HelpTooltip tooltipKey="architecture_search" side="right" />
      </span>

      <textarea
        value={text}
        onChange={(e) => onTextChange(e.target.value)}
        placeholder="PF00109, PF02801, PF00501, PF08659, ..."
        rows={2}
        className="w-full resize-y rounded-md border bg-background px-2 py-1.5 font-mono text-xs leading-snug placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-ring"
      />
      <div className="text-[10px] text-muted-foreground">
        {tokenCount} token(s), in order · unknown accessions are silently
        dropped
      </div>

      <div className="space-y-1">
        <div className="flex items-center justify-between text-[11px] uppercase tracking-wide text-muted-foreground">
          <span>Weight</span>
          <span className="font-mono text-foreground">
            Adj {adjacency} · Dice {dice}
          </span>
        </div>
        <Slider
          min={0}
          max={1}
          step={0.01}
          value={[weight]}
          onValueChange={(v) => onWeightChange(v[0] ?? 0.5)}
        />
        <div className="flex justify-between text-[10px] text-muted-foreground">
          <span>← Adjacency Index</span>
          <span>Sørensen-Dice →</span>
        </div>
      </div>

      <div className="space-y-1">
        <div className="flex items-center justify-between text-[11px] uppercase tracking-wide text-muted-foreground">
          <span>Min similarity</span>
          <span className="font-mono text-foreground">
            {threshold.toFixed(2)}
          </span>
        </div>
        <Slider
          min={0}
          max={1}
          step={0.01}
          value={[threshold]}
          onValueChange={(v) => onThresholdChange(v[0] ?? 0.25)}
        />
      </div>

      {text.trim().length > 0 && (
        <button
          className="text-[10px] text-muted-foreground hover:text-foreground hover:underline"
          onClick={() => onTextChange("")}
        >
          Clear architecture
        </button>
      )}
    </div>
  );
}
