import { describe, expect, it } from "vitest";
import { category, yearRows, type PartyRuleFile } from "./partyRule";

describe("category", () => {
  it("classifies governors", () => {
    expect(category("gov", "D", null, null)).toBe("D");
    expect(category("gov", null, "R", "R")).toBe("none");
  });
  it("needs governor and both chambers for a trifecta", () => {
    expect(category("trifecta", "R", "R", "R")).toBe("RT");
    expect(category("trifecta", "R", "R", "D")).toBe("Rd");
    expect(category("trifecta", "D", "T", "D")).toBe("Dd");
    expect(category("trifecta", "W", "W", "W")).toBe("O");
  });
});

describe("yearRows", () => {
  const file: PartyRuleFile = {
    first: 2000,
    last: 2001,
    popEstimateYear: 2025,
    states: {
      AA: { name: "A", admitted: 2000, pop: [300, 300], gov: ["D", "D"], upper: ["D", "D"], lower: ["D", "R"] },
      BB: { name: "B", admitted: 2001, pop: [null, 100], gov: [null, "R"], upper: [null, "R"], lower: [null, "R"] },
    },
  };
  it("weights by population and skips states before admission", () => {
    const [a, b] = yearRows(file, "trifecta", "people");
    expect(a.share).toEqual({ DT: 1 });
    expect(b.share).toEqual({ Dd: 0.75, RT: 0.25 });
    expect(b.states.Dd).toEqual(["AA"]);
  });
  it("counts states once", () => {
    const [, b] = yearRows(file, "gov", "states");
    expect(b.share).toEqual({ D: 0.5, R: 0.5 });
  });
});
