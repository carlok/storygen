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

  it("calls onChange with updated text on textarea change", async () => {
    render(<BlockCard {...defProps} />);
    const textarea = screen.getByPlaceholderText(/scene caption/i);
    await userEvent.clear(textarea);
    await userEvent.type(textarea, "New text");
    expect(defProps.onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ text: expect.stringContaining("New text") })
    );
  });

  it("renders Y slider with correct value", () => {
    render(<BlockCard {...defProps} />);
    const sliders = screen.getAllByRole("slider");
    // first slider = X, second = Y
    const ySlider = sliders[1] as HTMLInputElement;
    expect(ySlider.value).toBe("900");
  });

  it("calls onChange when Y slider changes", () => {
    render(<BlockCard {...defProps} />);
    const sliders = screen.getAllByRole("slider");
    fireEvent.change(sliders[1], { target: { value: "500" } });
    expect(defProps.onChange).toHaveBeenCalledWith(
      expect.objectContaining({ text_position: [100, 500] })
    );
  });

  it("X row is visible and enabled when center_x is false", () => {
    render(<BlockCard {...defProps} />);
    const xRow = screen.getByTestId("x-row");
    expect(xRow).toHaveStyle({ opacity: 1 });
  });

  it("X row is dimmed and pointer-events:none when center_x is true", () => {
    const block = { ...baseBlock, center_x: true };
    render(<BlockCard {...defProps} block={block} />);
    const xRow = screen.getByTestId("x-row");
    expect(xRow).toHaveStyle({ opacity: 0.35 });
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
