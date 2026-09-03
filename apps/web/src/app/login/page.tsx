"use client";
import {FormEvent,useState} from "react";
import {useRouter} from "next/navigation";
import {api} from "../../lib/api";

const accounts=[{label:"HR Admin",email:"hr@movon.test"},{label:"Manager",email:"manager@movon.test"},{label:"Employee",email:"employee@movon.test"},{label:"Fresh check-in",email:"fresh@movon.test"}];

export default function Login(){
  const [email,setEmail]=useState("employee@movon.test"),[password,setPassword]=useState("Demo123!"),[error,setError]=useState(""),[busy,setBusy]=useState(false);
  const router=useRouter();
  async function submit(event:FormEvent){event.preventDefault();setBusy(true);setError("");try{const result=await api<{access_token:string}>("/auth/login",{method:"POST",body:JSON.stringify({email,password})});localStorage.setItem("movon_user",result.access_token);router.replace("/app/overview")}catch(reason){setError(reason instanceof Error?reason.message:"Login gagal")}finally{setBusy(false)}}
  return <main className="login-page"><section className="login-art"><div className="login-logo">mo<span>von</span></div><div><p className="eyebrow" style={{color:"#fff"}}>People operations, made human</p><h1>Presence with purpose.</h1><p>Kelola kehadiran, agenda harian, dan keputusan tim dalam satu ruang kerja yang tenang dan jelas.</p></div><p>PT Movon Solusi Kreatif · Jakarta, Indonesia</p></section><section className="login-form-wrap"><div className="login-form"><div className="brand">mo<span>von</span> HR</div><p className="eyebrow">Selamat datang kembali</p><h2>Masuk ke workspace Anda</h2><p className="muted">Gunakan akun kerja untuk melanjutkan.</p><form className="stack" style={{marginTop:32}} onSubmit={submit}><label>Email kerja<input type="email" value={email} onChange={event=>setEmail(event.target.value)} autoComplete="username"/></label><label>Kata sandi<input type="password" value={password} onChange={event=>setPassword(event.target.value)} autoComplete="current-password"/></label>{error&&<p className="notice">{error}</p>}<button disabled={busy} type="submit">{busy?"Memverifikasi…":"Masuk ke Movon HR →"}</button></form><div className="login-demo"><b>Pilih akun demo</b><div>{accounts.map(account=><button type="button" className={email===account.email?"active":""} onClick={()=>{setEmail(account.email);setPassword("Demo123!")}} key={account.email}>{account.label}</button>)}</div><small>Semua akun menggunakan kata sandi Demo123!</small></div></div></section></main>;
}
