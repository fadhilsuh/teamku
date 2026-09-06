"use client";
import {FormEvent, useState} from "react";
import {api} from "../../lib/api";
import {AuthLink, AuthLinks, AuthShell} from "../../components/AuthShell";
import {NotificationDialog, NotificationDialogState} from "../../components/NotificationDialog";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [notification, setNotification] = useState<NotificationDialogState | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      await api("/auth/forgot-password", {method: "POST", body: JSON.stringify({email})});
      setNotification({
        type: "success",
        title: "Permintaan terkirim",
        message: "Jika email terdaftar, tautan atur ulang sudah dikirim. Di lingkungan lokal, tautan juga muncul di log API.",
      });
    } catch (reason) {
      setNotification({
        type: "error",
        title: "Permintaan gagal",
        message: reason instanceof Error ? reason.message : "Permintaan gagal",
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <AuthShell title="Lupa kata sandi" subtitle="Masukkan email kerja. Kami akan mengirim tautan jika akunnya ada.">
        <form className="stack" style={{marginTop: 32}} onSubmit={submit}>
          <label>Email kerja<input disabled={busy} type="email" value={email} onChange={event => setEmail(event.target.value)} autoComplete="username" /></label>
          <button disabled={busy} type="submit">{busy ? "Mengirim…" : "Kirim tautan →"}</button>
        </form>
        <AuthLinks>
          <AuthLink href="/login">Kembali masuk</AuthLink>
        </AuthLinks>
      </AuthShell>
      <NotificationDialog notification={notification} onClose={() => setNotification(null)} />
    </>
  );
}
