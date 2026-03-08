import type { Block } from "@/api/types";
import { CanvasPreview } from "./CanvasPreview";

interface Props {
  block: Block;
  videoWidth: number;
  videoHeight: number;
  fontSize: number;
  onChange: (updated: Block) => void;
}

export function BlockCard({ block, videoWidth, videoHeight, fontSize, onChange }: Props) {
  const upd = (patch: Partial<Block>) => onChange({ ...block, ...patch });

  const setX = (v: number) =>
    upd({ text_position: [Math.max(0, Math.min(videoWidth, v)), block.text_position[1]] });
  const setY = (v: number) =>
    upd({ text_position: [block.text_position[0], Math.max(0, Math.min(videoHeight, v))] });

  return (
    <div className="block-card">
      <div className="block-meta">
        <strong>{block.image}</strong>
        &nbsp;·&nbsp;
        {block.start}s – {block.end}s ({block.end - block.start}s)
      </div>

      <div className="card-body">
        <div className="controls">
          <textarea
            value={block.text}
            onChange={(e) => upd({ text: e.target.value })}
            placeholder="Scene caption…"
          />

          <div
            className="slider-row x-row"
            data-testid="x-row"
            style={{ opacity: block.center_x ? 0.35 : 1, pointerEvents: block.center_x ? "none" : undefined }}
          >
            <div className="slider-label">
              X <span className="val">{block.text_position[0]}</span>
            </div>
            <input
              type="range"
              min={0}
              max={videoWidth}
              value={block.text_position[0]}
              onChange={(e) => setX(parseInt(e.target.value, 10))}
            />
          </div>

          <div className="slider-row">
            <div className="slider-label">
              Y <span className="val">{block.text_position[1]}</span>
            </div>
            <input
              type="range"
              min={0}
              max={videoHeight}
              value={block.text_position[1]}
              onChange={(e) => setY(parseInt(e.target.value, 10))}
            />
          </div>

          <div className="toggles">
            {(
              [
                ["align_center", "Align center"],
                ["center_x",     "Center X"],
                ["bw",           "B&W"],
                ["fade_in",      "Fade in"],
                ["fade_out",     "Fade out"],
              ] as [keyof Block, string][]
            ).map(([key, label]) => (
              <label key={key} className="toggle-label">
                <input
                  type="checkbox"
                  aria-label={label}
                  checked={!!block[key]}
                  onChange={(e) => upd({ [key]: e.target.checked })}
                />
                {label}
              </label>
            ))}
          </div>
        </div>

        <CanvasPreview
          image={block.image}
          text={block.text}
          textPosition={block.text_position}
          alignCenter={block.align_center}
          centerX={block.center_x}
          videoWidth={videoWidth}
          videoHeight={videoHeight}
          fontSize={fontSize}
          onPositionChange={(x, y) => upd({ text_position: [x, y] })}
        />
      </div>
    </div>
  );
}
