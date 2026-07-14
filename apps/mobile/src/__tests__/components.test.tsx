import { Badge, Metric } from "../components";

describe("mobile UI components", () => {
  it("renders fallback mode label text", () => {
    const element = Badge({ tone: "warn", children: "SAMPLE" });
    expect(JSON.stringify(element)).toContain("SAMPLE");
  });

  it("renders pending review metric value", () => {
    const element = Metric({ label: "Pending Reviews", value: "3", note: "Need human decision" });
    const serialized = JSON.stringify(element);
    expect(serialized).toContain("Pending Reviews");
    expect(serialized).toContain("3");
    expect(serialized).toContain("Need human decision");
  });
});
