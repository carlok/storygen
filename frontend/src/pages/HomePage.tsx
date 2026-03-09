import { useState } from "react";
import { useVideo } from "@/context/VideoContext";
import { BlockTabs } from "@/features/blocks/BlockTabs";
import { BlockCard } from "@/features/blocks/BlockCard";
import { ActionsBar } from "@/features/actions/ActionsBar";
import { Modal } from "@/components/Modal";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { generateVideo, sendEmail } from "@/api/blocks";
import { ApiError } from "@/api/client";
import type { Block } from "@/api/types";

export function HomePage() {
  const { blocks, setBlocks, videoWidth, videoHeight, fontSize, loading, error } = useVideo();

  const [activeIndex, setActiveIndex] = useState(0);
  const [generating, setGenerating] = useState(false);
  const [emailSending, setEmailSending] = useState(false);
  const [modalMsg, setModalMsg] = useState<string | null>(null);
  const [filename, setFilename] = useState<string | null>(null);
  const [status, setStatus] = useState<{ type: "error"; message: string } | null>(null);
  const [emailStatus, setEmailStatus] = useState<
    { type: "success" | "error"; message: string } | null
  >(null);

  const updateBlock = (updated: Block) =>
    setBlocks((prev) => prev.map((b) => (b.index === updated.index ? updated : b)));

  const handleGenerate = async () => {
    setGenerating(true);
    setStatus(null);
    setModalMsg("Generating video…");
    try {
      const updates = blocks.map((b) => ({
        index:        b.index,
        text:         b.text,
        align_center: b.align_center,
        center_x:     b.center_x,
        bw:           b.bw,
        fade_in:      b.fade_in,
        fade_out:     b.fade_out,
        text_position: b.text_position,
      }));
      const data = await generateVideo(updates);
      setFilename(data.filename);
      setEmailStatus(null);
    } catch (e) {
      setStatus({ type: "error", message: e instanceof ApiError ? e.detail : String(e) });
    } finally {
      setModalMsg(null);
      setGenerating(false);
    }
  };

  const handleSendEmail = async (to: string) => {
    if (!filename) return;
    setEmailSending(true);
    setEmailStatus(null);
    setModalMsg("Sending video…");
    try {
      await sendEmail(to, filename);
      setEmailStatus({ type: "success", message: "Sent!" });
    } catch (e) {
      setEmailStatus({ type: "error", message: e instanceof ApiError ? e.detail : String(e) });
    } finally {
      setModalMsg(null);
      setEmailSending(false);
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
              filename={filename}
              onSendEmail={handleSendEmail}
              emailSending={emailSending}
              emailStatus={emailStatus}
              status={status}
            />
          </>
        )}
      </div>
      <Footer />
      <Modal visible={modalMsg !== null} message={modalMsg ?? ""} />
    </>
  );
}
