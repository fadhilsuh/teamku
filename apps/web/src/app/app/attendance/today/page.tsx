"use client";

import {useEffect,useRef,useState} from "react";
import {Icon} from "../../../../components/Icon";
import {NotificationDialog,NotificationDialogState} from "../../../../components/NotificationDialog";
import {api} from "../../../../lib/api";

type AttendanceState={
  state:"not_checked_in"|"checked_in"|"completed";
  session:null|{id:string;checked_in_at:string;checked_out_at:string|null;anomaly:string|null;agenda_count:number;summary:string|null};
  pending_reverification:null|{id:string;due_at:string;kind:string};
  is_remote:boolean;
};
type CameraState="idle"|"previewing"|"captured";
type OfficeSettings={name:string;latitude:number;longitude:number;radius_meters:number};

export default function Today(){
  const [attendance,setAttendance]=useState<AttendanceState>();
  const [office,setOffice]=useState<OfficeSettings>({name:"Jakarta HQ",latitude:-6.2,longitude:106.8166,radius_meters:300});
  const [notification,setNotification]=useState<NotificationDialogState|null>(null);
  const [summary,setSummary]=useState("");
  const [agendaTitle,setAgendaTitle]=useState("");
  const [busy,setBusy]=useState(false);
  const [cameraState,setCameraState]=useState<CameraState>("idle");
  const [selfiePreview,setSelfiePreview]=useState("");
  const [locationShareApproved,setLocationShareApproved]=useState(false);
  const [reverifyOpen,setReverifyOpen]=useState(true);
  const [reverifyBusy,setReverifyBusy]=useState(false);
  const video=useRef<HTMLVideoElement>(null);
  const cameraStream=useRef<MediaStream|null>(null);
  const lastPendingId=useRef<string|null>(null);
  const token=()=>localStorage.getItem("movon_user")||undefined;

  function notify(type:NotificationDialogState["type"],title:string,message:string){setNotification({type,title,message})}

  const load=()=>Promise.all([
    api<AttendanceState>("/attendance/today",{},token()),
    api<OfficeSettings>("/settings/office",{},token()),
  ]).then(([today,officeSettings])=>{setAttendance(today);setOffice(officeSettings)}).catch(e=>notify("error","Tidak dapat melanjutkan",e.message));

  function stopCamera(){
    cameraStream.current?.getTracks().forEach(track=>track.stop());
    cameraStream.current=null;
    if(video.current)video.current.srcObject=null;
  }

  useEffect(()=>{
    load();
    const timer=window.setInterval(()=>{load()},60_000);
    return()=>{window.clearInterval(timer);stopCamera()};
  },[]);

  useEffect(()=>{
    const pendingId=attendance?.pending_reverification?.id||null;
    if(pendingId&&pendingId!==lastPendingId.current){
      setReverifyOpen(true);
      lastPendingId.current=pendingId;
    }
    if(!pendingId)lastPendingId.current=null;
  },[attendance?.pending_reverification?.id]);

  async function startCamera(){
    setSelfiePreview("");setLocationShareApproved(false);stopCamera();
    try{
      const stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:"user"},audio:false});
      cameraStream.current=stream;
      setCameraState("previewing");
      if(video.current){video.current.srcObject=stream;await video.current.play()}
    }catch(reason){
      setCameraState("idle");
      notify("error","Kamera gagal dibuka",reason instanceof Error?reason.message:"Kamera tidak tersedia. Periksa izin browser lalu coba kembali.");
    }
  }

  function captureSelfie(){
    const camera=video.current;
    if(!camera||!camera.videoWidth||!camera.videoHeight){notify("error","Kamera belum siap","Tunggu sebentar lalu ambil foto kembali.");return}
    const canvas=document.createElement("canvas");
    canvas.width=camera.videoWidth;canvas.height=camera.videoHeight;
    canvas.getContext("2d")?.drawImage(camera,0,0,canvas.width,canvas.height);
    setSelfiePreview(canvas.toDataURL("image/jpeg",0.85));
    stopCamera();
    setCameraState("captured");
  }

  function cancelCamera(){
    stopCamera();setSelfiePreview("");setCameraState("idle");
  }

  async function confirmCheckin(){
    if(cameraState!=="captured"){notify("error","Check-in belum siap","Ambil selfie terlebih dahulu sebelum mengonfirmasi check-in.");return}
    if(agendaTitle.trim().length<3){notify("error","Prioritas belum diisi","Tuliskan satu prioritas kerja sebelum check-in.");return}
    if(!locationShareApproved){notify("error","Lokasi belum disetujui","Setujui berbagi lokasi untuk menyelesaikan check-in.");return}
    setBusy(true);
    try{
      const position=await new Promise<GeolocationPosition>((resolve,reject)=>navigator.geolocation.getCurrentPosition(resolve,reject,{enableHighAccuracy:true,timeout:15000,maximumAge:0}));
      const result=await api<{checked_in_at:string;anomaly:string|null}>("/attendance/check-in",{method:"POST",headers:{"Idempotency-Key":crypto.randomUUID()},body:JSON.stringify({latitude:position.coords.latitude,longitude:position.coords.longitude,accuracy_meters:position.coords.accuracy,selfie_captured:true,location_share_approved:true,agenda:[{title:agendaTitle.trim(),priority:"high",status:"planned"}]})},token());
      notify("success","Check-in berhasil",`Presensi tercatat pukul ${new Date(result.checked_in_at).toLocaleTimeString("id-ID",{hour:"2-digit",minute:"2-digit"})}.`);
      setCameraState("idle");setSelfiePreview("");setLocationShareApproved(false);
      await load();
    }catch(reason){
      const geoCode=reason&&typeof reason==="object"&&"code" in reason?Number((reason as {code?:number}).code):NaN;
      if(geoCode===1)notify("error","Lokasi gagal diambil","Izin lokasi ditolak. Aktifkan akses lokasi browser lalu coba kembali.");
      else if(geoCode===2||geoCode===3)notify("error","Lokasi gagal diambil","Lokasi tidak berhasil diperoleh. Periksa GPS atau koneksi, lalu coba kembali.");
      else{
        const message=reason instanceof Error?reason.message:"Check-in gagal. Coba kembali.";
        notify("error",/radius|kantor|ditolak/i.test(message)?"Di luar area kantor":"Check-in gagal",message);
      }
    }finally{setBusy(false)}
  }

  async function submitReverify(){
    if(attendance&&!attendance.is_remote&&cameraState!=="captured"){
      notify("error","Re-verifikasi belum siap","Ambil selfie terlebih dahulu sebelum mengirim lokasi.");
      return;
    }
    setReverifyBusy(true);
    try{
      const position=await new Promise<GeolocationPosition>((resolve,reject)=>navigator.geolocation.getCurrentPosition(resolve,reject,{enableHighAccuracy:true,timeout:15000,maximumAge:0}));
      await api("/attendance/reverify",{
        method:"POST",
        body:JSON.stringify({
          latitude:position.coords.latitude,
          longitude:position.coords.longitude,
          accuracy_meters:position.coords.accuracy,
          selfie_captured:attendance?.is_remote?true:cameraState==="captured",
        }),
      },token());
      notify("success","Lokasi tercatat","Re-verifikasi lokasi berhasil dikirim.");
      setReverifyOpen(false);
      setCameraState("idle");
      setSelfiePreview("");
      await load();
    }catch(reason){
      const geoCode=reason&&typeof reason==="object"&&"code" in reason?Number((reason as {code?:number}).code):NaN;
      if(geoCode===1)notify("error","Lokasi gagal diambil","Izin lokasi ditolak. Aktifkan akses lokasi browser lalu coba kembali.");
      else notify("error","Re-verifikasi gagal",reason instanceof Error?reason.message:"Re-verifikasi gagal. Coba kembali.");
    }finally{setReverifyBusy(false)}
  }

  async function checkout(){
    if(summary.trim().length<4){notify("error","Ringkasan belum lengkap","Tuliskan ringkasan pencapaian minimal 4 karakter sebelum check-out.");return}
    setBusy(true);
    try{
      const result=await api<{effective_hours:number}>("/attendance/check-out",{method:"POST",body:JSON.stringify({summary})},token());
      notify("success","Check-out berhasil",`Durasi kerja efektif ${result.effective_hours} jam.`);
      await load();
    }catch(reason){
      notify("error","Check-out gagal",reason instanceof Error?reason.message:"Check-out gagal.");
    }finally{setBusy(false)}
  }

  const notCheckedIn=attendance?.state==="not_checked_in";
  const pendingReverify=attendance?.state==="checked_in"&&attendance.pending_reverification;
  const isRemote=Boolean(attendance?.is_remote);

  return <>
    <NotificationDialog notification={notification} onClose={()=>setNotification(null)}/>

    <section className="page-heading attendance-heading">
      <div>
        <p className="eyebrow">Attendance</p>
        <h1>Presensi hari ini</h1>
        <p>{new Intl.DateTimeFormat("id-ID",{weekday:"long",day:"2-digit",month:"long",year:"numeric"}).format(new Date())} · Shift Reguler 09.00-18.00 WIB</p>
      </div>
      <span className={`attendance-state ${attendance?.state||"loading"}`}>
        <i/>
        {attendance?.state==="checked_in"?"Sedang bekerja":attendance?.state==="completed"?"Hari kerja selesai":"Belum check-in"}
      </span>
    </section>

    <div className="privacy-note">
      <Icon name="pin"/>
      <div>
        <b>Verifikasi yang transparan</b>
        <p>{isRemote?"Pekerja remote bebas lokasi. Kamera tetap dipakai untuk konfirmasi check-in.":"Kamera dan lokasi wajib untuk check-in. Presensi kantor hanya diterima jika Anda berada dalam radius kantor."}</p>
      </div>
    </div>

    <section className="attendance-layout">
      <article className="panel check-card">
        <div className={`camera-shell ${cameraState}`}>
          {cameraState==="captured"&&selfiePreview
            ? <img className="selfie-preview" src={selfiePreview} alt="Preview selfie untuk check-in"/>
            : <video ref={video} muted playsInline/>}
          {cameraState==="idle"&&(
            <div className="camera-placeholder">
              <span><Icon name="users" size={28}/></span>
              <b>{attendance?.state==="checked_in"?"Anda sudah check-in":"Siapkan wajah Anda"}</b>
              <p>{attendance?.state==="checked_in"?"Tidak perlu mengambil selfie kembali.":"Buka kamera, ambil foto, lalu konfirmasi check-in."}</p>
            </div>
          )}
          {cameraState==="previewing"&&(
            <div className="camera-guidance">
              <b>Posisikan wajah di dalam bingkai</b>
              <span>Foto belum disimpan</span>
            </div>
          )}
          <div className="camera-corners"><i/><i/><i/><i/></div>
        </div>

        {notCheckedIn&&(
          <div className="check-form">
            <label className="agenda-input">
              <span>Prioritas utama hari ini</span>
              <input value={agendaTitle} onChange={event=>setAgendaTitle(event.target.value)} placeholder="Contoh: Selesaikan desain dashboard"/>
            </label>

            {cameraState==="captured"&&(
              <>
                <label className={`location-consent ${locationShareApproved?"approved":""}`}>
                  <input type="checkbox" checked={locationShareApproved} onChange={event=>setLocationShareApproved(event.target.checked)}/>
                  <span>
                    <b>Saya setuju membagikan lokasi untuk check-in ini</b>
                    <small>{isRemote?`Lokasi dicatat untuk ${office.name}, tanpa penolakan geofence.`:`Lokasi diverifikasi terhadap ${office.name} (radius ${office.radius_meters} m). Check-in dari luar area akan ditolak.`}</small>
                  </span>
                </label>
                <p className="selfie-ready"><Icon name="check"/>Selfie siap. Check-in belum disimpan sampai Anda menekan konfirmasi.</p>
              </>
            )}

            {!attendance&&<button className="check-action" disabled>Memuat status presensi…</button>}

            <div className="camera-actions">
              {cameraState==="idle"&&(
                <button className="check-action" disabled={busy} onClick={startCamera}><Icon name="users"/>Buka kamera</button>
              )}
              {cameraState==="previewing"&&(
                <>
                  <button className="camera-secondary" disabled={busy} onClick={cancelCamera}>Batalkan</button>
                  <button className="check-action" disabled={busy} onClick={captureSelfie}>Ambil foto</button>
                </>
              )}
              {cameraState==="captured"&&(
                <>
                  <button className="camera-secondary" disabled={busy} onClick={startCamera}>Ulangi foto</button>
                  <button className="check-action" disabled={busy||!locationShareApproved} onClick={confirmCheckin}>
                    <Icon name="check"/>{busy?"Mengonfirmasi check-in…":"Setujui & konfirmasi check-in"}
                  </button>
                </>
              )}
            </div>
          </div>
        )}

        {attendance?.state==="checked_in"&&(
          <div className="active-session">
            <div><span>Check-in</span><b>{new Date(attendance.session!.checked_in_at).toLocaleTimeString("id-ID",{hour:"2-digit",minute:"2-digit"})} WIB</b></div>
            <div><span>Agenda</span><b>{attendance.session!.agenda_count} item</b></div>
            <div><span>Lokasi</span><b>{attendance.session!.anomaly?"Perlu ditinjau":"Terverifikasi"}</b></div>
          </div>
        )}

        {attendance?.state==="completed"&&(
          <div className="completed-session">
            <span><Icon name="check"/></span>
            <div>
              <b>Presensi hari ini selesai</b>
              <p>Check-out pukul {new Date(attendance.session!.checked_out_at!).toLocaleTimeString("id-ID",{hour:"2-digit",minute:"2-digit"})} WIB.</p>
            </div>
          </div>
        )}
      </article>

      <aside className="panel attendance-flow">
        <header className="flow-head">
          <p className="eyebrow">Today&apos;s flow</p>
          <h2>Alur kerja Anda</h2>
        </header>
        <ol className="flow-list">
          <li className={!attendance||attendance.state==="not_checked_in"?"active":"done"}><span>1</span><div><b>Verifikasi presensi</b><small>Selfie kamera & lokasi kerja</small></div></li>
          <li className={attendance?.state==="checked_in"?"active":attendance?.state==="completed"?"done":""}><span>2</span><div><b>Jalankan agenda</b><small>Catat prioritas dan progres</small></div></li>
          <li className={attendance?.state==="completed"?"done":""}><span>3</span><div><b>Ringkas & check-out</b><small>Tutup hari dengan hasil kerja</small></div></li>
        </ol>
        <div className="location-policy">
          <Icon name="pin"/>
          <span><b>Lokasi kerja</b><small>{isRemote?`${office.name} · pekerja remote, bebas geofence`:`${office.name} · wajib dalam radius ${office.radius_meters} m`}</small></span>
        </div>
        {attendance?.state==="checked_in"&&(
          <div className="checkout-form">
            <label>Ringkasan pencapaian<textarea value={summary} onChange={event=>setSummary(event.target.value)} placeholder="Apa yang berhasil Anda selesaikan hari ini?" rows={5}/></label>
            <button className="checkout-button" disabled={busy} onClick={checkout}>{busy?"Memproses…":"Check-out sekarang"}</button>
          </div>
        )}
      </aside>
    </section>

    {pendingReverify&&reverifyOpen&&(
      <div className="dialog-backdrop" role="presentation">
        <section className="decision-dialog reverify-dialog" role="dialog" aria-modal="true" aria-labelledby="reverify-title">
          <p className="eyebrow">Re-verifikasi lokasi</p>
          <h2 id="reverify-title">Konfirmasi lokasi Anda</h2>
          <p>Ada permintaan verifikasi lokasi untuk sesi yang sedang berjalan. Ambil lokasi saat ini{isRemote?"":" dan selfie"}.</p>
          {!isRemote&&cameraState!=="captured"&&(
            <div className="camera-actions">
              {cameraState==="idle"&&<button type="button" className="check-action" disabled={reverifyBusy} onClick={startCamera}><Icon name="users"/>Buka kamera</button>}
              {cameraState==="previewing"&&<button type="button" className="check-action" disabled={reverifyBusy} onClick={captureSelfie}>Ambil foto</button>}
            </div>
          )}
          {cameraState==="captured"&&selfiePreview&&<p className="selfie-ready"><Icon name="check"/>Selfie siap dikirim bersama lokasi.</p>}
          <div className="dialog-actions">
            <button type="button" className="secondary-button" disabled={reverifyBusy} onClick={()=>setReverifyOpen(false)}>Tunda sebentar</button>
            <button type="button" className="primary-action auto-width" disabled={reverifyBusy} onClick={submitReverify}>
              {reverifyBusy?"Mengirim…":"Kirim lokasi"}
            </button>
          </div>
        </section>
      </div>
    )}
  </>;
}
