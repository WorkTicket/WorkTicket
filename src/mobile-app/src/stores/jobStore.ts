import { create } from "zustand";
import { AIOutput, Quote } from "@/types";

interface JobState {
  activeJobId: string | null;
  uploadedMediaIds: string[];
  aiOutput: AIOutput | null;
  quote: Quote | null;
  isProcessing: boolean;
  setActiveJob: (jobId: string) => void;
  addMedia: (mediaId: string) => void;
  setAIOutput: (output: AIOutput) => void;
  setQuote: (quote: Quote) => void;
  setProcessing: (processing: boolean) => void;
  reset: () => void;
}

export const useJobStore = create<JobState>((set) => ({
  activeJobId: null,
  uploadedMediaIds: [],
  aiOutput: null,
  quote: null,
  isProcessing: false,
  setActiveJob: (jobId) => set({ activeJobId: jobId }),
  addMedia: (mediaId) => set((s) => ({ uploadedMediaIds: [...s.uploadedMediaIds, mediaId] })),
  setAIOutput: (output) => set({ aiOutput: output }),
  setQuote: (quote) => set({ quote }),
  setProcessing: (processing) => set({ isProcessing: processing }),
  reset: () =>
    set({
      activeJobId: null,
      uploadedMediaIds: [],
      aiOutput: null,
      quote: null,
      isProcessing: false,
    }),
}));
