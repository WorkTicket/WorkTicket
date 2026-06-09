import { describe, expect, it } from "vitest";
import { canAccessRoute, hasPermission, normalizeRole } from "@/lib/permissions";

describe("permissions", () => {
  it("normalizes office_manager to dispatcher", () => {
    expect(normalizeRole("office_manager")).toBe("dispatcher");
  });

  it("grants billing access to owner only for manage", () => {
    expect(hasPermission("owner", "billing:manage")).toBe(true);
    expect(hasPermission("technician", "billing:manage")).toBe(false);
  });

  it("blocks technicians from customers route", () => {
    expect(canAccessRoute("technician", "/customers")).toBe(false);
    expect(canAccessRoute("dispatcher", "/customers")).toBe(true);
  });
});
