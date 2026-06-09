"use client";

import { api } from "@/lib/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Activity, AlertTriangle, ArrowRight, CheckCircle, Download, RefreshCw, RotateCcw, Shield } from "lucide-react";
import { PageHeader } from "@/components/dashboard/page-header";
import { PermissionGate } from "@/components/dashboard/permission-gate";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";
import { MigrationStepIndicator, MIGRATION_STEPS } from "@/components/integrations/migration-step";
import { ImportProgress } from "@/components/integrations/import-progress";
import type { ImportJob, IntegrationConnection, ScanResult, DryRunResult, ProviderInfo, ApiError } from "@/lib/api/integrations";

const ENTITY_LABELS: Record<string, string> = {
  customers: "Customers",
  jobs: "Jobs",
  work_orders: "Work Orders",
  invoices: "Invoices",
  payments: "Payments",
  employees: "Employees",
  assets: "Assets",
  schedule_events: "Schedule Events",
  locations: "Locations",
};

export default function MigrationWizardPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const provider = searchParams.get("provider") || "quickbooks";

  const [step, setStep] = useState(1);
  const [completedSteps, setCompletedSteps] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [scanData, setScanData] = useState<ScanResult | null>(null);
  const [dryRunData, setDryRunData] = useState<DryRunResult | null>(null);
  const [importJobs, setImportJobs] = useState<ImportJob[]>([]);
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set(["customers", "jobs", "invoices"]));
  const [polling, setPolling] = useState(false);

  const { data: providerInfo } = useQuery({
    queryKey: ["integrations", "provider", provider],
    queryFn: () => api.get(`/integrations/providers/${provider}`).then((r) => r.data.data as ProviderInfo),
  });

  const { data: connections } = useQuery({
    queryKey: ["integrations", "connections"],
    queryFn: () => api.get("/integrations/connections").then((r) => r.data.data as IntegrationConnection[]),
  });

  const connection = connections?.find((c) => c.provider === provider);
  const isConnected = connection?.status === "connected";

  const markStepComplete = useCallback((stepNum: number) => {
    setCompletedSteps((prev) => new Set([...prev, stepNum]));
  }, []);

  const handleScan = async () => {
    if (!connection) return;
    setError(null);
    try {
      const resp = await api.post(
        `/integrations/${provider}/scan`,
        new URLSearchParams({ connection_id: connection.id }).toString(),
        { headers: { "Content-Type": "application/x-www-form-urlencoded" } }
      );
      setScanData(resp.data.data);
      markStepComplete(2);
      setStep(3);
    } catch (err: unknown) {
      const apiErr = err as ApiError;
      setError(apiErr?.response?.data?.detail || "Scan failed. Try reconnecting.");
    }
  };

  const handleDryRun = async () => {
    if (!connection) return;
    setError(null);
    try {
      const resp = await api.post(
        `/integrations/${provider}/dry-run`,
        new URLSearchParams({
          import_types: Array.from(selectedTypes).join(","),
          connection_id: connection.id,
        }).toString(),
        { headers: { "Content-Type": "application/x-www-form-urlencoded" } }
      );
      setDryRunData(resp.data.data);
      markStepComplete(3);
      setStep(4);
    } catch (err: unknown) {
      const apiErr = err as ApiError;
      setError(apiErr?.response?.data?.detail || "Dry run failed.");
    }
  };

  const handleImport = async () => {
    if (!connection) return;
    setError(null);
    try {
        await api.post(
        `/integrations/${provider}/import`,
        new URLSearchParams({
          import_types: Array.from(selectedTypes).join(","),
          connection_id: connection.id,
          dry_run: "false",
        }).toString(),
        { headers: { "Content-Type": "application/x-www-form-urlencoded" } }
      );
      queryClient.invalidateQueries({ queryKey: ["integrations"] });
      setPolling(true);
    } catch (err: unknown) {
      const apiErr = err as ApiError;
      setError(apiErr?.response?.data?.detail || "Import failed to start.");
    }
  };

  useEffect(() => {
    if (!polling) return;
    const interval = setInterval(async () => {
      try {
        const resp = await api.get("/integrations/imports");
        const jobs: ImportJob[] = resp.data.data || [];
        const relevantJobs = jobs.filter(
          (j) => j.provider === provider && selectedTypes.has(j.import_type)
        );
        setImportJobs(relevantJobs);

        const allDone = relevantJobs.length > 0 && relevantJobs.every(
          (j) => j.status === "completed" || j.status === "partial" || j.status === "failed"
        );
        if (allDone) {
          setPolling(false);
          markStepComplete(4);
          setStep(5);
          queryClient.invalidateQueries({ queryKey: ["integrations"] });
        }
      } catch {}
    }, 1000);
    return () => clearInterval(interval);
  }, [polling, provider, selectedTypes, markStepComplete, queryClient]);

  const handleRollback = async (jobId: string) => {
    try {
      await api.post(`/integrations/imports/${jobId}/rollback`);
      queryClient.invalidateQueries({ queryKey: ["integrations"] });
      setImportJobs([]);
      setStep(3);
      setCompletedSteps((prev) => { const next = new Set(prev); next.delete(4); return next; });
    } catch (err: unknown) {
      const apiErr = err as ApiError;
      setError(apiErr?.response?.data?.detail || "Rollback failed.");
    }
  };

  const toggleType = (type: string) => {
    setSelectedTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  return (
    <PermissionGate permission="settings:view">
      <div>
        <PageHeader
          title={`Migrate from ${providerInfo?.display_name || provider}`}
          description="Import your data into WorkTicket in a few steps."
        />

        <MigrationStepIndicator steps={MIGRATION_STEPS} currentStep={step} completedSteps={completedSteps} />

        {error && (
          <Alert variant="error" className="mb-4">
            <Shield className="h-4 w-4" />
            <span>{error}</span>
          </Alert>
        )}

        {/* Step 1: Connect */}
        {step === 1 && (
          <Card>
            <CardContent className="p-6">
              <h2 className="mb-2 text-lg font-semibold text-foreground">Connect Your System</h2>
              <p className="mb-4 text-sm text-muted-foreground">
                Link your {providerInfo?.display_name || provider} account to WorkTicket.
              </p>
              {isConnected ? (
                <div className="flex items-center gap-4">
                  <Badge variant="success" className="gap-1">
                    <CheckCircle className="h-3 w-3" /> Connected
                  </Badge>
                  <Button variant="primary" onClick={() => { setStep(2); markStepComplete(1); }}>
                    Continue <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </div>
              ) : (
                <div className="space-y-3">
                  <p className="text-sm text-amber-600 dark:text-amber-400">
                    <AlertTriangle className="mr-1 inline h-4 w-4" />
                    Not connected yet. Go to the Integrations page to connect first.
                  </p>
                  <Button variant="primary" onClick={() => router.push("/settings/integrations")}>
                    Go to Connections
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Step 2: Scan */}
        {step === 2 && (
          <Card>
            <CardContent className="p-6">
              <h2 className="mb-2 text-lg font-semibold text-foreground">Scan Your Data</h2>
              <p className="mb-4 text-sm text-muted-foreground">
                We&apos;ll scan your {providerInfo?.display_name || provider} account to find all available records.
              </p>
              <Button variant="primary" onClick={handleScan}>
                <Activity className="mr-2 h-4 w-4" /> Start Scan
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Step 3: Preview (Dry Run Results) */}
        {step === 3 && (
          <Card>
            <CardContent className="p-6">
              <h2 className="mb-2 text-lg font-semibold text-foreground">Preview Your Data</h2>
              <p className="mb-4 text-sm text-muted-foreground">
                {scanData ? "Scan complete. Select which data to import and preview the results." : "Review what will be imported."}
              </p>

              {scanData?.counts && (
                <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
                  {Object.entries(scanData.counts).map(([type, count]) => (
                    <button
                      key={type}
                      onClick={() => toggleType(type)}
                      className={`rounded-lg border p-3 text-left transition-colors ${
                        selectedTypes.has(type)
                          ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20"
                          : "border-border bg-card hover:bg-gray-50 dark:hover:bg-gray-800/50"
                      } ${count <= 0 ? "opacity-50" : ""}`}
                      disabled={count <= 0}
                    >
                      <div className="text-sm font-medium text-foreground">{ENTITY_LABELS[type] || type}</div>
                      <div className="text-xs text-muted-foreground">
                        {count > 0 ? `${count} found` : "None"}
                      </div>
                    </button>
                  ))}
                </div>
              )}

              {dryRunData?.results && (
                <div className="mb-4 space-y-2">
                  <h3 className="text-sm font-semibold text-foreground">Import Preview</h3>
                  {Object.entries(dryRunData.results)
                    .filter(([type]) => selectedTypes.has(type))
                    .map(([type, result]) => (
                      <div key={type} className="flex items-center justify-between rounded-lg border border-border p-3">
                        <span className="text-sm font-medium text-foreground">{ENTITY_LABELS[type] || type}</span>
                        <div className="flex gap-3 text-xs">
                          <span className="text-green-600 dark:text-green-400">{result.new} new</span>
                          <span className="text-amber-600 dark:text-amber-400">{result.duplicates} existing</span>
                          <span className="text-muted-foreground">{result.total} total</span>
                        </div>
                      </div>
                    ))}
                </div>
              )}

              <div className="flex gap-3">
                <Button variant="secondary" onClick={handleDryRun}>
                  <RefreshCw className="mr-2 h-4 w-4" /> Run Preview
                </Button>
                <Button variant="primary" onClick={() => { markStepComplete(3); setStep(4); }}>
                  Proceed to Import <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Step 4: Import Execution */}
        {step === 4 && (
          <Card>
            <CardContent className="p-6">
              <h2 className="mb-2 text-lg font-semibold text-foreground">Import Your Data</h2>
              <p className="mb-4 text-sm text-muted-foreground">
                Importing {Array.from(selectedTypes).map((t) => ENTITY_LABELS[t] || t).join(", ")} from {providerInfo?.display_name || provider}.
              </p>

              {importJobs.length === 0 && !polling && (
                <Button variant="primary" size="lg" onClick={handleImport}>
                  <Download className="mr-2 h-5 w-5" /> Start Import
                </Button>
              )}

              <div className="mt-4 space-y-4">
                {importJobs.map((job) => (
                  <div key={job.id} className="rounded-lg border border-border p-4">
                    <div className="mb-2 flex items-center justify-between">
                      <span className="font-medium text-foreground">{ENTITY_LABELS[job.import_type] || job.import_type}</span>
                      <div className="flex items-center gap-2">
                        {job.status === "completed" && (
                          <Button variant="secondary" size="sm" onClick={() => handleRollback(job.id)}>
                            <RotateCcw className="mr-1 h-3 w-3" /> Rollback
                          </Button>
                        )}
                      </div>
                    </div>
                    <ImportProgress
                      progressPct={job.progress_pct}
                      imported={job.imported}
                      skipped={job.skipped}
                      failed={job.failed}
                      totalRecords={job.total_records}
                      status={job.status}
                      errorMessage={job.error_message}
                    />
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Step 5: Completion */}
        {step === 5 && (
          <Card>
            <CardContent className="p-6 text-center">
              <CheckCircle className="mx-auto mb-4 h-16 w-16 text-green-500" />
              <h2 className="mb-2 text-xl font-bold text-foreground">Migration Complete</h2>
              <p className="mb-4 text-muted-foreground">
                Your data has been successfully imported from {providerInfo?.display_name || provider}.
              </p>

              <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
                {importJobs.map((job) => (
                  <div key={job.id} className="rounded-lg border border-border p-3">
                    <div className="text-xs text-muted-foreground">{ENTITY_LABELS[job.import_type] || job.import_type}</div>
                    <div className="text-lg font-bold text-green-600">{job.imported}</div>
                    <div className="text-xs text-muted-foreground">imported</div>
                    {job.failed > 0 && (
                      <div className="text-xs text-red-500">{job.failed} failed</div>
                    )}
                  </div>
                ))}
              </div>

              <div className="flex justify-center gap-3">
                <Button variant="secondary" onClick={() => router.push("/dashboard")}>
                  Go to Dashboard
                </Button>
                <Button variant="primary" onClick={() => router.push("/customers")}>
                  View Customers <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </PermissionGate>
  );
}
