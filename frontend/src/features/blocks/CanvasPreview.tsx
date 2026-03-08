import { useCallback, useEffect, useRef } from "react";

interface Props {
  image: string;
  text: string;
  textPosition: [number, number];
  alignCenter: boolean;
  centerX: boolean;
  videoWidth: number;
  videoHeight: number;
  fontSize: number;
  onPositionChange: (x: number, y: number) => void;
}

export function CanvasPreview({
  image, text, textPosition, alignCenter, centerX,
  videoWidth, videoHeight, fontSize, onPositionChange,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef    = useRef<HTMLImageElement | null>(null);
  const dragging  = useRef(false);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const displayW = canvas.parentElement?.clientWidth || 200;
    const scale = displayW / videoWidth;
    canvas.width  = displayW;
    canvas.height = Math.round(videoHeight * scale);

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const img = imgRef.current;
    if (img?.complete && img.naturalWidth) {
      const imgScale = Math.min(canvas.width / img.naturalWidth, canvas.height / img.naturalHeight);
      const iw = img.naturalWidth  * imgScale;
      const ih = img.naturalHeight * imgScale;
      ctx.drawImage(img, (canvas.width - iw) / 2, (canvas.height - ih) / 2, iw, ih);
    }

    const [x, y] = textPosition;
    const sy = y * scale;
    const fs = Math.max(7, fontSize * scale);
    const lh = fs * 1.35;
    const pad = 4;

    ctx.font = `bold ${fs}px system-ui, sans-serif`;
    ctx.textBaseline = "top";

    const lines = (text || "").split("\n");
    const lineWidths = lines.map((l) => {
      const m = ctx.measureText(l || " ");
      return (m.actualBoundingBoxRight ?? m.width) as number;
    });
    const maxW = Math.max(...lineWidths, 1);
    const totalH = lines.length * lh;
    const sx = centerX ? (canvas.width - maxW) / 2 : x * scale;

    ctx.fillStyle = "rgba(0,0,0,0.82)";
    ctx.beginPath();
    ctx.roundRect(sx - pad, sy - pad, maxW + pad * 2, totalH + pad * 2, 5);
    ctx.fill();

    ctx.fillStyle = "#fff";
    lines.forEach((line, idx) => {
      const lw = lineWidths[idx];
      const lineX = alignCenter ? sx + (maxW - lw) / 2 : sx;
      ctx.fillText(line, lineX, sy + idx * lh);
    });

    if (!centerX) {
      ctx.strokeStyle = "#6366f1";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(sx, sy, 4, 0, Math.PI * 2);
      ctx.stroke();
    }
  }, [text, textPosition, alignCenter, centerX, videoWidth, videoHeight, fontSize]);

  // Load image
  useEffect(() => {
    const img = new Image();
    img.src = `/api/image/${encodeURIComponent(image)}`;
    img.onload = draw;
    imgRef.current = img;
  }, [image]);

  // Redraw on data changes
  useEffect(draw, [draw]);

  // Redraw when container resizes (tab switches, window resize)
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas?.parentElement) return;
    const obs = new ResizeObserver(draw);
    obs.observe(canvas.parentElement);
    return () => obs.disconnect();
  }, [draw]);

  function coordsFromEvent(e: { clientX: number; clientY: number }): [number, number] {
    const canvas = canvasRef.current!;
    const r = canvas.getBoundingClientRect();
    const s = videoWidth / canvas.offsetWidth;
    return [
      Math.round((e.clientX - r.left) * s),
      Math.round((e.clientY - r.top)  * s),
    ];
  }

  function handleMouseDown(e: React.MouseEvent) {
    dragging.current = true;
    const [x, y] = coordsFromEvent(e.nativeEvent);
    onPositionChange(x, y);
  }
  function handleMouseMove(e: React.MouseEvent) {
    if (!dragging.current) return;
    const [x, y] = coordsFromEvent(e.nativeEvent);
    onPositionChange(x, y);
  }
  function stopDrag() { dragging.current = false; }

  function handleTouchStart(e: React.TouchEvent) {
    e.preventDefault();
    const [x, y] = coordsFromEvent(e.touches[0]);
    onPositionChange(x, y);
  }
  function handleTouchMove(e: React.TouchEvent) {
    e.preventDefault();
    const [x, y] = coordsFromEvent(e.touches[0]);
    onPositionChange(x, y);
  }

  return (
    <div className="preview-wrap">
      <canvas
        ref={canvasRef}
        className="preview"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={stopDrag}
        onMouseLeave={stopDrag}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
      />
      <div className="preview-hint">drag to reposition text</div>
    </div>
  );
}
