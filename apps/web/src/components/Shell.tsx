"use client";

import Link from "next/link";
import {usePathname, useRouter} from "next/navigation";
import {useEffect, useMemo, useState} from "react";
import {api} from "../lib/api";
import {waitForAuthTransition} from "../lib/transition";
import {AuthTransition} from "./AuthTransition";
import {Icon} from "./Icon";

type Role = "employee" | "manager" | "hr_admin";
type User = {id:string;name:string;email:string;role:Role;department:string;title:string};
type Tenant = {id:string;name:string;slug:string};
type Office = {name:string};
type Notification = {id:string;title:string;detail:string;target:string;read:boolean};
type NavItem = readonly [string,string,"grid"|"clock"|"calendar"|"users"|"check"|"wallet"|"pin"];

const workspace: NavItem[] = [
  ["Beranda","/app/overview","grid"],
  ["Kehadiran","/app/attendance/today","clock"],
  ["Agenda & Cuti","/app/time/time-off","calendar"],
];

export function Shell({children}:{children:React.ReactNode}) {
  const pathname=usePathname();
  const router=useRouter();
  const [user,setUser]=useState<User>();
  const [tenant,setTenant]=useState<Tenant>();
  const [officeName,setOfficeName]=useState("Kantor");
  const [notifications,setNotifications]=useState<Notification[]>([]);
  const [menuOpen,setMenuOpen]=useState(false);
  const [bootstrapError,setBootstrapError]=useState("");
  const [bootstrapAttempt,setBootstrapAttempt]=useState(0);
  const [searchOpen,setSearchOpen]=useState(false);
  const [notificationsOpen,setNotificationsOpen]=useState(false);
  const [intelligenceOpen,setIntelligenceOpen]=useState(false);
  const [signingOut,setSigningOut]=useState(false);

  useEffect(()=>{
    const token=localStorage.getItem("movon_user")||undefined;
    setBootstrapError("");
    api<{user:User;tenant:Tenant}>("/me",{},token).then(profile=>{
      setUser(profile.user);
      setTenant(profile.tenant);
    }).catch(reason=>{
      if(!token){router.replace("/login");return}
      setBootstrapError(reason instanceof Error?reason.message:"Workspace gagal dimuat.");
    });
    api<{items:Notification[]}>("/notifications",{},token).then(inbox=>setNotifications(inbox.items)).catch(()=>setNotifications([]));
    api<Office>("/settings/office",{},token).then(office=>setOfficeName(office.name)).catch(()=>setOfficeName("Kantor"));
  },[router,bootstrapAttempt]);

  const nav=useMemo(()=>{
    if(!user)return workspace;
    const items=[...workspace];
    if(user.role!=="employee")items.push(["Karyawan","/app/people","users"]);
    return items;
  },[user]);
  const operations=useMemo<NavItem[]>(()=>{
    if(user?.role==="hr_admin")return [["Persetujuan","/app/approvals","check"],["Payroll","/app/payroll/runs","wallet"],["Slip Gaji","/app/payroll/payslips","wallet"],["Pengaturan","/app/settings","pin"]];
    if(user?.role==="manager")return [["Persetujuan","/app/approvals","check"],["Slip Gaji","/app/payroll/payslips","wallet"]];
    return [["Slip Gaji","/app/payroll/payslips","wallet"]];
  },[user]);
  const initials=user?.name.split(" ").map(part=>part[0]).slice(0,2).join("")||"--";
  const roleLabel=user?.role==="hr_admin"?"HR Admin":user?.role==="manager"?"Manager":"Employee";
  const unread=notifications.filter(item=>!item.read).length;
  const allNav=[...nav,...operations];

  const logout=async()=>{
    if(signingOut)return;
    const startedAt=Date.now();
    setSigningOut(true);
    const token=localStorage.getItem("movon_user")||undefined;
    try{
      if(token)await api("/auth/logout",{method:"POST"},token);
    }catch{
      // Local logout must still complete if the server is unavailable.
    }finally{
      await waitForAuthTransition(startedAt);
      localStorage.removeItem("movon_user");
      router.replace("/login");
    }
  };
  const markRead=async()=>{
    const token=localStorage.getItem("movon_user")||undefined;
    await api("/notifications/read-all",{method:"POST"},token);
    setNotifications(items=>items.map(item=>({...item,read:true})));
  };
  const links=(items:NavItem[])=>items.map(([label,href,icon])=><Link onClick={()=>setMenuOpen(false)} className={pathname.startsWith(href)?"nav-link active":"nav-link"} key={href} href={href}><Icon name={icon}/><span>{label}</span></Link>);

  if(!user)return bootstrapError?<div className="session-recovery"><b>Workspace belum dapat dimuat</b><p>{bootstrapError}</p><div><button onClick={()=>setBootstrapAttempt(value=>value+1)}>Coba lagi</button><button onClick={logout}>Kembali ke login</button></div></div>:<div className="session-loader"><span/>Memuat workspace…</div>;
  return <div className="app-frame">
    {menuOpen&&<button className="sidebar-backdrop" aria-label="Tutup navigasi" onClick={()=>setMenuOpen(false)}/>}
    <aside className={menuOpen?"sidebar open":"sidebar"}>
      <Link className="sidebar-brand" href="/app/overview"><span>teamku</span><small>PEOPLE OS</small></Link>
      <div className="sidebar-section"><p>Workspace</p>{links(nav)}</div>
      {operations.length>0&&<div className="sidebar-section"><p>Operations</p>{links(operations)}</div>}
      <div className={intelligenceOpen?"sidebar-callout expanded":"sidebar-callout"}><span className="callout-icon"><Icon name="spark"/></span><b>Movon Intelligence</b><small>{intelligenceOpen?"Ringkasan operasional berasal dari data kehadiran, cuti, dan payroll di workspace ini.":"Insight tim, tanpa spreadsheet."}</small><button type="button" onClick={()=>setIntelligenceOpen(value=>!value)}>{intelligenceOpen?"Tutup penjelasan":"Pelajari fitur"}</button></div>
      <div className="user-panel"><span className="avatar">{initials}</span><span><b>{user.name}</b><small>{roleLabel}</small></span><button className="logout-button" type="button" onClick={logout} aria-label="Keluar" title="Keluar"><Icon name="logout" size={17}/></button></div>
    </aside>
    <div className="app-workspace">
      <header className="app-topbar">
        <button className="mobile-menu" onClick={()=>setMenuOpen(true)} aria-label="Buka navigasi"><Icon name="menu"/></button>
        <div className="workspace-name"><b>{tenant?.name||"Teamku"}</b><span>{user.department} · {officeName}</span></div>
        <div className="topbar-actions">
          <button className="search-button" onClick={()=>setSearchOpen(value=>!value)} aria-expanded={searchOpen}><Icon name="search"/><span>Cari karyawan atau menu</span><kbd>⌘ K</kbd></button>
          <button className="icon-button" onClick={()=>setNotificationsOpen(value=>!value)} aria-label={`Notifikasi, ${unread} belum dibaca`} aria-expanded={notificationsOpen}><Icon name="bell"/>{unread>0&&<i/>}</button>
          <button className="icon-button mobile-logout" type="button" onClick={logout} aria-label="Keluar" title="Keluar"><Icon name="logout"/></button>
          <span className="top-avatar">{initials}</span>
        </div>
        {searchOpen&&<div className="topbar-popover search-popover"><b>Pindah cepat</b>{allNav.map(([label,href,icon])=><Link href={href} key={href} onClick={()=>setSearchOpen(false)}><Icon name={icon}/><span>{label}</span></Link>)}</div>}
      </header>
      <main className="content"><div className="route-content" key={pathname}>{children}</div></main>
      <nav className="mobile-nav">{links(nav.slice(0,4))}</nav>
      {notificationsOpen&&(
        <div className="dialog-backdrop" role="presentation" onClick={()=>setNotificationsOpen(false)}>
          <section className="decision-dialog notification-inbox-dialog" role="dialog" aria-modal="true" aria-labelledby="notifications-title" onClick={event=>event.stopPropagation()}>
            <div className="popover-head">
              <div><p className="eyebrow">Inbox</p><h2 id="notifications-title">Notifikasi</h2></div>
              {unread>0&&<button type="button" onClick={markRead}>Tandai dibaca</button>}
            </div>
            {notifications.length?notifications.map(item=><Link className={item.read?"notification-item":"notification-item unread"} href={item.target} key={item.id} onClick={()=>setNotificationsOpen(false)}><b>{item.title}</b><small>{item.detail}</small></Link>):<p className="popover-empty">Tidak ada notifikasi baru.</p>}
            <div className="dialog-actions"><button type="button" className="secondary-button" onClick={()=>setNotificationsOpen(false)}>Tutup</button></div>
          </section>
        </div>
      )}
      {signingOut&&<AuthTransition message="Mengakhiri sesi…"/>}
    </div>
  </div>;
}
