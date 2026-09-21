"use client";
import {FormEvent, useEffect, useRef, useState} from "react";
import {useRouter} from "next/navigation";
import {api, ApiError} from "../../lib/api";
import {SignupErrors, SignupValues, validateSignup} from "../../lib/signup";
import {waitForAuthTransition} from "../../lib/transition";
import {PasswordInput} from "../../components/PasswordInput";
import {AuthTransition} from "../../components/AuthTransition";
import {AuthLink, AuthLinks, AuthShell} from "../../components/AuthShell";

const fields = [
  {name: "company_name", label: "Nama perusahaan", type: "text", autoComplete: "organization"},
  {name: "admin_name", label: "Nama Anda", type: "text", autoComplete: "name"},
  {name: "email", label: "Email kerja", type: "email", autoComplete: "username"},
  {name: "password", label: "Kata sandi", type: "password", autoComplete: "new-password"},
] as const;

export default function Signup() {
  const [values, setValues] = useState<SignupValues>({company_name: "", admin_name: "", email: "", password: ""});
  const [errors, setErrors] = useState<SignupErrors>({});
  const [formError, setFormError] = useState("");
  const [busy, setBusy] = useState(false);
  const [transitioning, setTransitioning] = useState(false);
  const [focusTarget, setFocusTarget] = useState<{id: string} | null>(null);
  const submitting = useRef(false);
  const router = useRouter();

  useEffect(() => {
    if (focusTarget && !busy) document.getElementById(focusTarget.id)?.focus();
  }, [focusTarget, busy]);

  function showErrors(next: SignupErrors, message = "") {
    setErrors(next);
    setFormError(message);
    const first = fields.find(field => next[field.name]);
    setFocusTarget({id: first ? `signup-${first.name}` : "signup-error"});
  }

  function change(name: keyof SignupValues, value: string) {
    setValues(current => ({...current, [name]: value}));
    setErrors(current => {
      const next = {...current};
      delete next[name];
      return next;
    });
    setFormError("");
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (submitting.current) return;
    const next = validateSignup(values);
    if (Object.keys(next).length) {
      showErrors(next);
      return;
    }
    const startedAt = Date.now();
    submitting.current = true;
    setBusy(true);
    setErrors({});
    setFormError("");
    try {
      const result = await api<{access_token: string}>("/auth/signup", {
        method: "POST",
        body: JSON.stringify({
          ...values,
          company_name: values.company_name.trim(),
          admin_name: values.admin_name.trim(),
          email: values.email.trim(),
        }),
      });
      localStorage.setItem("movon_user", result.access_token);
      setTransitioning(true);
      await waitForAuthTransition(startedAt);
      router.replace("/app/overview");
    } catch (reason) {
      const fieldErrors: SignupErrors = {};
      if (reason instanceof ApiError) {
        for (const {name} of fields) {
          if (reason.fieldErrors[name]) fieldErrors[name] = reason.fieldErrors[name];
        }
        if (reason.status === 409 && /email/i.test(reason.message)) {
          fieldErrors.email = "Email kerja sudah digunakan. Gunakan email lain atau masuk ke akun Anda.";
        }
      }
      showErrors(fieldErrors, Object.keys(fieldErrors).length ? "" : reason instanceof Error ? reason.message : "Pendaftaran belum berhasil. Silakan coba lagi.");
      setTransitioning(false);
      setBusy(false);
      submitting.current = false;
    }
  }

  return (
    <>
      <AuthShell title="Buat workspace perusahaan" subtitle="Daftarkan perusahaan Anda dan jadi admin pertamanya.">
        <form className="stack signup-form" onSubmit={submit} noValidate aria-busy={busy}>
          <p className="signup-hint">Semua kolom wajib diisi.</p>
          {(formError || Object.keys(errors).length > 0) && (
            <div id="signup-error" className="signup-error-summary" role="alert" aria-label="Pendaftaran belum berhasil" tabIndex={-1}>
              <strong>{formError ? "Workspace belum dapat dibuat" : "Periksa kembali isian Anda"}</strong>
              <p>{formError || "Perbaiki kolom yang ditandai, lalu pilih Buat workspace."}</p>
            </div>
          )}
          {fields.map(({name, label, type, autoComplete}) => {
            const Input = name === "password" ? PasswordInput : "input";
            return (
            <div className="signup-field" key={name}>
              <label htmlFor={`signup-${name}`}>{label}</label>
              <Input
                id={`signup-${name}`} name={name} {...(name !== "password" ? {type} : {})} autoComplete={autoComplete}
                required disabled={busy} value={values[name]}
                aria-invalid={Boolean(errors[name])}
                aria-describedby={[name === "password" ? "signup-password-hint" : "", errors[name] ? `signup-${name}-error` : ""].filter(Boolean).join(" ") || undefined}
                onChange={event => change(name, event.target.value)}
              />
              {name === "password" && <p id="signup-password-hint" className="signup-hint">Gunakan 8–128 karakter untuk kata sandi Anda.</p>}
              {errors[name] && <p id={`signup-${name}-error`} className="signup-field-error">{errors[name]}</p>}
            </div>
            );
          })}
          <button disabled={busy} type="submit">{busy ? "Membuat workspace…" : "Buat workspace →"}</button>
          <span className="signup-status" role="status">{busy ? "Sedang memproses pendaftaran. Mohon tunggu." : ""}</span>
        </form>
        <AuthLinks>
          Sudah punya akun? <AuthLink href="/login">Masuk</AuthLink>
        </AuthLinks>
      </AuthShell>
      {transitioning && <AuthTransition message="Menyiapkan perusahaan Anda…" />}
    </>
  );
}
