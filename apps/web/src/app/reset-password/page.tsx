"use client";
import {FormEvent, Suspense, useState} from "react";
import {useRouter, useSearchParams} from "next/navigation";
import {api} from "../../lib/api";
import {waitForAuthTransition} from "../../lib/transition";
import {AuthTransition} from "../../components/AuthTransition";
import {AuthLink, AuthLinks, AuthShell} from "../../components/AuthShell";
import {NotificationDialog, NotificationDialogState} from "../../components/NotificationDialog";

function ResetForm() {
  const params = useSearchParams();
  const token = params.get("token") || "";
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [notification, setNotification] = useState<NotificationDialogState | null>(null);
  const router = useRouter();

  async function submit(event: FormEvent) {
    event.preventDefault();
    const startedAt = Date.now();
    setBusy(true);
    try {
      const result = await api<{access_token: string}>("/auth/reset-password", {
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
        title: "Atur ulang gagal",
        message: reason instanceof Error ? reason.message : "Atur ulang gagal",
      });
      setBusy(false);
    }
  }

  return (
    <>
      <AuthShell title="Atur kata sandi baru" subtitle="Masukkan kata sandi baru untuk akun Anda.">
        <form className="stack" style={{marginTop: 32}} onSubmit={submit}>
          <label>Kata sandi baru<input disabled={busy} type="password" value={password} onChange={event => setPassword(event.target.value)} autoComplete="new-password" /></label>
          <button disabled={busy || !token} type="submit">{busy ? "Menyimpan…" : "Simpan kata sandi →"}</button>
        </form>
        <AuthLinks>
          <AuthLink href="/login">Kembali masuk</AuthLink>
        </AuthLinks>
      </AuthShell>
      <NotificationDialog notification={notification} onClose={() => setNotification(null)} />
      {busy && <AuthTransition message="Memperbarui akun…" />}
    </>
  );
}

export default function ResetPassword() {
  return (
    <Suspense>
      <ResetForm />
    </Suspense>
  );
}
