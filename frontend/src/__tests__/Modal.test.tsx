import { render, screen } from "@testing-library/react";
import { Modal } from "@/components/Modal";

describe("Modal", () => {
  it("renders nothing when visible=false", () => {
    const { container } = render(<Modal visible={false} message="loading" />);
    expect(container.firstChild).toBeNull();
  });

  it("shows the message when visible=true", () => {
    render(<Modal visible={true} message="Generating video…" />);
    expect(screen.getByText("Generating video…")).toBeInTheDocument();
  });

  it("renders the spinner element", () => {
    const { container } = render(<Modal visible={true} message="test" />);
    expect(container.querySelector(".modal-spinner")).toBeInTheDocument();
  });

  it("has role=dialog for accessibility", () => {
    render(<Modal visible={true} message="test" />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});
