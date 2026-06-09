export interface Customer {
  id: string;
  company_id: string;
  name: string;
  email?: string;
  phone?: string;
  address?: string;
}

export interface CustomerListResponse {
  customers: Customer[];
  total: number;
}

export interface Job {
  id: string;
  company_id: string;
  customer_id: string;
  technician_id: string;
  status: "pending" | "in_progress" | "completed" | "cancelled";
  scheduled_time: string;
  description?: string;
  address?: string;
  created_at: string;
  updated_at: string;
}

export interface JobListResponse {
  jobs: Job[];
  total: number;
}

export interface AIOutput {
  problem_type: string;
  summary: string;
  recommended_fix: string;
  materials: string[];
  estimated_hours: number;
  labor_cost_estimate: number;
  permit_required: boolean;
  confidence: number;
  is_fallback?: boolean;
}

export interface AIProcessResponse {
  job_id: string;
  status: string;
  output?: AIOutput;
}

export interface MediaItem {
  id: string;
  job_id: string;
  type: "photo" | "audio";
  storage_url: string;
  thumbnail_url?: string;
  ai_processed: boolean;
}

export interface Quote {
  quote_id: string;
  job_id: string;
  status: string;
  total_amount: number;
  line_items: Record<string, unknown>;
}
