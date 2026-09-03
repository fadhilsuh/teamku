"use client";

import {useEffect,useRef,useState} from "react";
import {Shell} from "../../../../components/Shell";
import {Icon} from "../../../../components/Icon";
import {api} from "../../../../lib/api";

type AttendanceState={state:"not_checked_in"|"checked_in"|"completed";session:null|{id:string;checked_in_at:string;checked_out_at:string|null;anomaly:string|null;agenda_count:number;summary:string|null}};

export default function Today(){
  const [attendance,setAttendance]=useState<AttendanceState>();
  const [message,setMessage]=useState("");
  const [error,setError]=useState("");
  const [summary,setSummary]=useState("");
  const [busy,setBusy]=useState(false);
  const video=useRef<HTMLVideoElement>(null);
  const token=()=>localStorage.getItem("movon_user")||undefined;
  const load=()=>api<AttendanceState>("/attendance/today",{},token()).then(setAttendance).catch(e=>setError(e.message));
  useEffect(()=>{load()},[]);

  async function checkin(){
    setBusy(true);setError("");setMessage("");
    let stream:MediaStream|undefined;
    try{
      stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:"user"}});
      if(video.current){video.current.srcObject=stream;await video.current.play()}
      const position=await new Promise<GeolocationPosition>((resolve,reject)=>navigator.geolocation.getCurrentPosition(resolve,reject,{enableHighAccuracy:true,timeout:15000,maximumAge:0}));
      const result=await api<{checked_in_at:string;anomaly:string|null}>("/attendance/check-in",{method:"POST",headers:{"Idempotency-Key":crypto.randomUUID()},body:JSON.stringify({latitude:position.coords.latitude,longitude:position.coords.longitude,accuracy_meters:position.coords.accuracy,selfie_captured:true,agenda:[{title:"Menyelesaikan prioritas hari ini",priority:"high"}]})},token());
      setMessage(`Check-in berhasil pukul ${new Date(result.checked_in_at).toLocaleTimeString("id-ID",{hour:"2-digit",minute:"2-digit"})}.`);
      await load();
    }catch(reason){
      if(reason instanceof GeolocationPositionError)setError(reason.code===1?"Izin lokasi ditolak. Aktifkan akses lokasi browser lalu coba kembali.":"Lokasi tidak berhasil diperoleh. Periksa GPS atau koneksi, lalu coba kembali.");
      else setError(reason instanceof Error?reason.message:"Kamera tidak tersedia. Periksa izin browser lalu coba kembali.");
    }finally{stream?.getTracks().forEach(track=>track.stop());setBusy(false)}
  }

  async function checkout(){
    if(summary.trim().length<4){setError("Tuliskan ringkasan pencapaian minimal 4 karakter sebelum check-out.");return}
    setBusy(true);setError("");
    try{const result=await api<{effective_hours:number}>("/attendance/check-out",{method:"POST",body:JSON.stringify({summary})},token());setMessage(`Check-out berhasil. Durasi kerja efektif ${result.effective_hours} jam.`);await load()}catch(reason){setError(reason instanceof Error?reason.message:"Check-out gagal.")}finally{setBusy(false)}
  }

  return <Shell><section className="page-heading attendance-heading"><div><p className="eyebrow">Attendance</p><h1>Presensi hari ini</h1><p>Rabu, 03 September 2026 · Shift Reguler 09.00-18.00 WIB</p></div><span className={`attendance-state ${attendance?.state||"loading"}`}><i/>{attendance?.state==="checked_in"?"Sedang bekerja":attendance?.state==="completed"?"Hari kerja selesai":"Belum check-in"}</span></section><div className="privacy-note"><Icon name="pin"/><div><b>Verifikasi yang transparan</b><p>Kamera dan lokasi digunakan hanya untuk bukti kehadiran sesuai kebijakan retensi perusahaan.</p></div></div>{error&&<div className="attendance-alert error"><b>Tidak dapat melanjutkan</b><span>{error}</span></div>}{message&&<div className="attendance-alert success"><b>Berhasil</b><span>{message}</span></div>}<section className="attendance-layout"><article className="panel check-card"><div className="camera-shell"><video ref={video} muted playsInline/><div className="camera-placeholder"><span><Icon name="users" size={28}/></span><b>{attendance?.state==="checked_in"?"Anda sudah check-in":"Siapkan wajah Anda"}</b><p>{attendance?.state==="checked_in"?"Tidak perlu mengambil selfie kembali.":"Pastikan wajah terlihat jelas dan pencahayaan cukup."}</p></div><div className="camera-corners"><i/><i/><i/><i/></div></div>{!attendance&&<button className="check-action" disabled>Memuat status presensi…</button>}{attendance?.state==="not_checked_in"&&<button className="check-action" disabled={busy} onClick={checkin}><Icon name="clock"/>{busy?"Memverifikasi kamera & lokasi…":"Ambil selfie & check-in"}</button>}{attendance?.state==="checked_in"&&<div className="active-session"><div><span>Check-in</span><b>{new Date(attendance.session!.checked_in_at).toLocaleTimeString("id-ID",{hour:"2-digit",minute:"2-digit"})} WIB</b></div><div><span>Agenda</span><b>{attendance.session!.agenda_count} item</b></div><div><span>Lokasi</span><b>{attendance.session!.anomaly?"Perlu ditinjau":"Terverifikasi"}</b></div></div>}{attendance?.state==="completed"&&<div className="completed-session"><span><Icon name="check"/></span><div><b>Presensi hari ini selesai</b><p>Check-out pukul {new Date(attendance.session!.checked_out_at!).toLocaleTimeString("id-ID",{hour:"2-digit",minute:"2-digit"})} WIB.</p></div></div>}</article><aside className="panel attendance-summary"><p className="eyebrow">Today&apos;s flow</p><h2>Alur kerja Anda</h2><ol className="flow-list"><li className={attendance?"done":"active"}><span>1</span><div><b>Verifikasi presensi</b><small>Selfie kamera & lokasi kerja</small></div></li><li className={attendance?.state==="checked_in"?"active":attendance?.state==="completed"?"done":""}><span>2</span><div><b>Jalankan agenda</b><small>Catat prioritas dan progres</small></div></li><li className={attendance?.state==="completed"?"done":""}><span>3</span><div><b>Ringkas & check-out</b><small>Tutup hari dengan hasil kerja</small></div></li></ol>{attendance?.state==="checked_in"&&<div className="checkout-form"><label>Ringkasan pencapaian<textarea value={summary} onChange={event=>setSummary(event.target.value)} placeholder="Apa yang berhasil Anda selesaikan hari ini?" rows={5}/></label><button className="checkout-button" disabled={busy} onClick={checkout}>{busy?"Memproses…":"Check-out sekarang"}</button></div>}<div className="location-policy"><Icon name="pin"/><span><b>Lokasi kerja</b><small>Jakarta HQ · radius 300 m</small></span></div></aside></section></Shell>;
}
