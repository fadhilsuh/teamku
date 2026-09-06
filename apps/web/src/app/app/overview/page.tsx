"use client";

import {useEffect,useState} from "react";
import {LazyLink as Link} from "../../../components/LazyLink";
import {NotificationDialog,NotificationDialogState} from "../../../components/NotificationDialog";
import {api} from "../../../lib/api";

type Attendance={checked_in_at:string;checked_out_at?:string;anomaly?:string};
type Dashboard={current_user:{name:string;role:string};headcount:number;present:number;late:number;pending_approvals:number;agenda_total:number;agenda_completed:number;attendance:Attendance[]};
type Leave={items:{status:string}[];balance:{remaining_days:number}};
type Payslip={period:string;published_at:string};
type Office={name:string};
const auth=()=>localStorage.getItem("movon_user")||undefined;

export default function Overview(){
  const [data,setData]=useState<Dashboard>();
  const [leave,setLeave]=useState<Leave>();
  const [payslip,setPayslip]=useState<Payslip>();
  const [officeName,setOfficeName]=useState("Kantor");
  const [notification,setNotification]=useState<NotificationDialogState|null>(null);
  const load=async()=>{
    try{
      const dashboard=await api<Dashboard>("/dashboard",{},auth());
      setData(dashboard);
      const [leaveResult,payslipResult,officeResult]=await Promise.all([
        api<Leave>("/leave-requests",{},auth()).catch(()=>undefined),
        api<{items:Payslip[]}>("/payroll/payslips",{},auth()).catch(()=>undefined),
        api<Office>("/settings/office",{},auth()).catch(()=>undefined),
      ]);
      setLeave(leaveResult);setPayslip(payslipResult?.items[0]);
      if(officeResult?.name)setOfficeName(officeResult.name);
    }catch(reason){setNotification({type:"error",title:"Beranda belum dapat dimuat",message:reason instanceof Error?reason.message:"Beranda belum dapat dimuat."})}
  };
  useEffect(()=>{load()},[]);
  return <>{data?<Home data={data} leave={leave} payslip={payslip} officeName={officeName}/>:<HomeLoading/>}<NotificationDialog notification={notification} onClose={()=>setNotification(null)}/></>;
}

function Home({data,leave,payslip,officeName}:{data:Dashboard;leave:Leave|undefined;payslip:Payslip|undefined;officeName:string}){
  const attendance=data.attendance[0];
  const checkedIn=Boolean(attendance&&!attendance.checked_out_at);
  const finished=Boolean(attendance?.checked_out_at);
  const attendanceLabel=checkedIn?"Sedang bekerja":finished?"Hari kerja selesai":"Belum check-in";
  const progress=data.agenda_total?Math.round(data.agenda_completed/data.agenda_total*100):0;
  const firstName=data.current_user.name.split(" ")[0];
  const isEmployee=data.current_user.role==="employee";
  const currentTime=now();
  const greeting=currentTime.getHours()<12?"Selamat pagi":currentTime.getHours()<17?"Selamat siang":"Selamat sore";
  const requestLabel=leave?.items[0]?leaveStatus(leave.items[0].status):"Tidak ada permohonan aktif";
  return <section className="home-page">
    <header className="home-hero">
      <div><p className="home-date">{formatLongDate(currentTime)}</p><h1>{greeting}, {firstName} <span aria-hidden="true">👋</span></h1><p>Siap memulai hari yang produktif?</p></div>
      <div className="home-date-picker">▣ <span>{formatLongDate(currentTime)}</span></div>
    </header>

    <div className="home-primary-grid">
      <article className="home-card attendance-card">
        <div className="home-card-head"><div><span className="home-icon red">◷</span><h2>{isEmployee?"Kehadiran hari ini":"Kehadiran tim hari ini"}</h2></div><span className="home-time"><i/>{checkedIn?time(attendance!.checked_in_at):"09:00 WIB"}</span></div>
        <div className="attendance-summary"><div><b className={checkedIn?"attendance-ok":"attendance-pending"}>{isEmployee?attendanceLabel:`${data.present} dari ${data.headcount} hadir`}</b><dl><div><dt>◷ Shift</dt><dd>09.00 – 18.00 WIB</dd></div><div><dt>⌂ Lokasi kerja</dt><dd>{officeName}</dd></div><div><dt>⌖ Lokasi</dt><dd>{checkedIn?"Terverifikasi saat check-in":"Diverifikasi saat check-in"}</dd></div></dl></div><Clock/></div>
        <Link className="home-primary-button" href="/app/attendance/today">◉ {checkedIn?"Buka presensi":"Mulai check-in"}</Link>
      </article>

      <article className="home-card agenda-card">
        <div className="home-card-head"><div><span className="home-icon red">□</span><h2>Agenda hari ini</h2></div><Link className="home-outline-button" href="/app/attendance/today">＋ Tambah agenda</Link></div>
        <div className="agenda-progress"><div><span>{data.agenda_completed} dari {data.agenda_total} selesai</span><b>{progress}%</b></div><i><em style={{width:`${progress}%`}}/></i></div>
        <div className="agenda-list">{data.agenda_total?<><AgendaRow title="Agenda kerja hari ini" detail="Prioritas dicatat saat check-in" index={1}/><AgendaRow title={`${data.agenda_total-data.agenda_completed} agenda perlu ditindaklanjuti`} detail="Perbarui status dari halaman presensi" index={2}/></>:<div className="agenda-empty"><span>＋</span><b>Belum ada agenda</b><p>Tambahkan prioritas saat memulai check-in.</p></div>}</div>
      </article>
    </div>

    <div className="home-secondary-grid">
      <SummaryCard icon="☘" tone="green" label="Sisa cuti" value={`${leave?.balance.remaining_days??"—"} hari`} detail="Tahun ini" action="Lihat saldo" href="/app/time/time-off"/>
      <SummaryCard icon="▧" tone="blue" label="Permohonan" value={requestLabel} detail="Ajukan cuti atau izin jika diperlukan" action="Ajukan cuti atau izin" href="/app/time/time-off"/>
      <SummaryCard icon="▤" tone="purple" label="Slip gaji terbaru" value={payslip?formatPeriod(payslip.period):"Belum ada slip"} detail={payslip?`Diterbitkan ${formatShortDate(payslip.published_at)}`:"Slip akan tampil setelah dipublikasikan"} action="Lihat slip gaji" href="/app/payroll/payslips"/>
    </div>

    <div className={checkedIn?"home-status checked":"home-status"}><b>{checkedIn?"✓ Sudah check-in":"ⓘ Belum check-in"}</b><span>{checkedIn?"Presensi aktif untuk hari ini.":"Agenda dapat diperbarui setelah check-in."}</span></div>
  </section>;
}

function AgendaRow({title,detail,index}:{title:string;detail:string;index:number}){return <div className="agenda-row"><span className="agenda-check"/><div><b>{title}</b><small>{detail}</small></div><time>{index===1?"Hari ini":"Selanjutnya"}</time></div>}
function SummaryCard({icon,tone,label,value,detail,action,href}:{icon:string;tone:string;label:string;value:string;detail:string;action:string;href:string}){return <article className="home-summary-card"><span className={`summary-icon ${tone}`}>{icon}</span><div><p>{label}</p><b>{value}</b><small>{detail}</small></div><Link href={href} className="summary-action">{action}</Link></article>}
function Clock(){return <div className="home-clock" aria-hidden="true"><i/><b/></div>}
function HomeLoading(){return <section className="home-page home-loading"><div/><div/><div/></section>}
function now(){return new Date()}
function time(value:string){return new Date(value).toLocaleTimeString("id-ID",{hour:"2-digit",minute:"2-digit"})+" WIB"}
function formatLongDate(value:Date){return new Intl.DateTimeFormat("id-ID",{weekday:"long",day:"numeric",month:"long",year:"numeric"}).format(value)}
function formatShortDate(value:string){return new Intl.DateTimeFormat("id-ID",{day:"numeric",month:"long",year:"numeric"}).format(new Date(value))}
function formatPeriod(value:string){return new Intl.DateTimeFormat("id-ID",{month:"long",year:"numeric"}).format(new Date(`${value}-01T00:00:00`))}
function leaveStatus(value:string){return ({pending:"Menunggu persetujuan",approved:"Cuti disetujui",rejected:"Permohonan ditolak",revision_requested:"Perlu revisi",cancelled:"Permohonan dibatalkan"} as Record<string,string>)[value]||value}
