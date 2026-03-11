import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { ErrorBoundary } from "@/components/ErrorBoundary";

function Bomb() {
  throw new Error("test explosion");
}

describe("ErrorBoundary", () => {
  it("renders fallback when a child throws", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>
    );
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
    spy.mockRestore();
  });

  it("renders children normally when no error", () => {
    render(<ErrorBoundary><p>all good</p></ErrorBoundary>);
    expect(screen.getByText("all good")).toBeInTheDocument();
  });

  it("renders a Reload page button in the fallback", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>
    );
    expect(screen.getByRole("button", { name: /reload page/i })).toBeInTheDocument();
    spy.mockRestore();
  });

  it("calls window.location.reload when Reload button is clicked", async () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    const reloadSpy = vi.fn();
    Object.defineProperty(window, "location", {
      value: { reload: reloadSpy },
      writable: true,
    });
    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>
    );
    await userEvent.click(screen.getByRole("button", { name: /reload page/i }));
    expect(reloadSpy).toHaveBeenCalledTimes(1);
    spy.mockRestore();
  });
});
