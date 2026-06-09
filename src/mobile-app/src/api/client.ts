import { create } from "axios";
import { AI_FEATURES_ENABLED } from "@/constants/product-rules";
import { JobListResponse, AIProcessResponse, Quote } from "@/types";

let _getToken: (() => Promise<string | null>) | null = null;

export function setTokenGetter(fn: () => Promise<string | null>) {
  _getToken = fn;
}

export const api = create({
  baseURL: process.env.EXPO_PUBLIC_API_URL || "http://localhost:8000",
  timeout: 15000,
});

api.interceptors.request.use(async (config) => {
  if (_getToken) {
    const token = await _getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

export interface RegistrationStatus {
  registered: boolean;
  user_id: string;
  company_id?: string;
  role?: string;
}

export async function fetchRegistrationStatus(): Promise<RegistrationStatus> {
  const { data } = await api.get("/auth/registration-status");
  return data;
}

export async function registerUser(payload: {
  user_id: string;
  email: string;
  name: string;
  company_name: string;
}) {
  const { data } = await api.post("/auth/register", payload);
  return data as { user_id: string; company_id: string; role: string };
}

export async function updateJob(jobId: string, payload: { status?: string }) {
  const { data } = await api.patch(`/jobs/${jobId}`, payload);
  return data;
}

export async function fetchJobs(): Promise<JobListResponse> {
  const { data } = await api.get("/jobs");
  return data;
}

export async function fetchJob(jobId: string) {
  const { data } = await api.get(`/jobs/${jobId}`);
  return data;
}

export async function createJob(payload: {
  customer_id: string;
  description?: string;
  address?: string;
}) {
  const { data } = await api.post("/jobs", payload);
  return data;
}

export async function getUploadUrl(payload: {
  job_id: string;
  file_name: string;
  content_type: string;
  file_size: number;
  client_media_id?: string;
}) {
  const { data } = await api.post("/media/upload-url", payload);
  return data;
}

export async function confirmUpload(mediaId: string) {
  const { data } = await api.post("/media/confirm-upload", { media_id: mediaId });
  return data;
}

/** @deprecated v1 manual-first — do not call. See src/docs/PRODUCT_RULES.md */
export async function processJobAI(_jobId: string): Promise<AIProcessResponse> {
  if (!AI_FEATURES_ENABLED) {
    throw new Error("Not available in current version");
  }
  const { data } = await api.post(`/ai/process-job/${_jobId}`);
  return data;
}

/** @deprecated v1 manual-first — do not call. See src/docs/PRODUCT_RULES.md */
export async function getAIOutput(_jobId: string): Promise<AIProcessResponse> {
  if (!AI_FEATURES_ENABLED) {
    throw new Error("Not available in current version");
  }
  const { data } = await api.get(`/ai/output/${_jobId}`);
  return data;
}

export async function generateQuote(jobId: string): Promise<Quote> {
  const { data } = await api.post(`/quotes/generate/${jobId}`);
  return data;
}

export async function approveQuote(quoteId: string) {
  const { data } = await api.post(`/quotes/${quoteId}/approve`);
  return data;
}

export async function createCheckoutSession(): Promise<{ url: string }> {
  const { data } = await api.post("/billing/create-checkout-session");
  return data;
}

export async function fetchCustomers() {
  const { data } = await api.get("/jobs/customers");
  return data;
}

export async function createCustomer(payload: {
  name: string;
  email?: string;
  phone?: string;
  address?: string;
}) {
  const { data } = await api.post("/jobs/customers", payload);
  return data;
}

export async function registerPushToken(pushToken: string) {
  const { data } = await api.post("/notifications/register-push-token", {
    push_token: pushToken,
    platform: "expo",
  });
  return data;
}
