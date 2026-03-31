import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { postGenomeAssessment, fetchAssessmentStatus } from "@/api/assessment";
import { useAssessStore } from "@/stores/assess-store";
import { useGenomeWeightStore } from "@/stores/genome-weight-store";
import type { GenomeAssessmentResult } from "@/api/types";

export function useGenomeAssessment() {
  const { assetType, assetId, taskId, status, result } = useAssessStore();
  const setTaskId = useAssessStore((s) => s.setTaskId);
  const setResult = useAssessStore((s) => s.setResult);
  const setStatus = useAssessStore((s) => s.setStatus);
  const weights = useGenomeWeightStore();

  const mutation = useMutation({
    mutationFn: (assemblyId: number) =>
      postGenomeAssessment(assemblyId, {
        w_diversity: weights.w_diversity,
        w_novelty: weights.w_novelty,
        w_density: weights.w_density,
      }),
    onSuccess: (data) => {
      setTaskId(data.task_id);
    },
    onError: () => {
      setStatus("error");
    },
  });

  // Auto-trigger assessment when assetId changes and we're in genome mode
  useEffect(() => {
    if (assetType === "genome" && assetId && status === "idle") {
      mutation.mutate(assetId);
    }
  }, [assetType, assetId]);

  // Poll for results
  const poll = useQuery({
    queryKey: ["assess-genome-status", taskId],
    queryFn: () => fetchAssessmentStatus(taskId!),
    enabled: !!taskId && status === "pending",
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data?.status === "SUCCESS" || data?.status === "FAILURE") return false;
      return 2000;
    },
  });

  // Update store when result arrives
  useEffect(() => {
    if (poll.data?.status === "SUCCESS" && poll.data.result) {
      setResult(poll.data.result as GenomeAssessmentResult);
    } else if (poll.data?.status === "FAILURE") {
      setStatus("error");
    }
  }, [poll.data]);

  return {
    isLoading: status === "pending" || mutation.isPending,
    isError: status === "error",
    result: result as GenomeAssessmentResult | null,
    retry: () => assetId && mutation.mutate(assetId),
  };
}
