"use client";

import Link from "next/link";
import { AlertTriangle, CheckCircle, Clock, LinkIcon, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import type { ProviderInfo } from "@/lib/api/integrations";
import { PROVIDER_CATEGORIES } from "@/lib/api/integrations";

function statusBadge(status: string) {
  const map: Record<string, { variant: "success" | "warning" | "error" | "info" | "default"; label: string }> = {
    production: { variant: "success", label: "Available" },
    beta: { variant: "warning", label: "Beta" },
    stub: { variant: "default", label: "Coming Soon" },
    internal: { variant: "info", label: "Internal" },
  };
  const s = map[status] || map.default;
  return <Badge variant={s.variant}>{s.label}</Badge>;
}

function healthIcon(health: string) {
  const size = "h-4 w-4";
  switch (health) {
    case "healthy":
      return <CheckCircle className={`${size} text-green-500`} />;
    case "token_expiring":
      return <AlertTriangle className={`${size} text-amber-500`} />;
    case "disconnected":
      return <XCircle className={`${size} text-red-500`} />;
    case "rate_limited":
      return <Clock className={`${size} text-orange-500`} />;
    case "error":
      return <XCircle className={`${size} text-red-500`} />;
    default:
      return <Clock className={`${size} text-gray-400`} />;
  }
}

export function ProviderCard({ provider, onConnect }: { provider: ProviderInfo; onConnect: (p: string) => void }) {
  const isAvailable = provider.status === "production" || provider.status === "beta";
  const isConnected = provider.health === "healthy";

  return (
    <Card key={provider.provider}>
      <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-foreground">{provider.display_name}</h3>
            {statusBadge(provider.status)}
          </div>
          <p className="mt-1 text-sm text-muted-foreground">{provider.description}</p>
        </div>
        <div className="flex items-center gap-2">
          {healthIcon(provider.health)}
          {isConnected && (
            <Badge variant="success" className="text-xs">Connected</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <LinkIcon className="h-3 w-3" />
              {provider.auth_type.toUpperCase()}
            </span>
            <span>{PROVIDER_CATEGORIES[provider.category] || provider.category}</span>
          </div>
          <div className="flex gap-2">
            {isAvailable && (
              <>
                {isConnected ? (
                  <Link href={`/settings/integrations/migrate?provider=${provider.provider}`}>
                    <Button variant="secondary" size="sm">
                      Manage
                    </Button>
                  </Link>
                ) : (
                  <Button variant="primary" size="sm" onClick={() => onConnect(provider.provider)}>
                    Connect
                  </Button>
                )}
              </>
            )}
            {!isAvailable && (
              <span className="text-xs text-muted-foreground italic">Available in future phase</span>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
