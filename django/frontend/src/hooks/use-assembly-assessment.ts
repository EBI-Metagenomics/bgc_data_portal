import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { postAssemblyAssessment, fetchAssessmentStatus } from "@/api/assessment";
import { useAssessStore } from "@/stores/assess-store";
import { useAssemblyWeightStore } from "@/stores/assembly-weight-store";
import type { AssemblyAssessmentResult } from "@/api/types";

export function useAssemblyAssessment() {
  const { assetType, assetId, taskId, status, result } = useAssessStore();
  const setTaskId = useAssessStore((s) => s.setTaskId);
  const setResult = useAssessStore((s) => s.setResult);
  const setStatus = useAssessStore((s) => s.setStatus);
  const weights = useAssemblyWeightStore();

  const mutation = useMutation({
    mutationFn: (assemblyId: number) =>
      postAssemblyAssessment(assemblyId, {
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

  // Auto-trigger assessment when assetId or weights change
  useEffect(() => {
    if (assetType === "assembly" && assetId && status === "idle") {
      mutation.mutate(assetId);
    }
  }, [assetType, assetId, weights.w_diversity, weights.w_novelty, weights.w_density]);

  // Reset to idle when weights change so re-assessment triggers
  useEffect(() => {
    if (assetType === "assembly" && assetId && status === "success") {
      useAssessStore.getState().setStatus("idle");
    }
  }, [weights.w_diversity, weights.w_novelty, weights.w_density]);

  // Poll for results
  const poll = useQuery({
    queryKey: ["assess-assembly-status", taskId],
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
      setResult(poll.data.result as AssemblyAssessmentResult);
    } else if (poll.data?.status === "FAILURE") {
      setStatus("error");
    }
  }, [poll.data]);

  return {
    isLoading: status === "pending" || mutation.isPending,
    isError: status === "error",
    result: result as AssemblyAssessmentResult | null,
    retry: () => assetId && mutation.mutate(assetId),
  };
}
