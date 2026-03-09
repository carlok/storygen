import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BlockCard } from "@/features/blocks/BlockCard";
import type { Block } from "@/api/types";

// CanvasPreview uses HTMLCanvasElement APIs that jsdom doesn't support;
// stub it so BlockCard tests stay fast and focused.
vi.mock("@/features/blocks/CanvasPreview", () => ({
  CanvasPreview: () => <div data-testid="canvas-preview" />,
}));

const baseBlock: Block = {
  index: 0,
  image: "photo.jpg",
  start: 0,
  end: 5,
  text: "Hello world",
  align_center: false,
  center_x: false,
  bw: false,
  fade_in: false,
  fade_out: false,
  text_position: [100, 900],
};

describe("BlockCard", () => {
  const defProps = {
    block: baseBlock,
    videoWidth: 1080,
    videoHeight: 1920,
    fontSize: 48,
    onChange: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders image filename", () => {
    render(<BlockCard {...defProps} />);
    expect(screen.getByText("photo.jpg")).toBeInTheDocument();
  });

  it("renders timing information", () => {
    render(<BlockCard {...defProps} />);
    expect(screen.getByText(/0s – 5s/)).toBeInTheDocument();
    expect(screen.getByText(/\(5s\)/)).toBeInTheDocument();
  });

  it("shows block text in the textarea", () => {
    render(<BlockCard {...defProps} />);
    expect(screen.getByDisplayValue("Hello world")).toBeInTheDocument();
  });

  it("calls onChange with updated text on textarea change", () => {
    // BlockCard is a controlled component whose value is driven by props.
    // The mock onChange spy doesn't feed back into block, so userEvent.type
    // would append to the stale "Hello world".  Use fireEvent.change to
    // directly fire a synthetic React change event with the desired value.
    render(<BlockCard {...defProps} />);
    const textarea = screen.getByPlaceholderText(/scene caption/i);
    fireEvent.change(textarea, { target: { value: "New text" } });
    expect(defProps.onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ text: "New text" })
    );
  });

  it.each([
    ["Align center", "align_center"],
    ["Center X", "center_x"],
    ["B&W", "bw"],
    ["Fade in", "fade_in"],
    ["Fade out", "fade_out"],
  ] as [string, keyof Block][])(
    "toggling '%s' checkbox calls onChange with %s toggled",
    async (label, key) => {
      render(<BlockCard {...defProps} />);
      const checkbox = screen.getByRole("checkbox", { name: new RegExp(label, "i") });
      await userEvent.click(checkbox);
      expect(defProps.onChange).toHaveBeenCalledWith(
        expect.objectContaining({ [key]: true })
      );
    }
  );

  it("renders the CanvasPreview stub", () => {
    render(<BlockCard {...defProps} />);
    expect(screen.getByTestId("canvas-preview")).toBeInTheDocument();
  });
});
