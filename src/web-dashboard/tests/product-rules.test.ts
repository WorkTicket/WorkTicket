import { describe, expect, it } from "vitest";
import { AI_FEATURES_ENABLED, FUTURE_FEATURE_LABEL, FUTURE_FEATURES } from "@/lib/product-rules";

describe("product-rules", () => {
  it("locks AI off in v1", () => {
    expect(AI_FEATURES_ENABLED).toBe(false);
  });

  it("uses approved future-feature label", () => {
    expect(FUTURE_FEATURE_LABEL).toBe("Coming Soon");
  });

  it("does not use beta or enable wording in feature copy", () => {
    for (const feature of Object.values(FUTURE_FEATURES)) {
      expect(feature.title.toLowerCase()).not.toContain("beta");
      expect(feature.description.toLowerCase()).not.toContain("enable");
      expect(feature.description.toLowerCase()).not.toContain("ai-assisted");
    }
  });
});
