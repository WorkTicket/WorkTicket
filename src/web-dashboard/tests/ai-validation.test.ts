import { describe, it, expect } from "vitest";
import {
  roundCurrency,
  computeDeterministicTotal,
  computeSubtotal,
  computeTotal,
  recomputeLineItem,
  recomputeEstimate,
  validateLineItem,
  validateEstimate,
  validateAiOutput,
} from "../lib/ai-validation";

// ─── roundCurrency ───

describe("roundCurrency", () => {
  it("rounds to two decimals", () => {
    expect(roundCurrency(10.456)).toBe(10.46);
    expect(roundCurrency(10.454)).toBe(10.45);
  });

  it("uses ROUND_HALF_UP", () => {
    expect(roundCurrency(10.455)).toBe(10.46);
    expect(roundCurrency(1.005)).toBe(1.01);
    expect(roundCurrency(0.565)).toBe(0.57);
  });

  it("handles integers", () => {
    expect(roundCurrency(10)).toBe(10.0);
    expect(roundCurrency(0)).toBe(0.0);
  });

  it("handles negative values", () => {
    expect(roundCurrency(-10.456)).toBe(-10.46);
    expect(roundCurrency(-10.455)).toBe(-10.46);
  });
});

// ─── computeDeterministicTotal ───

describe("computeDeterministicTotal", () => {
  it("computes basic multiplication", () => {
    expect(computeDeterministicTotal(2, 150)).toBe(300.0);
  });

  it("rounds correctly", () => {
    expect(computeDeterministicTotal(1.5, 99.99)).toBe(149.99);
  });

  it("handles zero quantity", () => {
    expect(computeDeterministicTotal(0, 150)).toBe(0.0);
  });

  it("handles zero rate", () => {
    expect(computeDeterministicTotal(2, 0)).toBe(0.0);
  });

  it("matches backend Decimal ROUND_HALF_UP at edge cases", () => {
    expect(computeDeterministicTotal(1.005, 1)).toBe(1.01);
    expect(computeDeterministicTotal(10.455, 1)).toBe(10.46);
    expect(computeDeterministicTotal(3, 0.335)).toBe(1.01);
  });
});

// ─── computeSubtotal ───

describe("computeSubtotal", () => {
  it("sums line item totals", () => {
    expect(computeSubtotal([{ total: 100.0 }, { total: 200.0 }, { total: 50.5 }])).toBe(350.5);
  });

  it("handles empty items", () => {
    expect(computeSubtotal([])).toBe(0.0);
  });

  it("handles single item", () => {
    expect(computeSubtotal([{ total: 99.99 }])).toBe(99.99);
  });
});

// ─── computeTotal ───

describe("computeTotal", () => {
  it("adds tax to subtotal", () => {
    expect(computeTotal(300.0, 30.0)).toBe(330.0);
  });

  it("handles zero tax", () => {
    expect(computeTotal(100.0, 0.0)).toBe(100.0);
  });

  it("rounds correctly", () => {
    expect(computeTotal(100.123, 10.012)).toBe(110.14);
  });
});

// ─── recomputeLineItem ───

describe("recomputeLineItem", () => {
  it("recomputes total from quantity and rate", () => {
    const result = recomputeLineItem({ quantity: 2, rate: 150, total: 999 });
    expect(result.total).toBe(300.0);
  });

  it("handles missing total", () => {
    const result = recomputeLineItem({ name: "Labor", quantity: 2, rate: 150 });
    expect(result.total).toBe(300.0);
  });

  it("preserves extra fields", () => {
    const result = recomputeLineItem({ name: "Test", quantity: 3, rate: 50, item_type: "labor", note: "x" });
    expect(result.total).toBe(150.0);
    expect((result as any).item_type).toBe("labor");
    expect((result as any).note).toBe("x");
  });
});

// ─── recomputeEstimate ───

describe("recomputeEstimate", () => {
  it("recomputes all estimate totals", () => {
    const estimate = {
      line_items: [
        { name: "Labor", quantity: 2, rate: 150, total: 0 },
        { name: "Materials", quantity: 1, rate: 300, total: 0 },
      ],
      tax: 45.0,
      subtotal: 0,
      total: 0,
    };
    const result = recomputeEstimate(estimate);
    expect(result.subtotal).toBe(600.0);
    expect(result.total).toBe(645.0);
    expect(result.line_items[0].total).toBe(300.0);
    expect(result.line_items[1].total).toBe(300.0);
  });

  it("handles empty line items", () => {
    const result = recomputeEstimate({ line_items: [], tax: 10 });
    expect(result.subtotal).toBe(0.0);
    expect(result.total).toBe(10.0);
  });
});

// ─── validateLineItem ───

describe("validateLineItem", () => {
  it("passes valid item", () => {
    const errors = validateLineItem({ name: "Labor", item_type: "labor", quantity: 2, rate: 150, total: 300 }, 0);
    expect(errors).toEqual([]);
  });

  it("rejects empty name", () => {
    const errors = validateLineItem({ name: "", item_type: "labor", quantity: 1, rate: 100, total: 100 }, 0);
    expect(errors.some((e) => e.path.includes("name"))).toBe(true);
  });

  it("rejects invalid item_type", () => {
    const errors = validateLineItem({ name: "X", item_type: "invalid", quantity: 1, rate: 100, total: 100 }, 0);
    expect(errors.some((e) => e.path.includes("item_type"))).toBe(true);
  });

  it("rejects negative quantity", () => {
    const errors = validateLineItem({ name: "X", item_type: "labor", quantity: -1, rate: 100, total: 0 }, 0);
    expect(errors.some((e) => e.path.includes("quantity"))).toBe(true);
  });

  it("rejects negative rate", () => {
    const errors = validateLineItem({ name: "X", item_type: "labor", quantity: 1, rate: -10, total: 0 }, 0);
    expect(errors.some((e) => e.path.includes("rate"))).toBe(true);
  });

  it("rejects mismatched total", () => {
    const errors = validateLineItem({ name: "X", item_type: "labor", quantity: 2, rate: 150, total: 999 }, 0);
    expect(errors.some((e) => e.path.includes("total"))).toBe(true);
  });

  it("accepts correctly rounded total", () => {
    const errors = validateLineItem({ name: "X", item_type: "labor", quantity: 1.5, rate: 99.99, total: 149.99 }, 0);
    expect(errors).toEqual([]);
  });

  it("rejects missing quantity", () => {
    const errors = validateLineItem({ name: "X", item_type: "labor", rate: 100, total: 0 } as Record<string, unknown>, 0);
    expect(errors.some((e) => e.path.includes("quantity"))).toBe(true);
  });
});

// ─── validateEstimate ───

describe("validateEstimate", () => {
  it("passes valid estimate", () => {
    const estimate = {
      line_items: [{ name: "Labor", item_type: "labor", quantity: 2, rate: 150, total: 300 }],
      subtotal: 300,
      tax: 30,
      total: 330,
    };
    const errors = validateEstimate(estimate);
    expect(errors).toEqual([]);
  });

  it("rejects mismatched subtotal", () => {
    const estimate = {
      line_items: [{ name: "Labor", item_type: "labor", quantity: 2, rate: 150, total: 300 }],
      subtotal: 999,
      tax: 0,
      total: 300,
    };
    const errors = validateEstimate(estimate);
    expect(errors.some((e) => e.path.includes("subtotal"))).toBe(true);
  });

  it("rejects mismatched total", () => {
    const estimate = {
      line_items: [{ name: "Labor", item_type: "labor", quantity: 2, rate: 150, total: 300 }],
      subtotal: 300,
      tax: 30,
      total: 999,
    };
    const errors = validateEstimate(estimate);
    expect(errors.some((e) => e.path.includes("total"))).toBe(true);
  });
});

// ─── validateAiOutput ───

describe("validateAiOutput", () => {
  it("accepts valid AI output", () => {
    const result = validateAiOutput({ confidence: 0.85, summary: "Fix leak", estimated_hours: 2, materials: ["pipe"] });
    expect(result.valid).toBe(true);
    expect(result.data).not.toBeNull();
  });

  it("rejects invalid AI output", () => {
    const result = validateAiOutput({ confidence: 99 });
    expect(result.valid).toBe(false);
    expect(result.error).toContain("confidence");
  });

  it("accepts fallback output", () => {
    const result = validateAiOutput({ confidence: 0, is_fallback: true });
    expect(result.valid).toBe(true);
  });

  it("rejects missing confidence", () => {
    const result = validateAiOutput({});
    expect(result.valid).toBe(false);
  });
});
