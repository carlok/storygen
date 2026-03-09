interface Props {
  onGenerate: () => void;
  generating: boolean;
  status: { type: "success" | "error"; message: string } | null;
}

export function ActionsBar({ onGenerate, generating, status }: Props) {
  return (
    <div className="actions">
      <div className="action-row">
        <button
          className="btn-generate"
          disabled={generating}
          onClick={onGenerate}
        >
          {generating ? "Queuing…" : "Generate Video"}
        </button>

        {status && (
          <span className={`status ${status.type}`}>{status.message}</span>
        )}
      </div>
    </div>
  );
}
