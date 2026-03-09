import { useState } from "react";

interface Props {
  onGenerate: () => void;
  generating: boolean;
  filename: string | null;
  onSendEmail: (to: string) => void;
  emailSending: boolean;
  emailStatus: { type: "success" | "error"; message: string } | null;
  status: { type: "error"; message: string } | null;
}

export function ActionsBar({
  onGenerate, generating, filename, onSendEmail,
  emailSending, emailStatus, status,
}: Props) {
  const [emailTo, setEmailTo] = useState("");

  return (
    <div className="actions">
      <div className="action-row">
        <button
          className="btn-generate"
          disabled={generating}
          onClick={onGenerate}
        >
          Generate Video
        </button>

        {status && (
          <span className={`status ${status.type}`}>{status.message}</span>
        )}

        {filename && (
          <a
            className="download-link visible"
            href={`/api/video?name=${encodeURIComponent(filename)}`}
            download={filename}
          >
            Download Video
          </a>
        )}
      </div>

      <div className="email-row">
        <input
          type="email"
          placeholder="recipient@example.com"
          value={emailTo}
          onChange={(e) => setEmailTo(e.target.value)}
          disabled={emailSending || !filename}
        />
        <button
          className="btn-send"
          disabled={emailSending || !filename || !emailTo}
          onClick={() => onSendEmail(emailTo)}
        >
          Send Video
        </button>
        {emailStatus && (
          <span className={`email-status ${emailStatus.type}`}>
            {emailStatus.message}
          </span>
        )}
      </div>
    </div>
  );
}
