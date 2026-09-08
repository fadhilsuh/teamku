"use client";
import {FormEvent,useState} from "react";
import {useRouter} from "next/navigation";
import {api} from "../../lib/api";
import {waitForAuthTransition} from "../../lib/transition";
import {AuthTransition} from "../../components/AuthTransition";
import {AuthLink, AuthLinks} from "../../components/AuthShell";
import {BrandLogo} from "../../components/BrandLogo";
import {NotificationDialog,NotificationDialogState} from "../../components/NotificationDialog";

const accounts=[{label:"HR Admin",email:"hr@movon.test"},{label:"Manager",email:"manager@movon.test"},{label:"Employee",email:"employee@movon.test"},{label:"Fresh check-in",email:"fresh@movon.test"}];

export default function Login(){
  const [email,setEmail]=useState("employee@movon.test"),[password,setPassword]=useState("Demo123!"),[notification,setNotification]=useState<NotificationDialogState|null>(null),[busy,setBusy]=useState(false);
  const router=useRouter();
  async function submit(event:FormEvent){
    event.preventDefault();
    const startedAt=Date.now();
    setBusy(true);
    try{
      const result=await api<{access_token:string}>("/auth/login",{method:"POST",body:JSON.stringify({email,password})});
      localStorage.setItem("movon_user",result.access_token);
      await waitForAuthTransition(startedAt);
      router.replace("/app/overview");
    }catch(reason){
      await waitForAuthTransition(startedAt);
      setNotification({type:"error",title:"Login gagal",message:reason instanceof Error?reason.message:"Login gagal"});
      setBusy(false);
    }
  }
  return <>
    <main className="login-page">
      <section className="login-art">
        <div className="login-logo"><BrandLogo variant="white"/></div>
        <div><p className="eyebrow" style={{color:"#fff"}}>powered by movon digital house</p><h1>Presence with purpose.</h1><p>Kelola kehadiran, agenda harian, dan keputusan tim dalam satu ruang kerja yang tenang dan jelas.</p></div>
      </section>
      <section className="login-form-wrap">
        <div className="login-form">
          <h2>Masuk ke workspace Anda</h2>
          <p className="muted">Gunakan akun kerja untuk melanjutkan.</p>
          <form className="stack" style={{marginTop:32}} onSubmit={submit}>
            <label>Email kerja<input disabled={busy} type="email" value={email} onChange={event=>setEmail(event.target.value)} autoComplete="username"/></label>
            <label>Kata sandi<input disabled={busy} type="password" value={password} onChange={event=>setPassword(event.target.value)} autoComplete="current-password"/></label>
            <button disabled={busy} type="submit">{busy?"Memverifikasi…":"Masuk ke Teamku →"}</button>
          </form>
          <AuthLinks>
            <AuthLink href="/forgot-password">Lupa kata sandi</AuthLink>
            <span>·</span>
            <AuthLink href="/signup">Buat workspace perusahaan</AuthLink>
          </AuthLinks>
          <div className="login-demo">
            <b>Pilih akun demo</b>
            <div>{accounts.map(account=><button disabled={busy} type="button" className={email===account.email?"active":""} onClick={()=>{setEmail(account.email);setPassword("Demo123!")}} key={account.email}>{account.label}</button>)}</div>
            <small>Semua akun menggunakan kata sandi Demo123!</small>
          </div>
        </div>
      </section>
    </main>
    <NotificationDialog notification={notification} onClose={()=>setNotification(null)}/>
    {busy&&<AuthTransition message="Menyiapkan workspace…"/>}
  </>;
}
