import { describe, expect, it } from "vitest";
import { formatCalories, formatPercent, formatWeightGrams } from "@/core/utils/format";

describe("format utilities", () => {
  it("formats calories and percent", () => {
    expect(formatCalories(123.7)).toBe("124 cal");
    expect(formatPercent(67.4)).toBe("67%");
  });

  it("formats grams to kg when needed", () => {
    expect(formatWeightGrams(250)).toBe("250 g");
    expect(formatWeightGrams(1500)).toBe("1.5 kg");
  });
});
