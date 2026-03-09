import { render, screen } from "@testing-library/react";
import { StatsBar } from "@/features/admin/StatsBar";
import type { AdminStats } from "@/api/types";

const baseStats: AdminStats = {
  total_users: 42,
  total_jobs: 7,
  disk_bytes: 0,
};

describe("StatsBar", () => {
  it("renders total users", () => {
    render(<StatsBar stats={baseStats} />);
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("renders total jobs", () => {
    render(<StatsBar stats={baseStats} />);
    expect(screen.getByText("7")).toBeInTheDocument();
  });

  it("renders disk usage label", () => {
    render(<StatsBar stats={baseStats} />);
    expect(screen.getByText(/disk used/i)).toBeInTheDocument();
  });

  it("formats disk_bytes with fmtBytes", () => {
    render(<StatsBar stats={{ ...baseStats, disk_bytes: 2048 }} />);
    // 2048 bytes = 2.0 KB
    expect(screen.getByText("2.0 KB")).toBeInTheDocument();
  });

  it("renders all three stat labels", () => {
    render(<StatsBar stats={baseStats} />);
    expect(screen.getByText(/users/i)).toBeInTheDocument();
    expect(screen.getByText(/videos generated/i)).toBeInTheDocument();
    expect(screen.getByText(/disk used/i)).toBeInTheDocument();
  });
});
