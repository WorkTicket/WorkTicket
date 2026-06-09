"use client";

import { AlertTriangle, CheckCircle, Loader2, XCircle } from "lucide-react";

interface ImportProgressProps {
  progressPct: number;
  imported: number;
  skipped: number;
  failed: number;
  totalRecords: number;
  status: string;
  errorMessage?: string;
}

export function ImportProgress({ progressPct, imported, skipped, failed, totalRecords, status, errorMessage }: ImportProgressProps) {
  const isActive = status === "in_progress" || status === "scanning";
  const isComplete = status === "completed";
  const isPartial = status === "partial";
  const isFailed = status === "failed";

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        {isActive && <Loader2 className="h-5 w-5 animate-spin text-blue-500" />}
        {isComplete && <CheckCircle className="h-5 w-5 text-green-500" />}
        {(isPartial) && <AlertTriangle className="h-5 w-5 text-amber-500" />}
        {isFailed && <XCircle className="h-5 w-5 text-red-500" />}
        <span className="font-medium text-foreground">
          {isActive && `Importing... ${Math.round(progressPct)}%`}
          {isComplete && "Import Complete"}
          {isPartial && "Import Complete (Partial)"}
          {isFailed && "Import Failed"}
          {!isActive && !isComplete && !isPartial && !isFailed && "Preparing..."}
        </span>
      </div>

      <div className="h-2 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
        <div
          className={`h-full rounded-full transition-all duration-500 ${
            isFailed ? "bg-red-500" : isPartial ? "bg-amber-500" : "bg-blue-500"
          }`}
          style={{ width: `${Math.min(progressPct, 100)}%` }}
        />
      </div>

      <div className="grid grid-cols-4 gap-2 text-center text-sm">
        <div className="rounded-lg bg-gray-50 p-2 dark:bg-gray-800">
          <div className="text-lg font-bold text-foreground">{totalRecords}</div>
          <div className="text-xs text-muted-foreground">Total</div>
        </div>
        <div className="rounded-lg bg-green-50 p-2 dark:bg-green-900/20">
          <div className="text-lg font-bold text-green-700 dark:text-green-400">{imported}</div>
          <div className="text-xs text-green-600 dark:text-green-500">Imported</div>
        </div>
        <div className="rounded-lg bg-amber-50 p-2 dark:bg-amber-900/20">
          <div className="text-lg font-bold text-amber-700 dark:text-amber-400">{skipped}</div>
          <div className="text-xs text-amber-600 dark:text-amber-500">Skipped</div>
        </div>
        <div className="rounded-lg bg-red-50 p-2 dark:bg-red-900/20">
          <div className="text-lg font-bold text-red-700 dark:text-red-400">{failed}</div>
          <div className="text-xs text-red-600 dark:text-red-500">Failed</div>
        </div>
      </div>

      {errorMessage && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
          {errorMessage}
        </div>
      )}
    </div>
  );
}
