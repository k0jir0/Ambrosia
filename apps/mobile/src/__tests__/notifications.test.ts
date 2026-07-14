import { targetFromUrl } from "../notifications";

describe("mobile notification and deep-link targets", () => {
  it("maps review links to review detail targets", () => {
    expect(targetFromUrl("ambrosia://review/rev-123")).toEqual({
      module: "reviews",
      reviewId: "rev-123"
    });
  });

  it("maps signal links to signal detail targets", () => {
    expect(targetFromUrl("ambrosia://signal/sig-456")).toEqual({
      module: "signals",
      signalId: "sig-456"
    });
  });

  it("maps scanner links to scanner module targets", () => {
    expect(targetFromUrl("ambrosia://scanner")).toEqual({ module: "scanner" });
  });
});
