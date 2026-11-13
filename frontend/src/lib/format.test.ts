import { describe, expect, it } from "vitest";

import {
  formatDateTime,
  formatKm,
  nextParcelEvent,
  parcelActionLabel,
  relativeTime,
  serviceLabel,
  statusLabel,
  statusTone,
} from "./format";

describe("format helpers", () => {
  it("formats Kolkata times deterministically", () => {
    expect(formatDateTime("2026-11-13T04:30:00Z")).toBe("13 Nov, 10:00 am");
  });

  it("formats distances with one decimal", () => {
    expect(formatKm(12.345)).toBe("12.3 km");
    expect(formatKm(0)).toBe("0.0 km");
  });

  it("maps statuses to honest labels and tones", () => {
    expect(statusLabel("pending_matching")).toBe("Pending match");
    expect(statusLabel("pickup_arrived")).toBe("At pickup");
    expect(statusTone("delivered")).toBe("green");
    expect(statusTone("failed")).toBe("red");
    expect(serviceLabel("return")).toBe("Product return");
  });

  it("exposes legal next parcel steps only", () => {
    expect(nextParcelEvent("partner_accepted")).toBe("pickup_arrived");
    expect(nextParcelEvent("in_transit")).toBe("delivered");
    expect(nextParcelEvent("delivered")).toBeNull();
    expect(parcelActionLabel("picked_up")).toBe("Start transit");
  });

  it("describes recent timestamps", () => {
    const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000).toISOString();
    expect(relativeTime(fiveMinutesAgo)).toContain("min");
  });
});
