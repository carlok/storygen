import type { Block } from "@/api/types";

interface Props {
  blocks: Block[];
  activeIndex: number;
  onChange: (index: number) => void;
}

export function BlockTabs({ blocks, activeIndex, onChange }: Props) {
  return (
    <div className="tabs">
      {blocks.map((b) => (
        <button
          key={b.index}
          className={`tab-btn${b.index === activeIndex ? " active" : ""}`}
          onClick={() => onChange(b.index)}
        >
          Block {b.index + 1}
        </button>
      ))}
    </div>
  );
}
