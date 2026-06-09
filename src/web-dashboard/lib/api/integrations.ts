export interface ProviderInfo {
  provider: string;
  display_name: string;
  category: string;
  status: "production" | "stub" | "beta" | "internal";
  feature_flag: string;
  description: string;
  icon_url: string | null;
  docs_url: string | null;
  auth_type: string;
  scopes: string[];
  health: string;
}

export interface IntegrationConnection {
  id: string;
  provider: string;
  tenant: string;
  status: string;
  created_at: string | null;
  last_sync_at: string | null;
}

export interface ScanResult {
  status: string;
  provider: string;
  display_name: string;
  counts: Record<string, number>;
  reason?: string;
}

export interface DryRunResult {
  status: string;
  provider: string;
  results: Record<
    string,
    { total: number; new: number; duplicates: number; error?: string }
  >;
  reason?: string;
}

export interface ImportJob {
  id: string;
  provider: string;
  import_type: string;
  status: string;
  progress_pct: number;
  total_records: number;
  imported: number;
  skipped: number;
  failed: number;
  started_at: string | null;
  finished_at: string | null;
  error_message?: string;
}

export interface ImportReport extends ImportJob {
  logs: Array<{
    external_id: string;
    internal_id: string | null;
    entity_type: string;
    result: string;
    error_message: string | null;
  }>;
}

export interface MigrationMetrics {
  total_imports: number;
  completed: number;
  failed: number;
  in_progress: number;
  rolled_back_count: number;
  success_rate_pct: number;
  avg_duration_seconds: number;
  total_imported: number;
  total_skipped: number;
  total_failed_records: number;
}

export interface ConnectionHealth {
  connection_id: string;
  provider: string;
  tenant: string;
  health: "healthy" | "token_expiring" | "disconnected" | "rate_limited" | "error" | "unknown";
  connection_status: string;
  last_sync_at: string | null;
  last_error: string | null;
}

export const PROVIDER_CATEGORIES: Record<string, string> = {
  accounting: "Accounting",
  field_service: "Field Service",
  payments: "Payments",
  crm: "CRM",
  payroll: "Payroll & HR",
  scheduling: "Scheduling",
  inventory: "Inventory & Fleet",
  routing: "Routing",
  communication: "Communication",
  landscaping: "Landscaping",
};

export interface ApiError {
  response?: {
    data?: {
      detail?: string;
    };
  };
  message?: string;
}
