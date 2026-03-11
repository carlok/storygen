import { useState, useEffect } from "react";
import { useVideo } from "@/context/VideoContext";
import { useAuth } from "@/context/AuthContext";
import { BlockTabs } from "@/features/blocks/BlockTabs";
import { BlockCard } from "@/features/blocks/BlockCard";
import { ActionsBar } from "@/features/actions/ActionsBar";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { generateVideo } from "@/api/blocks";
import { ApiError } from "@/api/client";
import type { Block } from "@/api/types";

export function HomePage() {
  const { blocks, setBlocks, videoWidth, videoHeight, fontSize, loading, error } = useVideo();
  const { me } = useAuth();

  const [activeIndex, setActiveIndex] = useState(0);
  const [generating, setGenerating]   = useState(false);
  const [status, setStatus] = useState<{ type: "success" | "error"; message: string } | null>(null);

  // Auto-dismiss success message after 4 s
  useEffect(() => {
    if (status?.type !== "success") return;
    const id = setTimeout(() => setStatus(null), 4000);
    return () => clearTimeout(id);
  }, [status]);

  // Ctrl+Enter (or Cmd+Enter on Mac) triggers generate
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && !generating) {
        handleGenerate();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [generating]);  // eslint-disable-line react-hooks/exhaustive-deps

  const updateBlock = (updated: Block) =>
    setBlocks((prev) => prev.map((b) => (b.index === updated.index ? updated : b)));

  const handleGenerate = async () => {
    setGenerating(true);
    setStatus(null);
    try {
      const updates = blocks.map((b) => ({
        index:         b.index,
        text:          b.text,
        align_center:  b.align_center,
        center_x:      b.center_x,
        bw:            b.bw,
        fade_in:       b.fade_in,
        fade_out:      b.fade_out,
        text_position: b.text_position,
      }));
      await generateVideo(updates);
      const email = me?.email ?? "your email";
      setStatus({ type: "success", message: `✓ Generating… the video will be sent to ${email}` });
    } catch (e) {
      setStatus({ type: "error", message: e instanceof ApiError ? e.detail : String(e) });
    } finally {
      setGenerating(false);
    }
  };

  return (
    <>
      <Header />
      <div className="container">
        {loading && <p style={{ color: "var(--text-muted)" }}>Loading…</p>}
        {error   && <p style={{ color: "var(--red)" }}>{error}</p>}

        {!loading && !error && (
          <>
            <BlockTabs
              blocks={blocks}
              activeIndex={activeIndex}
              onChange={setActiveIndex}
            />

            {blocks.map((b) =>
              b.index === activeIndex ? (
                <BlockCard
                  key={b.index}
                  block={b}
                  videoWidth={videoWidth}
                  videoHeight={videoHeight}
                  fontSize={fontSize}
                  onChange={updateBlock}
                />
              ) : null,
            )}

            <ActionsBar
              onGenerate={handleGenerate}
              generating={generating}
              status={status}
            />
          </>
        )}
      </div>
      <Footer />
    </>
  );
}
