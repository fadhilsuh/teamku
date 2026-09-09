"use client";

import {useEffect,useState} from "react";
import {useRouter} from "next/navigation";
import {Icon} from "../../../components/Icon";
import {NotificationDialog,NotificationDialogState} from "../../../components/NotificationDialog";
import {api} from "../../../lib/api";
import {googleMapsEmbedUrl,googleMapsOpenUrl,isGoogleMapsShortUrl,parseGoogleMapsLocation} from "../../../lib/googleMaps";

type AttendanceSettings={
  name:string;
  latitude:number;
  longitude:number;
  radius_meters:number;
  reverify_enabled:boolean;
  reverify_count_per_day:number;
  reverify_window_start_minutes:number;
  reverify_window_end_minutes:number;
  alerts_enabled:boolean;
  clock_in_reminder_time:string;
  clock_out_reminder_time:string;
  max_open_hours:number;
  alert_managers:boolean;
};
type User={role:string};
type MapsParseResult={latitude:number;longitude:number;resolved_url:string;maps_url:string};
type CalendarSettings={provider:string;connected:boolean;team_calendar_id:string;calendar_name:string;scope:"company"|"division";division:string;delivery_mode:"shared"|"shared_and_email"};
type GoogleCalendar={id:string;name:string;primary:boolean};

const empty:AttendanceSettings={
  name:"Jakarta HQ",
  latitude:-6.2,
  longitude:106.8166,
  radius_meters:300,
  reverify_enabled:false,
  reverify_count_per_day:1,
  reverify_window_start_minutes:60,
  reverify_window_end_minutes:420,
  alerts_enabled:false,
  clock_in_reminder_time:"09:15",
  clock_out_reminder_time:"18:15",
  max_open_hours:10,
  alert_managers:false,
};
const emptyCalendar:CalendarSettings={provider:"google",connected:false,team_calendar_id:"",calendar_name:"",scope:"company",division:"",delivery_mode:"shared_and_email"};

export default function SettingsPage(){
  const router=useRouter();
  const [form,setForm]=useState<AttendanceSettings>(empty);
  const [mapsLink,setMapsLink]=useState("");
  const [busy,setBusy]=useState(false);
  const [loading,setLoading]=useState(true);
  const [notification,setNotification]=useState<NotificationDialogState|null>(null);
  const [calendar,setCalendar]=useState<CalendarSettings>(emptyCalendar);
  const [calendarBusy,setCalendarBusy]=useState(false);
  const [calendarAccount,setCalendarAccount]=useState(false);
  const [calendars,setCalendars]=useState<GoogleCalendar[]>([]);
  const token=()=>localStorage.getItem("movon_user")||undefined;
  const notify=(type:NotificationDialogState["type"],title:string,message:string)=>setNotification({type,title,message});
  const mapsUrl=googleMapsOpenUrl(form.latitude,form.longitude);
  const embedUrl=googleMapsEmbedUrl(form.latitude,form.longitude);

  useEffect(()=>{
    const auth=token();
    Promise.all([
      api<{user:User}>("/me",{},auth),
      api<AttendanceSettings>("/settings/office",{},auth),
      api<CalendarSettings>("/settings/calendar",{},auth),
    ]).then(([profile,office,calendarSettings])=>{
      if(profile.user.role!=="hr_admin"){router.replace("/app/overview");return}
      setForm({...empty,...office});
      setMapsLink(googleMapsOpenUrl(office.latitude,office.longitude));
      setCalendar({...emptyCalendar,...calendarSettings});
      setCalendarAccount(calendarSettings.connected);
      if(calendarSettings.connected) loadGoogleCalendars();
      setLoading(false);
    }).catch(reason=>{
      notify("error","Pengaturan gagal dimuat",reason instanceof Error?reason.message:"Pengaturan gagal dimuat.");
      setLoading(false);
    });
  },[router]);

  async function connectGoogle(){
    setCalendarBusy(true);
    try{
      const result=await api<{authorization_url:string}>("/settings/calendar/google/start",{},token());
      window.location.assign(result.authorization_url);
    }catch(reason){notify("error","Google Calendar belum siap",reason instanceof Error?reason.message:"Google Calendar belum siap.");setCalendarBusy(false)}
  }

  async function loadGoogleCalendars(){
    try{const result=await api<{items:GoogleCalendar[]}>("/settings/calendar/google/calendars",{},token());setCalendars(result.items)}catch(reason){notify("error","Daftar kalender gagal dimuat",reason instanceof Error?reason.message:"Daftar kalender gagal dimuat.")}
  }

  async function saveCalendar(){
    if(!calendarAccount){notify("error","Akun belum terhubung","Hubungkan akun Google atau Microsoft 365 terlebih dahulu.");return}
    if(!calendar.team_calendar_id.trim()){notify("error","Kalender belum dipilih","Muat daftar kalender Google lalu pilih kalender tujuan.");return}
    if(calendar.scope==="division"&&!calendar.division.trim()){notify("error","Divisi belum dipilih","Pilih divisi yang ingin disinkronkan.");return}
    setCalendarBusy(true);
    try{
      const saved=await api<CalendarSettings>("/settings/calendar",{method:"PUT",body:JSON.stringify({...calendar,team_calendar_id:calendar.team_calendar_id.trim(),calendar_name:calendar.calendar_name||"Kalender perusahaan",connected:true})},token());
      setCalendar(saved);
      notify("success","Kalender terhubung","Pengaturan kalender tersimpan. Cuti yang disetujui akan ditandai untuk kalender karyawan dan kalender bersama.");
    }catch(reason){notify("error","Kalender gagal disimpan",reason instanceof Error?reason.message:"Kalender gagal disimpan.")}
    finally{setCalendarBusy(false)}
  }

  async function save(successTitle:string,successMessage:string){
    if(form.name.trim().length<2){notify("error","Nama lokasi belum lengkap","Nama lokasi kantor wajib diisi.");return}
    if(form.reverify_window_end_minutes<=form.reverify_window_start_minutes){
      notify("error","Jendela re-verifikasi tidak valid","Waktu berakhir harus lebih besar dari waktu mulai.");
      return;
    }
    setBusy(true);
    try{
      const saved=await api<AttendanceSettings>("/settings/office",{
        method:"PUT",
        body:JSON.stringify({
          name:form.name.trim(),
          latitude:Number(form.latitude),
          longitude:Number(form.longitude),
          radius_meters:Number(form.radius_meters),
          reverify_enabled:form.reverify_enabled,
          reverify_count_per_day:Number(form.reverify_count_per_day),
          reverify_window_start_minutes:Number(form.reverify_window_start_minutes),
          reverify_window_end_minutes:Number(form.reverify_window_end_minutes),
          alerts_enabled:form.alerts_enabled,
          clock_in_reminder_time:form.clock_in_reminder_time,
          clock_out_reminder_time:form.clock_out_reminder_time,
          max_open_hours:Number(form.max_open_hours),
          alert_managers:form.alert_managers,
        }),
      },token());
      setForm({...empty,...saved});
      setMapsLink(googleMapsOpenUrl(saved.latitude,saved.longitude));
      notify("success",successTitle,successMessage);
    }catch(reason){
      notify("error","Pengaturan gagal disimpan",reason instanceof Error?reason.message:"Pengaturan gagal disimpan.");
    }finally{setBusy(false)}
  }

  function useCurrentLocation(){
    if(!navigator.geolocation){notify("error","Geolokasi tidak tersedia","Browser tidak mendukung geolokasi.");return}
    setBusy(true);
    navigator.geolocation.getCurrentPosition(
      position=>{
        const latitude=Number(position.coords.latitude.toFixed(6));
        const longitude=Number(position.coords.longitude.toFixed(6));
        setForm(current=>({...current,latitude,longitude}));
        setMapsLink(googleMapsOpenUrl(latitude,longitude));
        setBusy(false);
        notify("success","Koordinat diisi","Koordinat diisi dari lokasi perangkat Anda. Simpan untuk menerapkan.");
      },
      reason=>{
        setBusy(false);
        notify("error","Lokasi gagal diambil",reason.code===1?"Izin lokasi ditolak.":"Lokasi saat ini tidak berhasil diambil.");
      },
      {enableHighAccuracy:true,timeout:15000,maximumAge:0},
    );
  }

  async function applyMapsLink(){
    const value=mapsLink.trim();
    if(!value){notify("error","Tautan belum diisi","Tempel tautan Google Maps atau koordinat terlebih dahulu.");return}
    setBusy(true);
    try{
      const local=parseGoogleMapsLocation(value);
      if(local&&!isGoogleMapsShortUrl(value)){
        setForm(current=>({...current,latitude:local.latitude,longitude:local.longitude}));
        setMapsLink(googleMapsOpenUrl(local.latitude,local.longitude));
        notify("success","Koordinat diambil","Koordinat diambil dari tautan Google Maps. Simpan untuk menerapkan.");
        return;
      }
      const parsed=await api<MapsParseResult>("/settings/office/from-maps-url",{
        method:"POST",
        body:JSON.stringify({url:value}),
      },token());
      setForm(current=>({...current,latitude:parsed.latitude,longitude:parsed.longitude}));
      setMapsLink(parsed.maps_url);
      notify("success","Koordinat diambil","Koordinat diambil dari tautan Google Maps. Simpan untuk menerapkan.");
    }catch(reason){
      notify("error","Tautan Google Maps tidak dapat dibaca",reason instanceof Error?reason.message:"Tautan Google Maps tidak dapat dibaca.");
    }finally{setBusy(false)}
  }

  async function copyMapsLink(){
    try{
      await navigator.clipboard.writeText(mapsUrl);
      notify("success","Tautan disalin","Tautan Google Maps disalin ke clipboard.");
    }catch{
      notify("error","Gagal menyalin tautan","Salin manual dari tombol Buka di Google Maps.");
    }
  }

  return <>
    <NotificationDialog notification={notification} onClose={()=>setNotification(null)}/>
    <section className="page-heading">
      <div>
        <p className="eyebrow">Workspace settings</p>
        <h1>Pengaturan</h1>
        <p>Kelola lokasi kantor, re-verifikasi lokasi, dan pengingat kehadiran dari satu tempat.</p>
      </div>
    </section>
    {loading?<div className="panel settings-panel"><p className="muted">Memuat pengaturan…</p></div>:(
      <div className="settings-stack">
        <section className="settings-layout">
          <article className="panel settings-panel">
            <div className="panel-head">
              <div>
                <p className="eyebrow">Office geofence</p>
                <h2>Lokasi kantor</h2>
              </div>
            </div>
            <p className="settings-copy">Hanya HR Admin yang dapat mengubah titik ini. Tempel tautan Share dari Google Maps untuk mengisi koordinat otomatis.</p>

            <div className="maps-import">
              <label className="maps-import-field">
                <span>Tautan Google Maps</span>
                <input
                  value={mapsLink}
                  onChange={event=>setMapsLink(event.target.value)}
                  placeholder="Tempel link Share Google Maps atau -6.2, 106.8166"
                />
              </label>
              <button type="button" className="secondary-button" disabled={busy} onClick={applyMapsLink}>
                <Icon name="pin"/>Ambil koordinat
              </button>
            </div>

            <div className="form-grid settings-form">
              <label>Nama lokasi<input value={form.name} onChange={event=>setForm({...form,name:event.target.value})} placeholder="Contoh: Jakarta HQ"/></label>
              <label>Radius check-in (meter)<input type="number" min={50} max={5000} step={10} value={form.radius_meters} onChange={event=>setForm({...form,radius_meters:Number(event.target.value)})}/></label>
              <label>Latitude<input type="number" step="0.000001" value={form.latitude} onChange={event=>setForm({...form,latitude:Number(event.target.value)})}/></label>
              <label>Longitude<input type="number" step="0.000001" value={form.longitude} onChange={event=>setForm({...form,longitude:Number(event.target.value)})}/></label>
            </div>
            <div className="settings-actions">
              <button type="button" className="secondary-button" disabled={busy} onClick={useCurrentLocation}><Icon name="pin"/>Gunakan lokasi saya</button>
              <button type="button" className="primary-action auto-width" disabled={busy} onClick={()=>save("Lokasi kantor diperbarui","Lokasi kantor berhasil diperbarui. Aturan check-in langsung memakai titik ini.")}>{busy?"Menyimpan…":"Simpan lokasi kantor"}</button>
            </div>
          </article>

          <aside className="panel settings-side">
            <p className="eyebrow">Preview</p>
            <h2>{form.name||"Lokasi kantor"}</h2>
            <div className="maps-frame">
              <iframe title={`Peta ${form.name}`} src={embedUrl} loading="lazy" referrerPolicy="no-referrer-when-downgrade"/>
            </div>
            <dl className="settings-preview">
              <div><dt>Koordinat</dt><dd>{form.latitude}, {form.longitude}</dd></div>
              <div><dt>Radius</dt><dd>{form.radius_meters} m</dd></div>
              <div><dt>Kebijakan</dt><dd>Check-in di luar radius ditolak untuk pekerja kantor</dd></div>
            </dl>
            <div className="settings-actions maps-share-actions">
              <a className="secondary-button" href={mapsUrl} target="_blank" rel="noreferrer">
                <Icon name="pin"/>Buka di Google Maps
              </a>
              <button type="button" className="secondary-button" onClick={copyMapsLink}>Salin tautan</button>
            </div>
            <div className="location-policy settings-policy">
              <Icon name="pin"/>
              <span>
                <b>Berlaku segera</b>
                <small>Perubahan langsung dipakai pada check-in berikutnya.</small>
              </span>
            </div>
          </aside>
        </section>

        <article className="panel settings-panel">
          <div className="panel-head">
            <div>
              <p className="eyebrow">Location monitoring</p>
              <h2>Re-verifikasi lokasi</h2>
            </div>
          </div>
          <p className="settings-copy">Hanya berlaku untuk karyawan kantor. Pekerja remote tidak diminta verifikasi ulang berdasarkan geofence. Sesi yang sudah terbuka tetap memakai jadwal yang dihitung saat check-in.</p>
          <label className={`location-consent ${form.reverify_enabled?"approved":""}`}>
            <input type="checkbox" checked={form.reverify_enabled} onChange={event=>setForm({...form,reverify_enabled:event.target.checked})}/>
            <span>
              <b>Aktifkan re-verifikasi</b>
              <small>Setelah check-in, pekerja kantor diminta memverifikasi lokasi lagi sesuai jadwal.</small>
            </span>
          </label>
          <div className="form-grid settings-form">
            <label>Jumlah per hari
              <select value={form.reverify_count_per_day} onChange={event=>setForm({...form,reverify_count_per_day:Number(event.target.value)})}>
                <option value={1}>1 kali</option>
                <option value={2}>2 kali</option>
                <option value={3}>3 kali</option>
              </select>
            </label>
            <label>Mulai setelah check-in (menit)<input type="number" min={0} max={1440} value={form.reverify_window_start_minutes} onChange={event=>setForm({...form,reverify_window_start_minutes:Number(event.target.value)})}/></label>
            <label>Berakhir setelah check-in (menit)<input type="number" min={1} max={1440} value={form.reverify_window_end_minutes} onChange={event=>setForm({...form,reverify_window_end_minutes:Number(event.target.value)})}/></label>
          </div>
          <div className="settings-actions">
            <button type="button" className="primary-action auto-width" disabled={busy} onClick={()=>save("Re-verifikasi diperbarui","Pengaturan re-verifikasi lokasi tersimpan. Perubahan berlaku untuk check-in berikutnya.")}>{busy?"Menyimpan…":"Simpan re-verifikasi"}</button>
          </div>
        </article>

        <article className="panel settings-panel">
          <div className="panel-head">
            <div>
              <p className="eyebrow">Attendance alerts</p>
              <h2>Notifikasi & alert kehadiran</h2>
            </div>
          </div>
          <p className="settings-copy">Pengingat clock-in/out berlaku untuk remote dan kantor. Alert geofence dan re-verifikasi hanya untuk pekerja kantor. Jam memakai zona waktu Asia/Jakarta.</p>
          <label className={`location-consent ${form.alerts_enabled?"approved":""}`}>
            <input type="checkbox" checked={form.alerts_enabled} onChange={event=>setForm({...form,alerts_enabled:event.target.checked})}/>
            <span>
              <b>Aktifkan pengingat kehadiran</b>
              <small>Sistem mengirim notifikasi in-app saat karyawan lupa clock-in/out atau melewati batas.</small>
            </span>
          </label>
          <div className="form-grid settings-form">
            <label>Reminder clock-in<input type="time" value={form.clock_in_reminder_time} onChange={event=>setForm({...form,clock_in_reminder_time:event.target.value})}/></label>
            <label>Reminder clock-out<input type="time" value={form.clock_out_reminder_time} onChange={event=>setForm({...form,clock_out_reminder_time:event.target.value})}/></label>
            <label>Batas sesi terbuka (jam)<input type="number" min={1} max={24} value={form.max_open_hours} onChange={event=>setForm({...form,max_open_hours:Number(event.target.value)})}/></label>
          </div>
          <label className={`location-consent ${form.alert_managers?"approved":""}`}>
            <input type="checkbox" checked={form.alert_managers} onChange={event=>setForm({...form,alert_managers:event.target.checked})}/>
            <span>
              <b>Kirim juga ke manager/HR</b>
              <small>Manager departemen dan HR Admin menerima salinan alert yang sama.</small>
            </span>
          </label>
          <div className="settings-actions">
            <button type="button" className="primary-action auto-width" disabled={busy} onClick={()=>save("Pengingat kehadiran diperbarui","Pengaturan notifikasi dan alert kehadiran tersimpan.")}>{busy?"Menyimpan…":"Simpan pengingat kehadiran"}</button>
          </div>
        </article>

        <article className="panel settings-panel calendar-settings-card">
          <div className="panel-head"><div><p className="eyebrow">Calendar integration</p><h2>Hubungkan kalender kerja</h2></div><span className={`status ${calendar.connected?"approved":"pending"}`}>{calendar.connected?"Terhubung":"Belum terhubung"}</span></div>
          <p className="settings-copy">Pilih provider kalender perusahaan. Cuti yang disetujui akan dikirim ke kalender karyawan dan kalender bersama tim.</p>
          <div className="calendar-provider-grid" role="radiogroup" aria-label="Pilih provider kalender">
            {[{id:"google",name:"Google Calendar",description:"Google Workspace",color:"google"},{id:"microsoft",name:"Microsoft 365",description:"Outlook & Teams",color:"microsoft"}].map(provider=><button type="button" key={provider.id} className={`provider-option ${calendar.provider===provider.id?"selected":""} ${provider.color}`} onClick={()=>setCalendar({...calendar,provider:provider.id,connected:false})} role="radio" aria-checked={calendar.provider===provider.id}>
              <span className="provider-icon"><Icon name={provider.id as "google"|"microsoft"} size={25}/></span><span className="provider-copy"><b>{provider.name}</b><small>{provider.description}</small></span><span className="provider-check"><Icon name="check" size={14}/></span>
            </button>)}
          </div>
          <div className={`calendar-connect-box ${calendarAccount?"connected":""}`}>
            <div className="calendar-config-heading"><span className="calendar-config-icon"><Icon name={calendar.provider as "google"|"microsoft"} size={19}/></span><div><b>{calendarAccount?`Akun ${calendar.provider==="google"?"Google":"Microsoft 365"} terhubung`:"Hubungkan akun admin"}</b><small>{calendarAccount?"Kalender siap dipilih untuk sinkronisasi":"Teamku hanya membutuhkan izin kalender yang relevan."}</small></div></div>
            <button type="button" className={calendarAccount?"secondary-button":"connect-button"} disabled={calendarBusy} onClick={calendar.provider==="google"?connectGoogle:()=>notify("info","Microsoft 365 segera hadir","Koneksi Microsoft 365 akan menggunakan flow OAuth yang sama setelah kredensial aplikasi dikonfigurasi.")}><Icon name={calendarAccount?"check":"chevron"} size={15}/>{calendarAccount?"Ganti akun":"Hubungkan akun"}</button>
          </div>
          {calendarAccount&&<>
            <div className="calendar-config-box"><div className="calendar-config-heading"><span className="calendar-config-icon"><Icon name="calendar" size={19}/></span><div><b>Kalender tujuan</b><small>Pilih kalender yang menerima event cuti.</small></div></div>{calendar.provider==="google"&&!calendars.length?<button type="button" className="secondary-button" onClick={loadGoogleCalendars}>Muat daftar kalender Google</button>:calendars.length?<div className="calendar-list">{calendars.map(item=><button type="button" key={item.id} className={`calendar-choice ${calendar.team_calendar_id===item.id?"selected":""}`} onClick={()=>setCalendar({...calendar,team_calendar_id:item.id,calendar_name:item.name,connected:false})}><span className="calendar-dot"/><span><b>{item.name}</b><small>{item.primary?"Kalender utama":"Kalender bersama"}</small></span>{calendar.team_calendar_id===item.id&&<Icon name="check" size={16}/>}</button>)}</div>:<button type="button" className="calendar-choice selected"><span className="calendar-dot"/><span><b>{calendar.calendar_name||"Kalender perusahaan"}</b><small>{calendar.provider==="google"?"Google Calendar":"Microsoft 365 Calendar"}</small></span><Icon name="check" size={16}/></button>}</div>
            <div className="scope-box"><b>Siapa yang disinkronkan?</b><div className="scope-grid"><label className={calendar.scope==="company"?"active":""}><input type="radio" checked={calendar.scope==="company"} onChange={()=>setCalendar({...calendar,scope:"company"})}/>Seluruh perusahaan<small>Semua divisi</small></label><label className={calendar.scope==="division"?"active":""}><input type="radio" checked={calendar.scope==="division"} onChange={()=>setCalendar({...calendar,scope:"division"})}/>Satu divisi<small>Hanya tim tertentu</small></label></div>{calendar.scope==="division"&&<input value={calendar.division} onChange={event=>setCalendar({...calendar,division:event.target.value})} placeholder="Contoh: Engineering"/>}</div>
            <div className="delivery-box"><b>Bagaimana event dibagikan?</b><label><input type="radio" checked={calendar.delivery_mode==="shared_and_email"} onChange={()=>setCalendar({...calendar,delivery_mode:"shared_and_email"})}/>Kalender bersama + email invitation <small>Rekomendasi untuk semua karyawan</small></label><label><input type="radio" checked={calendar.delivery_mode==="shared"} onChange={()=>setCalendar({...calendar,delivery_mode:"shared"})}/>Kalender bersama saja</label></div>
          </>}
          <div className="calendar-privacy"><Icon name="check" size={16}/><span><b>Informasi sensitif tetap aman</b><small>Event hanya menampilkan “Cuti · Nama” dan tanggal. Alasan cuti tidak dibagikan ke kalender.</small></span></div>
          <div className="settings-actions calendar-actions"><button type="button" className="primary-action auto-width" disabled={calendarBusy} onClick={saveCalendar}>{calendarBusy?"Menyimpan…":calendar.connected?"Perbarui koneksi":"Hubungkan kalender"}</button><span className="calendar-help">Admin HR mengatur koneksi untuk seluruh workspace.</span></div>
        </article>
      </div>
    )}
  </>;
}
