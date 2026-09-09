"use client";

import {FormEvent,useState} from "react";
import Link from "next/link";
import {api} from "../../../lib/api";
import {Icon} from "../../../components/Icon";

type Citation={policy_id:string;policy_title:string;section_id:string;section_heading:string;effective_date:string;excerpt:string};
type Answer={answer:string;confidence:"supported"|"partially_supported"|"insufficient_evidence";citations:Citation[];personal_facts:{label:string;value:string|number}[];suggested_action:{type:string;href:string}};
const examples=["Apakah saya perlu surat dokter untuk cuti sakit?","How many leave days do I have?","Siapa yang menyetujui cuti saya?"];
const popular=[
  {title:"Cuti & Leave",copy:"Jenis cuti, kuota, prosedur pengajuan",tone:"blue",href:"/app/approvals",icon:"calendar" as const},
  {title:"Sakit & Izin",copy:"Surat dokter, prosedur izin, ketentuan",tone:"green",href:"/app/approvals",icon:"check" as const},
  {title:"Absensi",copy:"Jadwal kerja, lembur, kehadiran",tone:"purple",href:"/app/overview",icon:"clock" as const},
  {title:"Payroll",copy:"Gaji, tunjangan, potongan, slip gaji",tone:"orange",href:"/app/overview",icon:"wallet" as const},
];

export default function AskTeamkuPage(){
  const [question,setQuestion]=useState(""); const [answer,setAnswer]=useState<Answer>(); const [busy,setBusy]=useState(false); const [error,setError]=useState("");
  const ask=async(event:FormEvent)=>{event.preventDefault(); if(question.trim().length<3)return; setBusy(true);setError("");try{setAnswer(await api<Answer>("/policy-assistant/questions",{method:"POST",body:JSON.stringify({question:question.trim()})},localStorage.getItem("movon_user")||undefined));}catch(reason){setError(reason instanceof Error?reason.message:"Jawaban tidak dapat dimuat.");}finally{setBusy(false)}};
  return <section className="ask-teamku">
    <div className="ask-dashboard-grid">
      <div className="ask-main-column">
        <div className="ask-hero"><div><p className="eyebrow">Company policy assistant</p><h1>Ask Teamku</h1><p>Jawaban hanya bersumber dari kebijakan perusahaan yang aktif.<br/>Untuk keputusan penting, konfirmasi ke HR.</p></div><div className="ask-robot" aria-hidden="true"><span>⌣</span><i></i><b></b></div></div>
        <article className="panel ask-form"><form onSubmit={ask}><label htmlFor="teamku-question"><Icon name="spark" size={18}/>Apa yang ingin Anda tanyakan?</label><textarea id="teamku-question" rows={4} maxLength={800} value={question} onChange={event=>setQuestion(event.target.value)} placeholder="Contoh: Apakah saya perlu surat dokter untuk cuti sakit?"/><div className="ask-actions"><span>{question.length}/800</span><div className="ask-submit-row"><span className="ask-attach">⌕</span><button className="primary-action auto-width" disabled={busy||question.trim().length<3}>{busy?"Mencari kebijakan…":"Tanya Teamku  →"}</button></div></div></form><div className="ask-examples">{examples.map(example=><button type="button" key={example} onClick={()=>setQuestion(example)}>{example}</button>)}<button type="button" onClick={()=>setQuestion(examples[Math.floor(Math.random()*examples.length)])}>↻ &nbsp; Lihat lainnya</button></div></article>
        <section className="ask-popular"><div className="ask-section-heading"><div><h2><span>♨</span> Topik Populer</h2><p>Pertanyaan yang paling sering ditanyakan oleh karyawan</p></div></div><div className="ask-topic-grid">{popular.map(item=><Link className={`ask-topic-card ${item.tone}`} href={item.href} key={item.title}><span className="ask-topic-icon"><Icon name={item.icon} size={20}/></span><span><b>{item.title}</b><small>{item.copy}</small></span><i>→</i></Link>)}</div></section>
        <div className="ask-help"><div><h2>Butuh bantuan lebih lanjut?</h2><p>Jika pertanyaan Anda tidak terjawab, silakan hubungi tim HR.</p></div><a className="secondary-button" href="mailto:hr@company.local">✉ &nbsp; Hubungi HR</a></div>
        {error&&<article className="panel feature-empty compact"><h2>Belum dapat menjawab</h2><p>{error}</p><a className="secondary-button" href="mailto:hr@company.local">Hubungi HR</a></article>}{answer&&<article className="panel ask-answer"><div className="panel-head"><div><p className="eyebrow">Jawaban kebijakan</p><h2>{answer.confidence==="supported"?"Didukung kebijakan":"Perlu konfirmasi HR"}</h2></div><span className={`status ${answer.confidence==="supported"?"published":"draft"}`}>{answer.confidence.replace("_"," ")}</span></div><p className="ask-answer-copy">{answer.answer}</p>{answer.personal_facts.length>0&&<div className="ask-facts">{answer.personal_facts.map(item=><span key={item.label}><b>{item.label}</b> {item.value}</span>)}</div>}{answer.citations.length>0&&<details className="ask-citations" open><summary>Sumber kebijakan ({answer.citations.length})</summary>{answer.citations.map(item=><article key={`${item.policy_id}-${item.section_id}`}><b>{item.policy_title} · {item.section_heading}</b><small>Berlaku sejak {item.effective_date}</small><p>{item.excerpt}</p></article>)}</details>}<div className="ask-actions"><a className="secondary-button" href="mailto:hr@company.local">Hubungi HR</a>{answer.suggested_action.type!=="contact_hr"&&<Link className="primary-action auto-width" href={answer.suggested_action.href}>Buka tindakan terkait</Link>}</div></article>}
      </div>
      <aside className="ask-sidebar"><article className="panel ask-quick"><div className="ask-side-heading"><Icon name="grid" size={18}/><h2>Quick Access</h2></div>{[["Kebijakan Perusahaan","Lihat seluruh dokumen","/app/settings/policies","check"], ["Ajukan Cuti","Buat pengajuan cuti baru","/app/approvals","calendar"], ["Slip Gaji","Lihat slip gaji terbaru","/app/overview","wallet"], ["Profil Saya","Kelola data personal","/app/people","users"]].map(([title,copy,href,icon])=><Link className="ask-access-row" href={href} key={title}><span className="ask-access-icon"><Icon name={icon as "check"} size={19}/></span><span><b>{title}</b><small>{copy}</small></span><i>›</i></Link>)}</article><article className="panel ask-history"><div className="ask-side-heading"><Icon name="clock" size={18}/><h2>Riwayat Percakapan</h2><a href="#history">Lihat semua</a></div>{examples.concat(["Apakah lembur dihitung di payroll?","Prosedur kerja remote"]).map((item,index)=><button type="button" className="ask-history-row" key={item} onClick={()=>setQuestion(item)}><span><Icon name="spark" size={15}/></span><b>{item}</b><small>{index<2?"2 jam yang lalu":index===2?"2 hari yang lalu":"5 hari yang lalu"}</small><i>›</i></button>)}</article></aside>
    </div>
  </section>;
}
