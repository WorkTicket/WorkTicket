"use client";

import { api } from "@/lib/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Shield } from "lucide-react";
import { PageHeader } from "@/components/dashboard/page-header";
import { PermissionGate } from "@/components/dashboard/permission-gate";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { ProviderCard } from "@/components/integrations/provider-card";
import type { ProviderInfo, IntegrationConnection, MigrationMetrics, ApiError } from "@/lib/api/integrations";

export default function IntegrationsPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [connectingProvider, setConnectingProvider] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [tenant, setTenant] = useState("default");
  const [error, setError] = useState<string | null>(null);

  const { data: providers, isLoading: loadingProviders } = useQuery({
    queryKey: ["integrations", "providers"],
    queryFn: () => api.get("/integrations/providers").then((r) => r.data.data as ProviderInfo[]),
  });

  const { data: connections } = useQuery({
    queryKey: ["integrations", "connections"],
    queryFn: () => api.get("/integrations/connections").then((r) => r.data.data as IntegrationConnection[]),
  });

  const { data: metrics } = useQuery({
    queryKey: ["integrations", "metrics"],
    queryFn: () => api.get("/integrations/migration-metrics").then((r) => r.data.data as MigrationMetrics),
  });

  const handleConnect = async () => {
    if (!connectingProvider) return;
    setError(null);
    try {
      await api.post("/integrations/connections", new URLSearchParams({
        provider: connectingProvider,
        tenant,
        access_token: apiKey,
      }).toString(), {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });
      queryClient.invalidateQueries({ queryKey: ["integrations"] });
      setConnectingProvider(null);
      setApiKey("");
      router.push(`/settings/integrations/migrate?provider=${connectingProvider}`);
    } catch (err: unknown) {
      const apiErr = err as ApiError;
      setError(apiErr?.response?.data?.detail || "Connection failed. Check your credentials and try again.");
    }
  };

  const connectedProviders = new Set(connections?.map((c) => c.provider) || []);

  if (loadingProviders) {
    return (
      <PermissionGate permission="settings:view">
        <PageHeader title="Integrations" description="Connect your existing business tools." />
        <div className="flex items-center justify-center py-20"><Spinner /></div>
      </PermissionGate>
    );
  }

  return (
    <PermissionGate permission="settings:view">
      <div>
        <PageHeader title="Integrations" description="Connect your existing business tools and migrate your data." />

        {/* Migration metrics */}
        {metrics && metrics.total_imports > 0 && (
          <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-2xl font-bold text-green-600">{metrics.success_rate_pct}%</div>
                <div className="text-xs text-muted-foreground">Success Rate</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-2xl font-bold text-foreground">{metrics.total_imported}</div>
                <div className="text-xs text-muted-foreground">Records Imported</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-2xl font-bold text-foreground">{metrics.completed}</div>
                <div className="text-xs text-muted-foreground">Completed</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-2xl font-bold text-foreground">{metrics.in_progress}</div>
                <div className="text-xs text-muted-foreground">In Progress</div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Connection modal */}
        {connectingProvider && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
            <div className="w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-lg">
              <h3 className="text-lg font-semibold text-foreground">
                Connect {providers?.find((p) => p.provider === connectingProvider)?.display_name || connectingProvider}
              </h3>
              <div className="mt-4 space-y-3">
                <div>
                  <label className="mb-1 block text-sm font-medium text-foreground">API Key / Access Token</label>
                  <Input
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="Paste your API key or access token"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-foreground">Tenant (optional)</label>
                  <Input value={tenant} onChange={(e) => setTenant(e.target.value)} placeholder="default" />
                </div>
                {error && (
                  <Alert variant="error">
                    <Shield className="h-4 w-4" />
                    <span>{error}</span>
                  </Alert>
                )}
                <div className="flex justify-end gap-2 pt-2">
                  <Button variant="secondary" onClick={() => { setConnectingProvider(null); setError(null); }}>
                    Cancel
                  </Button>
                  <Button variant="primary" onClick={handleConnect} disabled={!apiKey}>
                    Connect
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Provider grid */}
        <div className="grid gap-4 sm:grid-cols-2">
          {(providers || []).map((p) => (
            <ProviderCard
              key={p.provider}
              provider={{ ...p, health: connectedProviders.has(p.provider) ? "healthy" : "disconnected" }}
              onConnect={setConnectingProvider}
            />
          ))}
        </div>
      </div>
    </PermissionGate>
  );
}
