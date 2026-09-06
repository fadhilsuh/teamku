"use client";
import {useEffect,useState} from "react";
import {NotificationDialog,NotificationDialogState} from "../../../../components/NotificationDialog";
import {api} from "../../../../lib/api";

type Payslip={id:string;period:string;employee:string;gross_rupiah:number;deductions_rupiah:number;net_rupiah:number;published_at:string};

export default function Payslips(){
  const [items,setItems]=useState<Payslip[]>([]),[notification,setNotification]=useState<NotificationDialogState|null>(null);
  const notify=(type:NotificationDialogState["type"],title:string,message:string)=>setNotification({type,title,message});
  const load=()=>api<{items:Payslip[]}>("/payroll/payslips",{},localStorage.getItem("movon_user")||undefined).then(result=>setItems(result.items)).catch(reason=>notify("error","Slip gaji gagal dimuat",reason instanceof Error?reason.message:"Slip gaji gagal dimuat."));
  useEffect(()=>{load()},[]);
  return <><NotificationDialog notification={notification} onClose={()=>setNotification(null)}/><section className="page-heading"><div><p className="eyebrow">Employee self service</p><h1>Slip Gaji</h1><p>Lihat rincian payroll yang sudah difinalisasi dan dipublikasikan untuk Anda.</p></div><button className="secondary-button" onClick={load}>Perbarui</button></section><section className="payslip-grid">{items.map(item=><article className="panel payslip-card" key={item.id}><div className="panel-head"><div><p className="eyebrow">{formatPeriod(item.period)}</p><h2>{item.employee}</h2></div><span className="status published">Terbit</span></div><div className="payslip-row"><span>Penghasilan bruto</span><b>{formatMoney(item.gross_rupiah)}</b></div><div className="payslip-row"><span>Total potongan</span><b>- {formatMoney(item.deductions_rupiah)}</b></div><div className="payslip-net"><span>Penerimaan bersih</span><strong>{formatMoney(item.net_rupiah)}</strong></div><small>Dipublikasikan {new Intl.DateTimeFormat("id-ID",{dateStyle:"medium",timeStyle:"short"}).format(new Date(item.published_at))}</small></article>)}{items.length===0&&<article className="panel feature-empty"><span>Rp</span><h2>Belum ada slip gaji</h2><p>Slip akan tampil setelah HR mempublikasikan payroll.</p></article>}</section></>;
}
function formatMoney(value:number){return new Intl.NumberFormat("id-ID",{style:"currency",currency:"IDR",maximumFractionDigits:0}).format(value)}
function formatPeriod(value:string){return new Intl.DateTimeFormat("id-ID",{month:"long",year:"numeric"}).format(new Date(`${value}-01T00:00:00`))}
