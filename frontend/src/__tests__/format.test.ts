import { fmtBytes, fmtDate } from "@/utils/format";

describe("fmtBytes", () => {
  it("shows bytes for values below 1 KB", () => {
    expect(fmtBytes(0)).toBe("0 B");
    expect(fmtBytes(512)).toBe("512 B");
    expect(fmtBytes(1023)).toBe("1023 B");
  });

  it("shows KB for values between 1 KB and 1 MB", () => {
    expect(fmtBytes(1024)).toBe("1.0 KB");
    expect(fmtBytes(2048)).toBe("2.0 KB");
    expect(fmtBytes(1024 * 500)).toBe("500.0 KB");
  });

  it("shows MB for values between 1 MB and 1 GB", () => {
    const mb = 1024 ** 2;
    expect(fmtBytes(mb)).toBe("1.0 MB");
    expect(fmtBytes(mb * 250)).toBe("250.0 MB");
  });

  it("shows GB for values 1 GB and above", () => {
    const gb = 1024 ** 3;
    expect(fmtBytes(gb)).toBe("1.00 GB");
    expect(fmtBytes(gb * 2)).toBe("2.00 GB");
  });
});

describe("fmtDate", () => {
  it("returns a non-empty string for a valid ISO date", () => {
    const result = fmtDate("2024-01-15T10:00:00Z");
    expect(typeof result).toBe("string");
    expect(result.length).toBeGreaterThan(0);
  });

  it("includes the year in the formatted date", () => {
    const result = fmtDate("2024-06-01T00:00:00Z");
    expect(result).toContain("2024");
  });
});
