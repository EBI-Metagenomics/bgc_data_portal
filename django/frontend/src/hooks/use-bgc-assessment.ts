import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { postBgcAssessment, fetchAssessmentStatus } from "@/api/assessment";
import { useAssessStore } from "@/stores/assess-store";
import type { BgcAssessmentResult } from "@/api/types";

export function useBgcAssessment() {
  const { assetType, assetId, taskId, status, result } = useAssessStore();
  const setTaskId = useAssessStore((s) => s.setTaskId);
  const setResult = useAssessStore((s) => s.setResult);
  const setStatus = useAssessStore((s) => s.setStatus);

  const mutation = useMutation({
    mutationFn: (bgcId: number) => postBgcAssessment(bgcId),
    onSuccess: (data) => {
      setTaskId(data.task_id);
    },
    onError: () => {
      setStatus("error");
    },
  });

  // Auto-trigger assessment when assetId changes and we're in bgc mode
  useEffect(() => {
    if (assetType === "bgc" && assetId && status === "idle") {
      mutation.mutate(assetId);
    }
  }, [assetType, assetId]);

  // Poll for results
  const poll = useQuery({
    queryKey: ["assess-bgc-status", taskId],
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
      setResult(poll.data.result as BgcAssessmentResult);
    } else if (poll.data?.status === "FAILURE") {
      setStatus("error");
    }
  }, [poll.data]);

  return {
    isLoading: status === "pending" || mutation.isPending,
    isError: status === "error",
    result: result as BgcAssessmentResult | null,
    retry: () => assetId && mutation.mutate(assetId),
  };
}
