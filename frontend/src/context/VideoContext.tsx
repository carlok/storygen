import React, { createContext, useContext, useEffect, useState } from "react";
import { getBlocks } from "@/api/blocks";
import type { Block } from "@/api/types";

interface VideoCtx {
  blocks: Block[];
  videoWidth: number;
  videoHeight: number;
  fontSize: number;
  loading: boolean;
  error: string | null;
  setBlocks: React.Dispatch<React.SetStateAction<Block[]>>;
  reload: () => Promise<void>;
}

const VideoContext = createContext<VideoCtx>({
  blocks: [],
  videoWidth: 1080,
  videoHeight: 1920,
  fontSize: 48,
  loading: true,
  error: null,
  setBlocks: () => {},
  reload: async () => {},
});

export function VideoProvider({ children }: { children: React.ReactNode }) {
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [videoWidth, setVideoWidth] = useState(1080);
  const [videoHeight, setVideoHeight] = useState(1920);
  const [fontSize, setFontSize] = useState(48);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getBlocks();
      setBlocks(data.blocks);
      setVideoWidth(data.video_width);
      setVideoHeight(data.video_height);
      setFontSize(data.font_size);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load blocks");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
  }, []);

  return (
    <VideoContext.Provider
      value={{ blocks, videoWidth, videoHeight, fontSize, loading, error, setBlocks, reload }}
    >
      {children}
    </VideoContext.Provider>
  );
}

export const useVideo = () => useContext(VideoContext);
