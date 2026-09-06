"use client";

import {useEffect,useState} from "react";
import {useRouter} from "next/navigation";
import {Icon} from "../../../components/Icon";
import {NotificationDialog,NotificationDialogState} from "../../../components/NotificationDialog";
import {api} from "../../../lib/api";
import {googleMapsEmbedUrl,googleMapsOpenUrl,isGoogleMapsShortUrl,parseGoogleMapsLocation} from "../../../lib/googleMaps";

type OfficeSettings={name:string;latitude:number;longitude:number;radius_meters:number};
type User={role:string};
type MapsParseResult={latitude:number;longitude:number;resolved_url:string;maps_url:string};

const empty:OfficeSettings={name:"Jakarta HQ",latitude:-6.2,longitude:106.8166,radius_meters:300};

export default function SettingsPage(){
  const router=useRouter();
  const [form,setForm]=useState<OfficeSettings>(empty);
  const [mapsLink,setMapsLink]=useState("");
  const [busy,setBusy]=useState(false);
  const [loading,setLoading]=useState(true);
  const [notification,setNotification]=useState<NotificationDialogState|null>(null);
  const token=()=>localStorage.getItem("movon_user")||undefined;
  const notify=(type:NotificationDialogState["type"],title:string,message:string)=>setNotification({type,title,message});
  const mapsUrl=googleMapsOpenUrl(form.latitude,form.longitude);
  const embedUrl=googleMapsEmbedUrl(form.latitude,form.longitude);

  useEffect(()=>{
    const auth=token();
    Promise.all([
      api<{user:User}>("/me",{},auth),
      api<OfficeSettings>("/settings/office",{},auth),
    ]).then(([profile,office])=>{
      if(profile.user.role!=="hr_admin"){router.replace("/app/overview");return}
      setForm(office);
      setMapsLink(googleMapsOpenUrl(office.latitude,office.longitude));
      setLoading(false);
    }).catch(reason=>{
      notify("error","Pengaturan gagal dimuat",reason instanceof Error?reason.message:"Pengaturan gagal dimuat.");
      setLoading(false);
    });
  },[router]);

  async function save(){
    if(form.name.trim().length<2){notify("error","Nama lokasi belum lengkap","Nama lokasi kantor wajib diisi.");return}
    setBusy(true);
    try{
      const saved=await api<OfficeSettings>("/settings/office",{
        method:"PUT",
        body:JSON.stringify({
          name:form.name.trim(),
          latitude:Number(form.latitude),
          longitude:Number(form.longitude),
          radius_meters:Number(form.radius_meters),
        }),
      },token());
      setForm(saved);
      setMapsLink(googleMapsOpenUrl(saved.latitude,saved.longitude));
      notify("success","Lokasi kantor diperbarui","Lokasi kantor berhasil diperbarui. Aturan check-in langsung memakai titik ini.");
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
        <p>Kelola titik lokasi kantor yang dipakai untuk verifikasi geofence check-in.</p>
      </div>
    </section>
    {loading?<div className="panel settings-panel"><p className="muted">Memuat pengaturan…</p></div>:(
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
            <button type="button" className="primary-action auto-width" disabled={busy} onClick={save}>{busy?"Menyimpan…":"Simpan lokasi kantor"}</button>
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
            <div><dt>Kebijakan</dt><dd>Check-in di luar radius ditolak otomatis</dd></div>
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
    )}
  </>;
}
