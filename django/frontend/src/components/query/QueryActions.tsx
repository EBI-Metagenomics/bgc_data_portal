import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useQueryStore } from "@/stores/query-store";
import { useDomainQuery } from "@/hooks/use-domain-query";
import { useSimilarBgcQuery } from "@/hooks/use-similar-bgc-query";
import { Play, Loader2 } from "lucide-react";

export function QueryActions() {
  const similarBgcSourceId = useQueryStore((s) => s.similarBgcSourceId);
  const conditions = useQueryStore((s) => s.domainConditions);
  const { runQuery, isFetching: domainFetching, hasConditions } =
    useDomainQuery();
  const { isFetching: similarFetching } = useSimilarBgcQuery();

  const isFetching = domainFetching || similarFetching;

  return (
    <div className="flex items-center gap-3 rounded-lg border bg-card p-3">
      {similarBgcSourceId ? (
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-xs">
            Similar BGC search
          </Badge>
          <span className="text-xs text-muted-foreground">
            Source: BGC #{similarBgcSourceId}
          </span>
          {isFetching && <Loader2 className="h-4 w-4 animate-spin" />}
        </div>
      ) : (
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            className="gap-1"
            onClick={runQuery}
            disabled={!hasConditions || isFetching}
          >
            {isFetching ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            Run Domain Query
          </Button>
          {conditions.length > 0 && (
            <span className="text-xs text-muted-foreground">
              {conditions.length} domain{conditions.length !== 1 ? "s" : ""}{" "}
              selected
            </span>
          )}
          {!hasConditions && (
            <span className="text-xs text-muted-foreground">
              Add domains in the sidebar to start a query
            </span>
          )}
        </div>
      )}
    </div>
  );
}
