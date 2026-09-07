---
title: Remote workers, re-verification, location history, and attendance alerts
type: plan
date: 2026-09-06
status: ready
---

# Remote workers, re-verification, location history, and attendance alerts

## Summary

Tambahkan flag **remote** pada karyawan, pengaturan **re-verifikasi lokasi** di Pengaturan (untuk pekerja kantor saja), halaman **detail karyawan** dengan riwayat/tracking lokasi yang hanya bisa dibuka HR Admin dan Manager (scoped departemen), serta **notifikasi/alert otomatis** saat karyawan lupa clock-in/out atau melewati batas yang diatur HR.

## Problem Frame

Check-in saat ini hanya membuktikan keberadaan di detik pertama. Setelah itu karyawan bisa meninggalkan kantor tanpa jejak. Tim juga butuh membedakan pekerja remote (bebas lokasi) dari pekerja kantor (terikat geofence), memberi manager/HR satu tempat untuk melihat riwayat lokasi per orang, dan mengingatkan orang yang lupa clock-in/out atau melewati batas jam/sesi supaya akuntabilitas tidak bergantung pada ingatan manual.

## Requirements

- R1. Karyawan punya field boolean `is_remote` yang bisa diisi saat create/invite/edit.
- R2. Karyawan remote **bebas lokasi penuh**: check-in dan re-verifikasi tidak menolak berdasarkan geofence (selfie/konfirmasi tetap boleh diminta).
- R3. Re-verifikasi **hanya dikontrol dari modul Pengaturan** (`/app/settings`) oleh HR Admin: bisa dinyalakan/dimatikan dan parameternya diubah tanpa ubah kode.
- R3a. Field wajib di Pengaturan: toggle aktif, jumlah re-verifikasi per hari (1–3), menit mulai jendela setelah check-in, menit akhir jendela setelah check-in.
- R3b. Perubahan di Pengaturan berlaku untuk check-in berikutnya (sesi yang sudah open tetap pakai jadwal yang sudah dihitung saat check-in).
- R4. Saat re-verifikasi aktif, pekerja kantor yang sudah check-in harus memverifikasi lokasi lagi sesuai jadwal; gagal/di luar radius → anomaly tercatat.
- R5. Manager/HR dapat membuka detail karyawan yang berisi riwayat kehadiran + titik lokasi (tracking) yang sudah dicatat.
- R6. Manager hanya melihat karyawan di departemennya; HR Admin melihat semua di tenant.
- R7. Karyawan biasa tidak bisa melihat tracking lokasi orang lain.
- R8. Sistem punya notifikasi/alert bawaan (reuse inbox in-app yang sudah ada) untuk mengingatkan clock-in/out yang terlewat dan menandai pelanggaran batas yang diatur HR.
- R8a. HR mengatur dari modul Pengaturan: toggle alert, jam reminder clock-in, jam reminder clock-out, batas jam sesi terbuka (max hours), dan apakah manager/HR juga menerima alert.
- R8b. Pemicu wajib: belum check-in setelah jam reminder; sesi masih open setelah jam reminder clock-out atau max hours; missed re-verify / di luar geofence (office worker saja).
- R8c. Dedup satu notifikasi per jenis per karyawan per hari; karyawan cuti approved hari itu dilewati.
- R8d. Reminder clock-in/out berlaku untuk remote dan office; alert geofence/re-verify hanya untuk pekerja kantor.

## Scope Boundaries

**In scope**
- Field remote pada employee + UI form/direktori
- **Modul Pengaturan sebagai satu-satunya tempat HR mengatur re-verifikasi dan alert kehadiran** (toggle + parameter)
- Endpoint re-verify + prompt di UI saat sesi open
- Halaman detail karyawan + timeline lokasi
- Persistensi field baru + event lokasi di store/Postgres
- Alert/reminder otomatis clock-in, clock-out, batas jam sesi, dan anomaly re-verify — in-app via `notify()` yang sudah ada; email via mailer existing (opsional, sama channel undangan)

**Out of scope**
- Hardcode jadwal re-verify di kode tanpa UI Pengaturan
- Heartbeat lokasi diam-diam tiap N menit (bisa follow-up)
- Anti fake-GPS / liveness camera sungguhan
- Native mobile app
- Hukuman otomatis (potong gaji) — hanya anomaly + audit + notifikasi
- Peta interaktif realtime (cukup list koordinat + link Maps)
- Push notification / SMS / kalender shift per orang
- Worker/Celery baru — evaluasi alert cukup lazy + idempotent di request yang sudah di-poll

## Key Technical Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Remote policy | Skip geofence on check-in **and** re-verify | Keputusan produk: remote penuh bebas lokasi |
| Re-verify control surface | **Hanya** `apps/web/src/app/app/settings/page.tsx` (HR Admin) | Kebijakan tenant harus bisa diubah operasional tanpa deploy |
| Re-verify schedule | Configurable: `enabled`, `count_per_day` (1–3), `window_start_minutes` / `window_end_minutes` setelah check-in | HR bisa atur agresivitas tanpa code change |
| When prompts fire | Server menghitung `due_at` saat check-in; client poll `/attendance/today` | Tidak butuh Redis/Celery dulu |
| Attendance alerts | Reuse `notify()` + inbox `apps/web/src/components/Shell.tsx`; evaluasi lazy + idempotent | Inbox sudah ada; jangan bangun channel baru |
| Alert evaluation | Jalankan scan di `GET /notifications` dan `GET /attendance/today` | Shell sudah poll keduanya; tanpa worker |
| Alert policy | Sama permukaan Pengaturan: toggle, jam reminder in/out, `max_open_hours`, CC manager/HR | Operasional tanpa deploy, konsisten R3 |
| Location events | Tabel/collection `location_events` terpisah dari attendance | Satu sesi bisa punya banyak verifikasi |
| Employee detail ACL | `hr_admin` all; `manager` same department only | Sudah ada pola `visible_employees` |
| Persistence | Ikuti pola store + `tenant_id` mirror yang ada; tambah kolom di Alembic | Konsisten dengan tenancy sekarang |

## System Flow

```text
Check-in
  ├─ is_remote? → skip geofence, catat event check_in
  └─ office worker → geofence wajib, jadwalkan N re-verify slots

Open session
  └─ GET /attendance/today → pending_reverification?
        └─ UI modal: ambil GPS (+ selfie opsional) → POST /attendance/reverify
              ├─ inside radius → event ok
              └─ outside / skip → anomaly left_office / missed_reverify

People directory
  └─ klik karyawan → /app/people/[id]
        └─ GET /employees/{id}/location-history
              └─ timeline: check-in, reverify, check-out (+ lat/lng, distance, anomaly)

Attendance alerts (jika policy on)
  └─ GET /notifications atau /attendance/today → evaluate_attendance_alerts()
        ├─ no check-in after reminder time → notify employee (+ manager/HR jika CC)
        ├─ open session after checkout reminder or max hours → notify employee (+ CC)
        └─ missed_reverify / outside_geofence → notify employee + manager (office only)
```

## Implementation Units

### U1. Employee remote flag (API + persistence)

**Goal:** Karyawan punya `is_remote` yang ikut tersimpan dan terserialisasi.

**Files**
- Modify: `apps/api/src/movon_hr/modules/api.py` (`Employee`, `EmployeeInput`, invite payload, `public_employee`, check-in gate)
- Modify: `apps/api/src/movon_hr/core/persistence.py`
- Create: `apps/api/alembic/versions/0002_remote_and_reverify.py`
- Test: `apps/api/tests/test_remote_attendance.py`

**Approach**
- Tambah `is_remote: bool = False` ke `Employee`, create/invite/update payloads.
- Check-in: jika `user.is_remote`, lewati jarak Haversine; tetap catat lat/lng jika dikirim (opsional) atau izinkan tanpa geofence reject.
- Seed demo: biarkan default `false`; boleh 1 akun demo remote untuk QA.

**Verification**
- Remote check-in di luar radius → 200
- Non-remote di luar radius → 403 (behavior lama)

**Test scenarios**
- Remote employee check-in far from office succeeds
- Office employee far from office still rejected
- Create/invite employee with `is_remote=true` persists and returns in `/employees`

---

### U2. Re-verification settings di modul Pengaturan

**Goal:** HR Admin mengaktifkan dan mengatur re-verifikasi **sepenuhnya dari modul Pengaturan** (`/app/settings`). Tanpa setting ini aktif, tidak ada prompt re-verify.

**Files**
- Modify: `apps/api/src/movon_hr/modules/api.py` (perluas payload `GET/PUT /settings/office` atau endpoint `/settings/attendance-policy`)
- Modify: `apps/api/src/movon_hr/core/persistence.py` + Alembic `0002`
- Modify: `apps/web/src/app/app/settings/page.tsx` — section baru di bawah lokasi kantor
- Test: `apps/api/tests/test_reverification_settings.py`

**Approach**
- Simpan policy per tenant bersama pengaturan kantor (satu form Pengaturan; section alert di U5):
  - Section 1 (existing): lokasi + radius geofence
  - Section 2 (**baru**): “Re-verifikasi lokasi”
    - Toggle: Aktifkan re-verifikasi
    - Jumlah per hari: 1 / 2 / 3
    - Jendela mulai (menit setelah check-in), mis. 60
    - Jendela akhir (menit setelah check-in), mis. 420
- Copy UI Bahasa Indonesia, jelas bahwa ini hanya berlaku untuk karyawan **bukan remote**.
- Default: `reverify_enabled=false` supaya tenant existing aman sampai HR menyalakan.
- API: field ikut di GET/PUT settings yang sudah dipakai halaman Pengaturan (hindari halaman admin terpisah).

**Wireframe section (Pengaturan)**
```text
Pengaturan
├─ Lokasi kantor (existing)
├─ Re-verifikasi lokasi          ← U2
│  ├─ [ ] Aktifkan re-verifikasi
│  ├─ Jumlah per hari: [1|2|3]
│  ├─ Mulai setelah check-in: [60] menit
│  └─ Berakhir setelah check-in: [420] menit
└─ Notifikasi & alert kehadiran  ← U5
   ├─ [ ] Aktifkan pengingat kehadiran
   ├─ Reminder clock-in: [09:15]
   ├─ Reminder clock-out: [18:15]
   ├─ Batas sesi terbuka: [10] jam
   └─ [ ] Kirim juga ke manager/HR
```

**Verification**
- HR mengubah toggle/parameter di `/app/settings` → tersimpan → GET mengembalikan nilai sama
- Non-HR tidak bisa ubah
- Dengan toggle off, check-in office worker tidak membuat pending reverify

**Test scenarios**
- HR can enable reverify with count=2 from settings payload
- Invalid count rejected
- Manager cannot update policy
- Disabled policy means no pending_reverification after check-in

---

### U3. Re-verification runtime (schedule + submit)

**Goal:** Setelah check-in, pekerja kantor mendapat permintaan verifikasi ulang; hasilnya tercatat.

**Files**
- Modify: `apps/api/src/movon_hr/modules/api.py` (attendance today, new reverify endpoint, event model)
- Modify: `apps/web/src/app/app/attendance/today/page.tsx`
- Optional: shell banner/modal global di `apps/web/src/components/Shell.tsx`
- Test: `apps/api/tests/test_reverification_flow.py`

**Approach**
- Model `LocationEvent`: `id`, `employee_id`, `attendance_id`, `kind` (`check_in`|`reverify`|`check_out`), `at`, `lat`, `lng`, `accuracy`, `distance_meters`, `inside_geofence`, `anomaly`
- Saat check-in office worker + policy on: buat N slot `due_at` acak di jendela; expose `pending_reverification` di `/attendance/today`
- `POST /attendance/reverify`: GPS (+ selfie flag); remote → auto-pass / skip due; office → Haversine; luar radius → simpan event + anomaly `outside_geofence` (jangan silent drop)
- Missed due (lewat `due_at` tanpa submit): saat poll/checkout tandai `missed_reverify` dan biarkan U5 mengirim alert
- UI: modal blocking ringan saat ada pending (bisa ditunda singkat, tapi deadline tetap)

**Verification**
- Dengan policy on, after check-in today returns pending slot
- Successful reverify clears pending and writes event
- Outside radius writes anomaly event

**Test scenarios**
- Office worker gets scheduled reverifies when enabled
- Remote worker never gets pending reverify
- Outside-geofence reverify recorded with anomaly
- Missed deadline creates `missed_reverify` anomaly

---

### U4. People UI: remote field + employee detail page

**Goal:** HR bisa set remote; Manager/HR membuka detail + history lokasi.

**Files**
- Modify: `apps/web/src/app/app/people/page.tsx`
- Create: `apps/web/src/app/app/people/[id]/page.tsx`
- Modify: `apps/api/src/movon_hr/modules/api.py` (`GET /employees/{id}`, `GET /employees/{id}/location-history`)
- Test: `apps/api/tests/test_employee_location_history.py`

**Approach**
- Direktori: kolom/badge `Remote` / `Kantor`; form tambah checkbox “Pekerja remote (bebas lokasi)”
- Detail page: profil ringkas + timeline events (waktu, jenis, jarak, anomaly, link Maps `lat,lng`)
- API detail/history: `require(manager|hr_admin)` + harus ada di `visible_employees`
- Employee membuka `/people/{ownId}` boleh lihat profil sendiri tanpa history lokasi orang lain; history lokasi **hanya** manager/HR (R5–R7)

**Verification**
- Manager dari dept A tidak melihat history dept B
- HR melihat semua di tenant
- Employee tidak akses history rekan

**Test scenarios**
- Manager scoped history 403/404 for other department
- HR can list location events for any tenant employee
- Employee cannot fetch another employee's location history
- Detail shows check-in and reverify events in chronological order

---

### U5. Automated attendance notifications and alerts

**Goal:** Sistem mengirim pengingat/alert bawaan saat karyawan lupa clock-in/out atau melewati batas yang diatur HR, supaya akuntabilitas tidak bergantung pada ingatan manual.

**Files**
- Modify: `apps/api/src/movon_hr/modules/api.py` (`notify()`, `GET /notifications`, `GET /attendance/today`, settings payload)
- Modify: `apps/api/src/movon_hr/core/persistence.py` + Alembic `0002` (field policy alert)
- Modify: `apps/web/src/app/app/settings/page.tsx` — section “Notifikasi & alert kehadiran”
- Reuse: inbox `apps/web/src/components/Shell.tsx` (tidak perlu UI inbox baru)
- Test: `apps/api/tests/test_attendance_alerts.py`

**Approach**
- Policy tenant di Pengaturan (default off, sama seperti re-verify):
  - `alerts_enabled`
  - `clock_in_reminder_time` (Asia/Jakarta, mis. 09:15)
  - `clock_out_reminder_time` (mis. 18:15)
  - `max_open_hours` (mis. 10)
  - `alert_managers` (bool)
- Fungsi `evaluate_attendance_alerts()` idempotent, dipanggil dari `GET /notifications` dan `GET /attendance/today`. Tanpa worker/Celery.
- Pemicu:
  - `missed_clock_in`: karyawan aktif, bukan cuti approved hari ini, belum ada attendance hari ini, waktu lokal ≥ reminder clock-in
  - `missed_clock_out`: sesi masih open dan (waktu ≥ reminder clock-out **atau** durasi ≥ `max_open_hours`)
  - `limit_reverify` / `limit_geofence`: anomaly `missed_reverify` atau `outside_geofence` hari ini (hanya office worker)
- Target: karyawan selalu; jika `alert_managers`, manager departemen + HR Admin. Remote tetap dapat reminder in/out, tidak dapat alert geofence.
- Dedup: kunci `kind + employee_id + local_date`; jangan spam jika scan jalan berkali-kali.
- Channel: in-app via `notify()` existing (`title`, `detail`, `target=/app/attendance/today`). Email via `send_email` boleh menyertai reminder in/out (channel undangan yang sama); push/SMS tetap out of scope.
- Copy inbox Bahasa Indonesia, netral: “Belum clock-in”, “Sesi masih terbuka”, “Re-verifikasi terlewat” — bukan bahasa hukuman.

**Verification**
- Toggle off → tidak ada alert attendance baru
- Setelah jam reminder, karyawan tanpa check-in mendapat 1 notifikasi; scan kedua hari yang sama tidak menambah
- Sesi open melewati max hours → alert clock-out
- Manager/HR menerima CC hanya jika `alert_managers` on
- Karyawan cuti approved tidak diingatkan clock-in

**Test scenarios**
- Disabled policy creates no attendance alerts
- Missed clock-in after reminder time notifies employee once per day
- Approved leave skips missed clock-in
- Open session past max hours notifies employee
- `alert_managers=true` notifies department manager and HR
- Remote employee gets clock-in reminder but not geofence-limit alert
- Outside-geofence / missed reverify creates accountability alert for office worker
- Repeated `/notifications` poll does not duplicate the same kind/day

## Dependencies & Sequencing

```text
U1 remote flag
  └─► U3 reverify runtime (needs is_remote gate)
U2 settings policy
  ├─► U3 reverify runtime
  └─► U5 attendance alerts (same Pengaturan payload)
U1 + U3 location events
  └─► U4 detail/history UI
U3 anomaly events
  └─► U5 geofence / missed-reverify alerts
```

Implement order: **U1 → U2 → U3 → U4 → U5**.

## Risks & Edge Cases

| Risk | Mitigation |
|---|---|
| Browser tab ditutup saat due | Flag `missed_reverify` on next poll/checkout; U5 mengirim in-app (+ email opsional), bukan push |
| Karyawan tidak membuka app | Manager/HR tetap dapat CC saat seseorang di tenant mem-poll inbox; email reminder in/out menutup gap offline |
| Alert spam | Dedup `kind + employee_id + local_date`; default policy off |
| Fake GPS | Explicitly out of scope; catat accuracy + anomaly saja |
| Privacy | History hanya manager/HR; consent lokasi sudah ada di check-in flow |
| Existing DB rows | Migration default `is_remote=false`, policy disabled |
| TestClient cookies/header | Ikuti pola bearer/`X-Demo-User` yang sudah dipakai di tenancy tests |

## Success Criteria

- Remote employee dapat check-in dari luar radius tanpa error
- **HR dapat mengaktifkan/mematikan dan mengatur re-verifikasi dari modul Pengaturan**
- Office employee dengan sesi open mendapat prompt re-verify **hanya jika** setting di Pengaturan aktif
- Manager/HR membuka detail karyawan dan melihat timeline lokasi; employee tidak bisa melihat milik orang lain
- **HR dapat mengaktifkan pengingat clock-in/out dan alert batas dari Pengaturan**; karyawan yang lupa atau melewati batas mendapat notifikasi in-app (tanpa duplikat per hari)

## Deferred to Implementation

- Exact random scheduling algorithm (uniform vs jittered slots)
- Whether selfie wajib pada re-verify (disarankan: sama dengan check-in policy, default true untuk office)
- Map embed vs external Maps link only on detail page
- Whether missed reverify blocks checkout or only flags anomaly (disarankan: **flag only**, jangan kunci checkout)
- Apakah email reminder wajib atau hanya in-app dulu (disarankan: in-app wajib, email menyertai reminder in/out)
- Apakah `max_open_hours` dihitung dari check-in aktual atau dari jam kerja tetap (disarankan: dari check-in aktual)

## Execution Notes

- Characterization-first untuk check-in geofence existing sebelum mengubah gate remote
- Semua endpoint baru harus tenant-scoped lewat store aktif
- Jangan klaim “anti-fraud 100%” di copy UI — gunakan bahasa “re-verifikasi lokasi” / “pemantauan kehadiran”
