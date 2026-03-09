import { render, screen, fireEvent } from "@testing-library/react";
import { CanvasPreview } from "@/features/blocks/CanvasPreview";

// ── jsdom canvas stubs ──────────────────────────────────────────────────────
// jsdom provides HTMLCanvasElement but getContext() returns null by default.
// Stub enough 2D context methods so CanvasPreview's draw() doesn't throw.
beforeAll(() => {
  const ctx: Partial<CanvasRenderingContext2D> = {
    fillRect: vi.fn(),
    clearRect: vi.fn(),
    drawImage: vi.fn(),
    fillText: vi.fn(),
    measureText: vi.fn(() => ({ width: 50 } as TextMetrics)),
    beginPath: vi.fn(),
    arc: vi.fn(),
    roundRect: vi.fn(),
    fill: vi.fn(),
    stroke: vi.fn(),
    set font(_v: string) {},
    set fillStyle(_v: string | CanvasGradient | CanvasPattern) {},
    set strokeStyle(_v: string | CanvasGradient | CanvasPattern) {},
    set lineWidth(_v: number) {},
    set textBaseline(_v: CanvasTextBaseline) {},
  };
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ctx as CanvasRenderingContext2D);
});

// Stub ResizeObserver (not in jsdom)
const mockObserve    = vi.fn();
const mockDisconnect = vi.fn();
class MockResizeObserver {
  observe    = mockObserve;
  unobserve  = vi.fn();
  disconnect = mockDisconnect;
}
vi.stubGlobal("ResizeObserver", MockResizeObserver);

// Stub Image so image-load never fires (keeps tests synchronous)
vi.stubGlobal("Image", class {
  src = "";
  onload: (() => void) | null = null;
  naturalWidth  = 0;
  naturalHeight = 0;
  complete      = false;
});

const defaultProps = {
  image: "photo.jpg",
  text: "Hello",
  textPosition: [100, 900] as [number, number],
  alignCenter: false,
  centerX: false,
  videoWidth: 1080,
  videoHeight: 1920,
  fontSize: 48,
  onPositionChange: vi.fn(),
};

describe("CanvasPreview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders a canvas element", () => {
    render(<CanvasPreview {...defaultProps} />);
    expect(document.querySelector("canvas")).toBeInTheDocument();
  });

  it("renders the hint text", () => {
    render(<CanvasPreview {...defaultProps} />);
    expect(screen.getByText(/drag to reposition text/i)).toBeInTheDocument();
  });

  it("registers a ResizeObserver on mount", () => {
    render(<CanvasPreview {...defaultProps} />);
    expect(mockObserve).toHaveBeenCalled();
  });

  it("disconnects ResizeObserver on unmount", () => {
    const { unmount } = render(<CanvasPreview {...defaultProps} />);
    unmount();
    expect(mockDisconnect).toHaveBeenCalled();
  });

  it("calls onPositionChange on mousedown", () => {
    render(<CanvasPreview {...defaultProps} />);
    const canvas = document.querySelector("canvas")!;

    // Stub getBoundingClientRect and offsetWidth so coordsFromEvent can compute coords
    Object.defineProperty(canvas, "getBoundingClientRect", {
      value: () => ({ left: 0, top: 0, width: 200, height: 355 }),
    });
    Object.defineProperty(canvas, "offsetWidth", { value: 200 });

    fireEvent.mouseDown(canvas, { clientX: 50, clientY: 100 });
    expect(defaultProps.onPositionChange).toHaveBeenCalledWith(270, 540);
  });

  it("does not call onPositionChange on mousemove without prior mousedown", () => {
    render(<CanvasPreview {...defaultProps} />);
    const canvas = document.querySelector("canvas")!;
    Object.defineProperty(canvas, "getBoundingClientRect", {
      value: () => ({ left: 0, top: 0, width: 200, height: 355 }),
    });
    Object.defineProperty(canvas, "offsetWidth", { value: 200 });

    fireEvent.mouseMove(canvas, { clientX: 50, clientY: 100 });
    expect(defaultProps.onPositionChange).not.toHaveBeenCalled();
  });

  it("calls onPositionChange on mousemove after mousedown", () => {
    render(<CanvasPreview {...defaultProps} />);
    const canvas = document.querySelector("canvas")!;
    Object.defineProperty(canvas, "getBoundingClientRect", {
      value: () => ({ left: 0, top: 0, width: 200, height: 355 }),
    });
    Object.defineProperty(canvas, "offsetWidth", { value: 200 });

    fireEvent.mouseDown(canvas, { clientX: 10, clientY: 10 });
    vi.clearAllMocks();
    fireEvent.mouseMove(canvas, { clientX: 60, clientY: 200 });
    expect(defaultProps.onPositionChange).toHaveBeenCalledTimes(1);
  });

  it("stops calling onPositionChange after mouseup", () => {
    render(<CanvasPreview {...defaultProps} />);
    const canvas = document.querySelector("canvas")!;
    Object.defineProperty(canvas, "getBoundingClientRect", {
      value: () => ({ left: 0, top: 0, width: 200, height: 355 }),
    });
    Object.defineProperty(canvas, "offsetWidth", { value: 200 });

    fireEvent.mouseDown(canvas, { clientX: 10, clientY: 10 });
    fireEvent.mouseUp(canvas);
    vi.clearAllMocks();
    fireEvent.mouseMove(canvas, { clientX: 60, clientY: 200 });
    expect(defaultProps.onPositionChange).not.toHaveBeenCalled();
  });
});
