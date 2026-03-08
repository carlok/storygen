import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AdminTable } from "@/features/admin/AdminTable";
import type { UserSummary } from "@/api/types";

const alice: UserSummary = {
  id: "u1",
  email: "alice@example.com",
  display_name: "Alice",
  avatar_url: null,
  is_admin: false,
  is_active: true,
  created_at: "2025-01-15T00:00:00Z",
  job_count: 3,
};

describe("AdminTable", () => {
  it("renders empty state when no users", () => {
    render(<AdminTable users={[]} onPatch={vi.fn()} onDelete={vi.fn()} />);
    expect(screen.getByText(/no users/i)).toBeInTheDocument();
  });

  it("shows user email", () => {
    render(<AdminTable users={[alice]} onPatch={vi.fn()} onDelete={vi.fn()} />);
    expect(screen.getByText("alice@example.com")).toBeInTheDocument();
  });

  it("shows Active badge for active user", () => {
    render(<AdminTable users={[alice]} onPatch={vi.fn()} onDelete={vi.fn()} />);
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("shows Disabled badge for inactive user", () => {
    const inactive = { ...alice, is_active: false };
    render(<AdminTable users={[inactive]} onPatch={vi.fn()} onDelete={vi.fn()} />);
    expect(screen.getByText("Disabled")).toBeInTheDocument();
  });

  it("shows Admin badge when is_admin=true", () => {
    const admin = { ...alice, is_admin: true };
    render(<AdminTable users={[admin]} onPatch={vi.fn()} onDelete={vi.fn()} />);
    expect(screen.getByText("Admin")).toBeInTheDocument();
  });

  it("shows initials when avatar_url is null", () => {
    render(<AdminTable users={[alice]} onPatch={vi.fn()} onDelete={vi.fn()} />);
    expect(screen.getByText("A")).toBeInTheDocument();
  });

  it("calls onPatch with is_active:false when Disable clicked", async () => {
    const onPatch = vi.fn();
    render(<AdminTable users={[alice]} onPatch={onPatch} onDelete={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /disable/i }));
    expect(onPatch).toHaveBeenCalledWith("u1", { is_active: false });
  });

  it("calls onPatch with is_admin:true when Make admin clicked", async () => {
    const onPatch = vi.fn();
    render(<AdminTable users={[alice]} onPatch={onPatch} onDelete={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /make admin/i }));
    expect(onPatch).toHaveBeenCalledWith("u1", { is_admin: true });
  });
});
