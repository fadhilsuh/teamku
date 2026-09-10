"use client";

import {useEffect,useState} from "react";
import {useParams,useRouter} from "next/navigation";
import {NotificationDialog,NotificationDialogState} from "../../../../components/NotificationDialog";
import {api} from "../../../../lib/api";

type Employee={
  id:string;
  name:string;
  email:string;
  role:string;
  department:string;
  title:string;
  status:string;
  salary?:number|null;
  is_remote?:boolean;
  work_location_id?:string|null;
  work_location?:{id:string;name:string}|null;
};
type User={id:string;role:string};
type WorkLocation={id:string;name:string};
type LocationEvent={
  id:string;
  kind:string;
  at:string;
  lat:number|null;
  lng:number|null;
  accuracy:number|null;
  distance_meters:number|null;
  inside_geofence:boolean|null;
  anomaly:string|null;
  maps_url:string|null;
};

const kindLabel:Record<string,string>={
  check_in:"Check-in",
  reverify:"Re-verifikasi",
  check_out:"Check-out",
};

export default function EmployeeDetail(){
  const params=useParams<{id:string}>();
  const router=useRouter();
  const [employee,setEmployee]=useState<Employee>();
  const [events,setEvents]=useState<LocationEvent[]|null>(null);
  const [role,setRole]=useState("");
  const [locations,setLocations]=useState<WorkLocation[]>([]);
  const [busy,setBusy]=useState(false);
  const [notification,setNotification]=useState<NotificationDialogState|null>(null);
  const token=()=>localStorage.getItem("movon_user")||undefined;
  const notify=(type:NotificationDialogState["type"],title:string,message:string)=>setNotification({type,title,message});

  const load=()=>{
    const auth=token();
    const id=params.id;
    Promise.all([
      api<Employee>(`/employees/${id}`,{},auth),
      api<{user:User}>("/me",{},auth),
      api<{items:WorkLocation[]}>("/settings/locations",{},auth),
    ]).then(([profile,me,locationResult])=>{
      setEmployee(profile);
      setRole(me.user.role);
      setLocations(locationResult.items);
      if(me.user.role==="manager"||me.user.role==="hr_admin"){
        return api<{items:LocationEvent[]}>(`/employees/${id}/location-history`,{},auth).then(history=>setEvents(history.items));
      }
      setEvents([]);
    }).catch(reason=>{
      notify("error","Profil gagal dimuat",reason instanceof Error?reason.message:"Data karyawan gagal dimuat.");
    });
  };

  useEffect(()=>{load()},[params.id]);

  async function toggleRemote(){
    if(!employee||role!=="hr_admin")return;
    setBusy(true);
    try{
      const updated=await api<Employee>(`/employees/${employee.id}`,{
        method:"PATCH",
        body:JSON.stringify({is_remote:!employee.is_remote}),
      },token());
      setEmployee(updated);
      notify("success","Lokasi kerja diperbarui",updated.is_remote?"Karyawan ditandai sebagai pekerja remote.":"Karyawan ditandai sebagai pekerja kantor.");
    }catch(reason){
      notify("error","Perubahan gagal",reason instanceof Error?reason.message:"Status remote gagal diperbarui.");
    }finally{setBusy(false)}
  }

  async function assignLocation(workLocationId:string){
    if(!employee||role!=="hr_admin")return;
    setBusy(true);
    try{
      const updated=await api<Employee>(`/employees/${employee.id}`,{method:"PATCH",body:JSON.stringify({work_location_id:workLocationId})},token());
      setEmployee(updated);notify("success","Lokasi kerja diperbarui",`${employee.name} kini ditugaskan ke ${updated.work_location?.name}.`);
    }catch(reason){notify("error","Perubahan gagal",reason instanceof Error?reason.message:"Lokasi kerja gagal diperbarui.")}finally{setBusy(false)}
  }

  if(!employee){
    return <>
      <NotificationDialog notification={notification} onClose={()=>setNotification(null)}/>
      <section className="page-heading"><div><p className="eyebrow">People</p><h1>Detail karyawan</h1><p>Memuat profil…</p></div></section>
    </>;
  }

  const canSeeHistory=role==="manager"||role==="hr_admin";

  return <>
    <NotificationDialog notification={notification} onClose={()=>setNotification(null)}/>
    <section className="page-heading">
      <div>
        <p className="eyebrow">People</p>
        <h1>{employee.name}</h1>
        <p>{employee.title} · {employee.department}</p>
      </div>
      <button type="button" className="text-link people-back" onClick={()=>router.push("/app/people")}>← Kembali ke direktori</button>
    </section>

    <section className="people-detail-grid">
      <article className="panel">
        <div className="panel-head">
          <div>
            <p className="eyebrow">Profil</p>
            <h2>Ringkasan karyawan</h2>
          </div>
          <span className={`status ${employee.is_remote?"remote":"office"}`}>{employee.is_remote?"Sales / Lapangan":employee.work_location?.name||"Kantor"}</span>
        </div>
        <dl className="settings-preview">
          <div><dt>Email</dt><dd>{employee.email}</dd></div>
          <div><dt>Peran</dt><dd>{employee.role==="hr_admin"?"HR Admin":employee.role==="manager"?"Manager":"Employee"}</dd></div>
          <div><dt>Status</dt><dd>{employee.status==="active"?"Aktif":employee.status==="suspended"?"Ditangguhkan":"Berakhir"}</dd></div>
          <div><dt>Gaji</dt><dd>{employee.salary!=null?formatMoney(employee.salary):"Tidak berwenang"}</dd></div>
          <div><dt>Lokasi kerja</dt><dd>{employee.is_remote?"Sales / lapangan (lokasi dicatat)":employee.work_location?.name||"Kantor utama"}</dd></div>
        </dl>
        {role==="hr_admin"&&(
          <div className="settings-actions">
            <button type="button" className="secondary-button" disabled={busy} onClick={toggleRemote}>
              {employee.is_remote?"Ubah ke pekerja kantor":"Tandai sebagai sales/lapangan"}
            </button>
            {!employee.is_remote&&<select aria-label="Tetapkan lokasi kerja" disabled={busy} value={employee.work_location_id||"office-default"} onChange={event=>assignLocation(event.target.value)}>{locations.map(location=><option key={location.id} value={location.id}>{location.name}</option>)}</select>}
          </div>
        )}
      </article>

      <article className="panel">
        <div className="panel-head">
          <div>
            <p className="eyebrow">Location history</p>
            <h2>Riwayat lokasi</h2>
          </div>
        </div>
        {!canSeeHistory&&<p className="settings-copy">Riwayat lokasi hanya dapat dilihat manager dan HR Admin.</p>}
        {canSeeHistory&&events&&events.length===0&&(
          <div className="feature-empty compact">
            <span>⌖</span>
            <h2>Belum ada titik lokasi</h2>
            <p>Check-in, re-verifikasi, dan check-out akan tampil di sini.</p>
          </div>
        )}
        {canSeeHistory&&events&&events.length>0&&(
          <ol className="location-timeline">
            {events.map(event=>(
              <li key={event.id}>
                <div>
                  <b>{kindLabel[event.kind]||event.kind}</b>
                  <small>{formatWhen(event.at)}</small>
                </div>
                <div className="location-meta">
                  {event.distance_meters!=null&&<span>{event.distance_meters} m dari kantor</span>}
                  {event.inside_geofence===true&&<span className="status active">Dalam radius</span>}
                  {event.inside_geofence===false&&<span className="status warning">Di luar radius</span>}
                  {event.anomaly&&<span className="status warning">{anomalyLabel(event.anomaly)}</span>}
                  {event.maps_url&&<a className="text-link" href={event.maps_url} target="_blank" rel="noreferrer">Buka di Maps</a>}
                  {event.lat!=null&&event.lng!=null&&<small>{event.lat}, {event.lng}</small>}
                </div>
              </li>
            ))}
          </ol>
        )}
      </article>
    </section>
  </>;
}

function formatMoney(value:number){
  return new Intl.NumberFormat("id-ID",{style:"currency",currency:"IDR",maximumFractionDigits:0}).format(value);
}

function formatWhen(value:string){
  return new Intl.DateTimeFormat("id-ID",{
    weekday:"short",
    day:"2-digit",
    month:"short",
    hour:"2-digit",
    minute:"2-digit",
  }).format(new Date(value));
}

function anomalyLabel(value:string){
  if(value==="outside_geofence")return "Di luar geofence";
  if(value==="missed_reverify")return "Re-verifikasi terlewat";
  if(value==="low_accuracy")return "Akurasi rendah";
  return value;
}
