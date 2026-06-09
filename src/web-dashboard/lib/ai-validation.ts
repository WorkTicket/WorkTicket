import { z } from "zod";

// ─── Canonical pricing constants (mirrors backend/app/pricing/engine.py) ───

export const LINE_ITEM_TYPES = ["labor", "materials", "fee"] as const;
export type LineItemType = (typeof LINE_ITEM_TYPES)[number];

export const AI_CONFIDENCE_MIN = 0.0;
export const AI_CONFIDENCE_MAX = 1.0;
export const AI_HOURS_MIN = 0.0;
export const AI_HOURS_MAX = 200.0;
export const AI_LABOR_COST_MIN = 0.0;
export const AI_LABOR_COST_MAX = 50000.0;
export const AI_MAX_MATERIALS = 50;

// ─── Core pricing functions (canonical — must match backend) ───

/** ROUND_HALF_UP — matches backend _round_currency (Decimal.quantize with ROUND_HALF_UP).
 * Uses toFixed(3) to get a clean 3-decimal string, then applies half-up rounding
 * entirely in the string/integer domain to avoid floating-point multiplication artifacts. */
export function roundCurrency(value: number): number {
  if (value === 0) return 0;
  const sign = value < 0 ? -1 : 1;
  const abs = Math.abs(value);
  const str = abs.toFixed(3);
  const dot = str.indexOf(".");
  const intPart = str.slice(0, dot);
  const dec = str.slice(dot + 1);
  const firstTwo = dec.slice(0, 2);
  const third = parseInt(dec[2], 10);
  let cents = parseInt(intPart + firstTwo, 10);
  if (third >= 5) cents += 1;
  return sign * cents / 100;
}

export function computeDeterministicTotal(quantity: number, rate: number): number {
  return roundCurrency(quantity * rate);
}

export function computeSubtotal(lineItems: { total: number }[]): number {
  return roundCurrency(lineItems.reduce((sum, item) => sum + item.total, 0));
}

export function computeTotal(subtotal: number, tax: number): number {
  return roundCurrency(subtotal + tax);
}

export function recomputeLineItem(item: {
  quantity: number;
  rate: number;
  total?: number;
  [key: string]: unknown;
}) {
  const computed = computeDeterministicTotal(item.quantity, item.rate);
  return { ...item, total: computed };
}

export function recomputeEstimate(estimate: {
  line_items?: { quantity: number; rate: number; total?: number }[];
  tax?: number;
  subtotal?: number;
  total?: number;
  [key: string]: unknown;
}) {
  const items = (estimate.line_items || []).map(recomputeLineItem);
  const subtotal = computeSubtotal(items);
  const tax = roundCurrency(estimate.tax ?? 0);
  const total = computeTotal(subtotal, tax);
  return { ...estimate, line_items: items, subtotal, tax, total };
}

// ─── Validation functions (mirrors backend validate_line_item / validate_estimate) ───

export interface ValidationError {
  path: string;
  message: string;
}

export function validateLineItem(item: Record<string, unknown>, idx: number): ValidationError[] {
  const errors: ValidationError[] = [];

  if (!item.name || !String(item.name).trim()) {
    errors.push({ path: `line_items[${idx}].name`, message: "must be non-empty" });
  }

  if (!LINE_ITEM_TYPES.includes(item.item_type as LineItemType)) {
    errors.push({
      path: `line_items[${idx}].item_type`,
      message: `must be one of ${LINE_ITEM_TYPES.join(", ")}, got '${item.item_type}'`,
    });
  }

  const quantity = item.quantity;
  if (quantity == null) {
    errors.push({ path: `line_items[${idx}].quantity`, message: "is required" });
  } else if (typeof quantity !== "number" || quantity < 0) {
    errors.push({ path: `line_items[${idx}].quantity`, message: `must be >= 0, got ${quantity}` });
  }

  const rate = item.rate;
  if (rate == null) {
    errors.push({ path: `line_items[${idx}].rate`, message: "is required" });
  } else if (typeof rate !== "number" || rate < 0) {
    errors.push({ path: `line_items[${idx}].rate`, message: `must be >= 0, got ${rate}` });
  }

  const qty = typeof quantity === "number" ? quantity : 0;
  const r = typeof rate === "number" ? rate : 0;
  const computedTotal = computeDeterministicTotal(qty, r);
  const providedTotal = item.total;
  if (providedTotal != null && typeof providedTotal === "number" && Math.abs(providedTotal - computedTotal) > 0.02) {
    errors.push({
      path: `line_items[${idx}].total`,
      message: `${providedTotal} does not match computed total ${computedTotal} (${qty} * ${r})`,
    });
  }

  return errors;
}

export function validateEstimate(estimate: Record<string, unknown>): ValidationError[] {
  const errors: ValidationError[] = [];
  const lineItems = estimate.line_items;

  if (!Array.isArray(lineItems)) {
    errors.push({ path: "line_items", message: "must be a list" });
    return errors;
  }

  lineItems.forEach((item, idx) => {
    errors.push(...validateLineItem(item as Record<string, unknown>, idx));
  });

  const computedSubtotal = computeSubtotal(lineItems as { total: number }[]);
  const providedSubtotal = estimate.subtotal;
  if (providedSubtotal != null && typeof providedSubtotal === "number" && Math.abs(providedSubtotal - computedSubtotal) > 0.02) {
    errors.push({
      path: "subtotal",
      message: `${providedSubtotal} does not match computed subtotal ${computedSubtotal}`,
    });
  }

  const tax = typeof estimate.tax === "number" ? estimate.tax : 0;
  const computedTotal = computeTotal(computedSubtotal, tax);
  const providedTotal = estimate.total;
  if (providedTotal != null && typeof providedTotal === "number" && Math.abs(providedTotal - computedTotal) > 0.02) {
    errors.push({
      path: "total",
      message: `${providedTotal} does not match computed total ${computedTotal} (subtotal=${computedSubtotal} + tax=${tax})`,
    });
  }

  return errors;
}

// ─── AI output validation (Zod schemas + helpers) ───

const materialSchema = z.string().min(1);

export const aiOutputSchema = z.object({
  problem_type: z.string().min(1).optional(),
  summary: z.string().min(1).optional(),
  recommended_fix: z.string().min(1).optional(),
  estimated_hours: z.number().min(AI_HOURS_MIN).max(AI_HOURS_MAX).optional(),
  labor_cost_estimate: z.number().min(AI_LABOR_COST_MIN).max(AI_LABOR_COST_MAX).optional(),
  permit_required: z.boolean().optional(),
  confidence: z.number().min(AI_CONFIDENCE_MIN).max(AI_CONFIDENCE_MAX),
  materials: z.array(materialSchema).max(AI_MAX_MATERIALS).optional(),
  is_fallback: z.boolean().optional(),
});

export type ValidatedAiOutput = z.infer<typeof aiOutputSchema>;

export interface AiValidationResult {
  valid: boolean;
  data: ValidatedAiOutput | null;
  error: string | null;
}

export function validateAiOutput(raw: unknown): AiValidationResult {
  const result = aiOutputSchema.safeParse(raw);
  if (result.success) {
    return { valid: true, data: result.data, error: null };
  }
  const issues = result.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`).join("; ");
  return { valid: false, data: null, error: `Invalid AI output: ${issues}` };
}

const lineItemAISchema = z.object({
  name: z.string().optional(),
  ai_quantity: z.number().nonnegative().nullable().optional(),
  ai_rate: z.number().nonnegative().nullable().optional(),
  ai_total: z.number().nullable().optional(),
});

export const estimateAISchema = z.object({
  line_items: z.array(lineItemAISchema).optional(),
  confidence_score: z.number().min(0).max(100).optional(),
  assumptions: z.array(z.string()).optional(),
});

export type ValidatedEstimateAI = z.infer<typeof estimateAISchema>;

export interface LineItemWithAI {
  id?: string;
  name: string;
  item_type: LineItemType;
  quantity: number;
  rate: number;
  total: number;
  sort_order: number;
  override_reason?: string;
  ai_quantity?: number | null;
  ai_rate?: number | null;
  ai_total?: number | null;
}

export function computeAiTotal(item: { ai_quantity?: number | null; ai_rate?: number | null }): number | null {
  if (item.ai_quantity == null || item.ai_rate == null) return null;
  return computeDeterministicTotal(item.ai_quantity, item.ai_rate);
}

export function enrichLineItemWithComputedTotal(item: LineItemWithAI): LineItemWithAI {
  if (item.ai_quantity != null && item.ai_rate != null) {
    return { ...item, ai_total: computeDeterministicTotal(item.ai_quantity, item.ai_rate) };
  }
  return { ...item, ai_total: null };
}
