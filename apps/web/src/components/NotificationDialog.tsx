"use client";

import {Icon} from "./Icon";

export type NotificationDialogState = {
  type: "success" | "error" | "info";
  title: string;
  message: string;
};

export function NotificationDialog({notification,onClose}:{notification:NotificationDialogState|null;onClose:()=>void}) {
  if(!notification)return null;
  const icon=notification.type==="success"?"check":notification.type==="error"?"pin":"bell";
  return (
    <div className="dialog-backdrop" role="presentation" onClick={onClose}>
      <section className={`decision-dialog notification-dialog ${notification.type}`} role="dialog" aria-modal="true" aria-labelledby="notification-title" onClick={event=>event.stopPropagation()}>
        <span className="notification-dialog-icon"><Icon name={icon}/></span>
        <p className="eyebrow">{notification.type==="success"?"Berhasil":notification.type==="error"?"Perlu perhatian":"Notifikasi"}</p>
        <h2 id="notification-title">{notification.title}</h2>
        <p>{notification.message}</p>
        <div className="dialog-actions">
          <button type="button" className="primary-action auto-width" onClick={onClose}>Mengerti</button>
        </div>
      </section>
    </div>
  );
}
