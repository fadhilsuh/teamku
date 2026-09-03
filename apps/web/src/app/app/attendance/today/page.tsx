"use client";

import {useEffect,useRef,useState} from "react";
import {Shell} from "../../../../components/Shell";
import {Icon} from "../../../../components/Icon";
import {api} from "../../../../lib/api";

type AttendanceState={state:"not_checked_in"|"checked_in"|"completed";session:null|{id:string;checked_in_at:string;checked_out_at:string|null;anomaly:string|null;agenda_count:number;summary:string|null}};
type CameraState="idle"|"previewing"|"captured";

export default function Today(){
  const [attendance,setAttendance]=useState<AttendanceState>();
  const [message,setMessage]=useState("");
  const [error,setError]=useState("");
  const [summary,setSummary]=useState("");
  const [agendaTitle,setAgendaTitle]=useState("");
  const [busy,setBusy]=useState(false);
  const [cameraState,setCameraState]=useState<CameraState>("idle");
  const [selfiePreview,setSelfiePreview]=useState("");
  const [locationShareApproved,setLocationShareApproved]=useState(false);
  const video=useRef<HTMLVideoElement>(null);
  const cameraStream=useRef<MediaStream|null>(null);
  const token=()=>localStorage.getItem("movon_user")||undefined;
  const load=()=>api<AttendanceState>("/attendance/today",{},token()).then(setAttendance).catch(e=>setError(e.message));

  function stopCamera(){
    cameraStream.current?.getTracks().forEach(track=>track.stop());
    cameraStream.current=null;
    if(video.current)video.current.srcObject=null;
  }

  useEffect(()=>{load();return()=>stopCamera()},[]);

  async function startCamera(){
    setError("");setMessage("");setSelfiePreview("");setLocationShareApproved(false);stopCamera();
    try{
      const stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:"user"},audio:false});
      cameraStream.current=stream;
      setCameraState("previewing");
      if(video.current){video.current.srcObject=stream;await video.current.play()}
    }catch(reason){
      setCameraState("idle");
      setError(reason instanceof Error?`Kamera tidak dapat dibuka. ${reason.message}`:"Kamera tidak tersedia. Periksa izin browser lalu coba kembali.");
    }
  }

  function captureSelfie(){
    const camera=video.current;
    if(!camera||!camera.videoWidth||!camera.videoHeight){setError("Kamera belum siap. Tunggu sebentar lalu ambil foto kembali.");return}
    const canvas=document.createElement("canvas");
    canvas.width=camera.videoWidth;canvas.height=camera.videoHeight;
    canvas.getContext("2d")?.drawImage(camera,0,0,canvas.width,canvas.height);
    setSelfiePreview(canvas.toDataURL("image/jpeg",0.85));
    stopCamera();
    setCameraState("captured");
  }

  function cancelCamera(){
    stopCamera();setSelfiePreview("");setCameraState("idle");setError("");
  }

  async function confirmCheckin(){
    if(cameraState!=="captured"){setError("Ambil selfie terlebih dahulu sebelum mengonfirmasi check-in.");return}
    if(agendaTitle.trim().length<3){setError("Tuliskan satu prioritas kerja sebelum check-in.");return}
    if(!locationShareApproved){setError("Setujui berbagi lokasi untuk menyelesaikan check-in.");return}
    setBusy(true);setError("");setMessage("");
    try{
      const position=await new Promise<GeolocationPosition>((resolve,reject)=>navigator.geolocation.getCurrentPosition(resolve,reject,{enableHighAccuracy:true,timeout:15000,maximumAge:0}));
      const result=await api<{checked_in_at:string;anomaly:string|null}>("/attendance/check-in",{method:"POST",headers:{"Idempotency-Key":crypto.randomUUID()},body:JSON.stringify({latitude:position.coords.latitude,longitude:position.coords.longitude,accuracy_meters:position.coords.accuracy,selfie_captured:true,location_share_approved:true,agenda:[{title:agendaTitle.trim(),priority:"high",status:"planned"}]})},token());
      setMessage(`Check-in berhasil pukul ${new Date(result.checked_in_at).toLocaleTimeString("id-ID",{hour:"2-digit",minute:"2-digit"})}.`);
      await load();
    }catch(reason){
      if(reason instanceof GeolocationPositionError)setError(reason.code===1?"Izin lokasi ditolak. Aktifkan akses lokasi browser lalu coba kembali.":"Lokasi tidak berhasil diperoleh. Periksa GPS atau koneksi, lalu coba kembali.");
      else setError(reason instanceof Error?reason.message:"Check-in gagal. Coba kembali.");
    }finally{setBusy(false)}
  }

  async function checkout(){
    if(summary.trim().length<4){setError("Tuliskan ringkasan pencapaian minimal 4 karakter sebelum check-out.");return}
    setBusy(true);setError("");
    try{const result=await api<{effective_hours:number}>("/attendance/check-out",{method:"POST",body:JSON.stringify({summary})},token());setMessage(`Check-out berhasil. Durasi kerja efektif ${result.effective_hours} jam.`);await load()}catch(reason){setError(reason instanceof Error?reason.message:"Check-out gagal.")}finally{setBusy(false)}
  }

  const notCheckedIn=attendance?.state==="not_checked_in";
  return <Shell><section className="page-heading attendance-heading"><div><p className="eyebrow">Attendance</p><h1>Presensi hari ini</h1><p>{new Intl.DateTimeFormat("id-ID",{weekday:"long",day:"2-digit",month:"long",year:"numeric"}).format(new Date())} · Shift Reguler 09.00-18.00 WIB</p></div><span className={`attendance-state ${attendance?.state||"loading"}`}><i/>{attendance?.state==="checked_in"?"Sedang bekerja":attendance?.state==="completed"?"Hari kerja selesai":"Belum check-in"}</span></section><div className="privacy-note"><Icon name="pin"/><div><b>Verifikasi yang transparan</b><p>Kamera dan lokasi digunakan hanya untuk bukti kehadiran sesuai kebijakan retensi perusahaan.</p></div></div>{error&&<div className="attendance-alert error"><b>Tidak dapat melanjutkan</b><span>{error}</span></div>}{message&&<div className="attendance-alert success"><b>Berhasil</b><span>{message}</span></div>}<section className="attendance-layout"><article className="panel check-card"><div className={`camera-shell ${cameraState}`}>{cameraState==="captured"&&selfiePreview?<img className="selfie-preview" src={selfiePreview} alt="Preview selfie untuk check-in"/>:<video ref={video} muted playsInline/>}{cameraState==="idle"&&<div className="camera-placeholder"><span><Icon name="users" size={28}/></span><b>{attendance?.state==="checked_in"?"Anda sudah check-in":"Siapkan wajah Anda"}</b><p>{attendance?.state==="checked_in"?"Tidak perlu mengambil selfie kembali.":"Buka kamera, ambil foto, lalu konfirmasi check-in."}</p></div>}{cameraState==="previewing"&&<div className="camera-guidance"><b>Posisikan wajah di dalam bingkai</b><span>Foto belum disimpan</span></div>}<div className="camera-corners"><i/><i/><i/><i/></div></div>{notCheckedIn&&<label className="agenda-input">Prioritas utama hari ini<input value={agendaTitle} onChange={event=>setAgendaTitle(event.target.value)} placeholder="Contoh: Selesaikan desain dashboard"/></label>}{!attendance&&<button className="check-action" disabled>Memuat status presensi…</button>}{cameraState==="captured"&&notCheckedIn&&<label className="location-consent"><input type="checkbox" checked={locationShareApproved} onChange={event=>setLocationShareApproved(event.target.checked)}/><span><b>Saya setuju membagikan lokasi untuk check-in ini</b><small>Lokasi hanya diambil satu kali saat check-in, bukan dilacak secara real-time.</small></span></label>}{notCheckedIn&&<div className="camera-actions">{cameraState==="idle"&&<button className="check-action" disabled={busy} onClick={startCamera}><Icon name="users"/>Buka kamera</button>}{cameraState==="previewing"&&<><button className="camera-secondary" disabled={busy} onClick={cancelCamera}>Batalkan</button><button className="check-action" disabled={busy} onClick={captureSelfie}>Ambil foto</button></>}{cameraState==="captured"&&<><button className="camera-secondary" disabled={busy} onClick={startCamera}>Ulangi foto</button><button className="check-action" disabled={busy||!locationShareApproved} onClick={confirmCheckin}><Icon name="check"/>{busy?"Mengonfirmasi check-in…":"Setujui & konfirmasi check-in"}</button></>}</div>}{cameraState==="captured"&&notCheckedIn&&<p className="selfie-ready"><Icon name="check"/>Selfie siap. Check-in belum disimpan sampai Anda menekan Konfirmasi check-in.</p>}{attendance?.state==="checked_in"&&<div className="active-session"><div><span>Check-in</span><b>{new Date(attendance.session!.checked_in_at).toLocaleTimeString("id-ID",{hour:"2-digit",minute:"2-digit"})} WIB</b></div><div><span>Agenda</span><b>{attendance.session!.agenda_count} item</b></div><div><span>Lokasi</span><b>{attendance.session!.anomaly?"Perlu ditinjau":"Terverifikasi"}</b></div></div>}{attendance?.state==="completed"&&<div className="completed-session"><span><Icon name="check"/></span><div><b>Presensi hari ini selesai</b><p>Check-out pukul {new Date(attendance.session!.checked_out_at!).toLocaleTimeString("id-ID",{hour:"2-digit",minute:"2-digit"})} WIB.</p></div></div>}</article><aside className="panel attendance-summary"><p className="eyebrow">Today&apos;s flow</p><h2>Alur kerja Anda</h2><ol className="flow-list"><li className={attendance?"done":"active"}><span>1</span><div><b>Verifikasi presensi</b><small>Selfie kamera & lokasi kerja</small></div></li><li className={attendance?.state==="checked_in"?"active":attendance?.state==="completed"?"done":""}><span>2</span><div><b>Jalankan agenda</b><small>Catat prioritas dan progres</small></div></li><li className={attendance?.state==="completed"?"done":""}><span>3</span><div><b>Ringkas & check-out</b><small>Tutup hari dengan hasil kerja</small></div></li></ol>{attendance?.state==="checked_in"&&<div className="checkout-form"><label>Ringkasan pencapaian<textarea value={summary} onChange={event=>setSummary(event.target.value)} placeholder="Apa yang berhasil Anda selesaikan hari ini?" rows={5}/></label><button className="checkout-button" disabled={busy} onClick={checkout}>{busy?"Memproses…":"Check-out sekarang"}</button></div>}<div className="location-policy"><Icon name="pin"/><span><b>Lokasi kerja</b><small>Jakarta HQ · radius 300 m</small></span></div></aside></section></Shell>;
}
