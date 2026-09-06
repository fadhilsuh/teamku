"use client";
import {FormEvent, Suspense, useEffect, useState} from "react";
import {useRouter, useSearchParams} from "next/navigation";
import {api} from "../../lib/api";
import {waitForAuthTransition} from "../../lib/transition";
import {AuthTransition} from "../../components/AuthTransition";
import {AuthLink, AuthLinks, AuthShell} from "../../components/AuthShell";
import {NotificationDialog, NotificationDialogState} from "../../components/NotificationDialog";

type Invite = {email: string; name: string; company: string; role: string; department: string};

function InviteForm() {
  const params = useSearchParams();
  const token = params.get("token") || "";
  const [invite, setInvite] = useState<Invite | null>(null);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [notification, setNotification] = useState<NotificationDialogState | null>(null);
  const router = useRouter();

  useEffect(() => {
    if (!token) return;
    api<Invite>(`/invites/${token}`)
      .then(setInvite)
      .catch(reason => setNotification({
        type: "error",
        title: "Undangan tidak valid",
        message: reason instanceof Error ? reason.message : "Undangan tidak valid",
      }));
  }, [token]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const startedAt = Date.now();
    setBusy(true);
    try {
      const result = await api<{access_token: string}>("/auth/accept-invite", {
        method: "POST",
        body: JSON.stringify({token, password}),
      });
      localStorage.setItem("movon_user", result.access_token);
      await waitForAuthTransition(startedAt);
      router.replace("/app/overview");
    } catch (reason) {
      await waitForAuthTransition(startedAt);
      setNotification({
        type: "error",
        title: "Aktivasi gagal",
        message: reason instanceof Error ? reason.message : "Aktivasi gagal",
      });
      setBusy(false);
    }
  }

  return (
    <>
      <AuthShell
        title={invite ? `Gabung ke ${invite.company}` : "Terima undangan"}
        subtitle={invite ? `Akun untuk ${invite.email} · ${invite.department}` : "Buka undangan dari email kerja Anda."}
      >
        <form className="stack" style={{marginTop: 32}} onSubmit={submit}>
          <label>Kata sandi<input disabled={busy || !invite} type="password" value={password} onChange={event => setPassword(event.target.value)} autoComplete="new-password" /></label>
          <button disabled={busy || !invite} type="submit">{busy ? "Mengaktifkan…" : "Aktifkan akun →"}</button>
        </form>
        <AuthLinks>
          <AuthLink href="/login">Sudah punya akun? Masuk</AuthLink>
        </AuthLinks>
      </AuthShell>
      <NotificationDialog notification={notification} onClose={() => setNotification(null)} />
      {busy && <AuthTransition message="Mengaktifkan akun…" />}
    </>
  );
}

export default function Invite() {
  return (
    <Suspense>
      <InviteForm />
    </Suspense>
  );
}
