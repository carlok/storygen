interface Props {
  visible: boolean;
  message: string;
}

export function Modal({ visible, message }: Props) {
  if (!visible) return null;
  return (
    <div className="modal-overlay" role="dialog" aria-modal aria-label={message}>
      <div className="modal-box">
        <div className="modal-spinner" />
        <p className="modal-msg">{message}</p>
      </div>
    </div>
  );
}
