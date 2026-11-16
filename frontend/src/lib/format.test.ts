import { describe, expect, it } from "vitest";

import { formatKm, formatWeight, initials, serviceLabel, statusLabel, statusTone } from "@/lib/format";

describe("format helpers", () => {
  it("labels v2 order statuses and tones", () => {
    expect(statusLabel("awaiting_assignment")).toBe("Awaiting assignment");
    expect(statusLabel("delivery_proof_pending")).toBe("Proof pending");
    expect(statusTone("delivered")).toBe("green");
    expect(statusTone("failed")).toBe("red");
  });

  it("formats distances and weights", () => {
    expect(formatKm(12.345)).toBe("12.3 km");
    expect(formatKm(null)).toBe("—");
    expect(formatWeight(0.4)).toBe("0.40 kg");
    expect(formatWeight(12)).toBe("12.0 kg");
  });

  it("labels services and derives initials", () => {
    expect(serviceLabel("return")).toBe("Product return");
    expect(serviceLabel("parcel")).toBe("Parcel");
    expect(initials("Arjun Das")).toBe("AD");
  });
});
