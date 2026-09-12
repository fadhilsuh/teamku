---
title: "chore: Pindahkan deploy apps/web ke Vercel (monorepo dipertahankan)"
type: plan
date: 2026-09-12
status: ready
scope: deployment-only
---

# chore: Pindahkan deploy `apps/web` ke Vercel

## Summary

Pindahkan target deploy `apps/web` ke Vercel sambil **mempertahankan monorepo**. Vercel mengarah ke Root Directory `apps/web`; `apps/api` tetap di repo yang sama dan di-deploy ke server Biznet. Tidak ada split repo, tidak ada perubahan arsitektur.

Browser tetap hanya berbicara ke domain Vercel: rewrite `/api/*` di `next.config.ts` dipertahankan sebagai proxy, sehingga cookie sesi tetap first-party dan **tidak ada satu baris pun kode auth yang berubah**.

Perubahan kode sangat kecil. Risiko sebenarnya ada di env build-time dan TLS di Biznet.

## Problem Frame

Monorepo ini tidak punya IaC deploy apa pun — satu-satunya jejak produksi adalah komentar `teamku.onrender.com` di `.env.example`, artinya deploy sebelumnya dilakukan manual lewat dashboard. FE dan API punya kebutuhan runtime yang berbeda: FE cocok di platform build-on-push, API wajib satu container long-running karena store-nya stateful in-process. Yang dipisahkan cukup target deploy-nya, bukan reponya.

## Temuan yang Mendasari Keputusan

Diverifikasi langsung dari kode dan dari menjalankan build, bukan asumsi:

- F1. `apps/web` memakai **tepat satu** env var: `MOVON_API_ORIGIN`, hanya di `next.config.ts`. Tidak ada `NEXT_PUBLIC_*`.
- F2. Tidak ada data fetching server-side. Seluruh trafik data lewat `lib/api.ts` di browser dengan path relatif `/api`.
- F3. Cookie sesi di-set `httponly=True, samesite="lax", path="/"`, **tanpa atribut `Domain`** (`apps/api/src/movon_hr/modules/api.py:455`). Cookie host-only.
- F4. Tidak ada upload file; `selfie_captured` hanya boolean. Payload absen kecil, jadi overhead proxy minim.
- F5. Next mengevaluasi `rewrites()` saat build dan membakukannya ke `routes-manifest.json`. Dikonfirmasi: hasil build memuat `"destination": "https://api.teamku.id/api/v1/:path*"` secara literal.
- F6. API stateful satu instance — `save_store` menghapus lalu menulis ulang seluruh baris tenant tiap request mutasi.
- F7. `package-lock.json` **tidak sinkron** dengan `package.json`; `npm ci` gagal. Tidak pernah ketahuan karena `Dockerfile` memakai `npm install` dan bahkan tidak menyalin lockfile. Vercel memakai `npm ci` → build akan gagal total.
- F8. Tidak ada konfigurasi maupun dependency ESLint, sehingga `npm run lint` membuka prompt setup interaktif dan tidak pernah benar-benar berfungsi — termasuk perintah di README.
- F9. `next lint` dan `next build` **tidak bisa dibedakan**: keduanya melaporkan `phase-production-build` dan `NODE_ENV=production`.
- F10. **Koreksi atas dugaan awal.** `teamku.onrender.com` adalah **web Next.js**, bukan API. API-nya publik terpisah di `teamku-api.onrender.com` (diverifikasi: `/health/live` 200, openapi 43 path, identik dengan yang dilayani proxy web). Topologi Render sekarang = web mem-proxy ke API, persis pola yang dipertahankan di Vercel.
- F11. Vercel **menolak men-deploy Next 15.1.2** karena bypass otorisasi middleware yang diketahui. App ini tidak punya middleware sehingga paparan nyatanya rendah, tapi blokirnya tanpa syarat. Dinaikkan ke 15.5.25.
- F12. Region default deployment adalah `iad1` (Washington DC) — merutekan user Indonesia lewat AS untuk mencapai API di Jakarta. Dipindah ke `sin1` lewat `vercel.json`.

## Key Technical Decisions

### D1. Pertahankan rewrite Next sebagai proxy; jangan panggil API langsung dari browser

Keputusan paling penting dalam plan ini.

Dengan rewrite, browser hanya bicara ke domain Vercel. `Set-Cookie` dari FastAPI mengalir balik lewat proxy dan browser mencatatnya sebagai cookie milik domain Vercel — host-only, same-origin, `SameSite=Lax` terpenuhi. Konsekuensinya: **nol perubahan** pada `lib/api.ts`, konfigurasi CORS, maupun atribut cookie.

Alternatif memanggil `https://api.<domain>` langsung dari browser ditolak karena:

- Butuh ubah `BASE` di `lib/api.ts`, aktifkan CORS kredensial, dan tinjau ulang `SameSite`.
- Preview deployment Vercel (`*.vercel.app`) cross-site terhadap `api.<domain>` → `SameSite=Lax` memblokir cookie → **login mati di semua preview**.
- `allow_methods` API saat ini `["GET","POST","PATCH","PUT"]`, perlu audit ulang.

Biaya rewrite adalah satu hop tambahan (Vercel edge → Biznet). Karena F4 memastikan payload kecil, overhead ini dapat diterima.

### D2. Monorepo dipertahankan; Vercel diarahkan lewat Root Directory

`apps/web` tidak punya dependency ke paket lokal mana pun, jadi Root Directory `apps/web` sudah cukup — opsi "Include files outside the root directory" tidak diperlukan.

Konsekuensi yang harus ditangani: tanpa penyetelan tambahan, **setiap commit ke `apps/api` akan memicu build FE yang sia-sia**. Diatasi dengan Ignored Build Step (Fase 2 langkah 5).

### D3. Gagalkan build kalau `MOVON_API_ORIGIN` tidak ada — lewat `prebuild`, bukan `next.config.ts`

Karena F5, env yang hilang saat build **tidak** error — rewrite diam-diam jatuh ke fallback `http://127.0.0.1:8000` dan seluruh aplikasi rusak di produksi dengan cara yang sulit didiagnosis.

Guard-nya **tidak boleh** ditaruh di `next.config.ts`. Upaya pertama melakukan itu dan langsung mematahkan `next lint`, karena F9: `next lint` juga memuat config dan melaporkan phase serta `NODE_ENV` yang identik dengan build.

Guard final ada di `apps/web/scripts/require-api-origin.mjs`, dijalankan sebagai npm `prebuild`, dan hanya aktif bila `VERCEL` atau `CI` di-set. Build lokal tetap bebas memakai default localhost, dan developer yang menyimpan env di `.env.local` tidak kena false positive.

Karena hook `prebuild` hanya ikut berjalan bila npm yang memanggil build, **Build Command di Vercel wajib `npm run build`, bukan `next build`.**

### D4. `output: "standalone"` dibuat kondisional, bukan dihapus

Dalam skenario monorepo, `Dockerfile` dan `infra/compose` tetap dipakai untuk pengembangan lokal, dan Dockerfile itu bergantung pada `.next/standalone`. Menghapus `standalone` akan mematahkan compose.

Karena itu: `output: process.env.VERCEL ? undefined : "standalone"`. Docker lokal tetap jalan, Vercel tidak menghasilkan artefak mubazir. Keduanya sudah diverifikasi.

## Langkah Migrasi

### Fase 1 — Perubahan kode (selesai)

Semua di branch `chore/web-vercel-migration`.

| # | Perubahan | Alasan |
|---|---|---|
| 1a | `apps/web/next.config.ts` — `standalone` kondisional, rewrite dipertahankan | D4, D1 |
| 1b | `apps/web/scripts/require-api-origin.mjs` + script `prebuild` | D3 |
| 1c | `apps/web/package.json` — `engines: node 22.x` | Paritas dengan `node:22-alpine` |
| 1d | Regenerasi `apps/web/package-lock.json` | F7 — tanpa ini build Vercel gagal di install |
| 1e | `apps/web/Dockerfile` — salin lockfile, `npm ci` | Mencegah drift F7 terulang |
| 1f | Root `.gitignore` — tambah `.vercel/` | Artefak CLI Vercel |
| 1g | Root `.env.example` — anotasi sifat build-time; redirect URI tak lagi menunjuk Render | Kejelasan |
| 1h | Root `README.md` — bagian Deployment | Dokumentasi |

Verifikasi, seluruhnya sudah dijalankan dan lulus:

| Skenario | Harapan | Hasil |
|---|---|---|
| `npm ci` | berhasil | lulus setelah 1d |
| `npm run build` lokal tanpa env | lulus, `.next/standalone` dibuat | lulus |
| `VERCEL=1 npm run build` tanpa env | gagal, exit 1 | lulus |
| `MOVON_API_ORIGIN=... VERCEL=1 npm run build` | lulus, `standalone` tidak dibuat | lulus |
| Rewrite terbakukan di `routes-manifest.json` | berisi origin absolut | lulus |

### Fase 2 — Setup Vercel

1. Import repo `fadhilsuh/teamku`.
2. **Root Directory: `apps/web`**.
3. **Build Command: `npm run build`** (wajib, agar hook `prebuild` D3 ikut berjalan).
4. Node.js Version **22.x**; Function Region **Singapore (`sin1`)** — terdekat ke Biznet Jakarta.
5. **Ignored Build Step** — cegah commit API memicu build FE (D2):
   ```
   git diff --quiet HEAD^ HEAD -- apps/web
   ```
   Vercel melewati build bila exit 0 (tidak ada perubahan di `apps/web`) dan melanjutkan bila exit 1. Bila `HEAD^` tidak tersedia, perintah gagal non-zero sehingga build tetap berjalan — arah kegagalan yang aman.
6. Environment Variables: `MOVON_API_ORIGIN=https://api.teamku.id` untuk **Production, Preview, dan Development** (build Preview juga butuh, lihat D3).
7. Deploy, verifikasi di URL `*.vercel.app`.
8. Tambahkan custom domain, arahkan DNS, tunggu TLS terbit.
9. Update `MOVON_APP_BASE_URL` di API ke domain final, restart API.

### Fase 3 — Deploy API di Biznet

- **A1. Domain + TLS publik.** Misal `api.teamku.id`, sertifikat Let's Encrypt (Caddy paling ringkas). **Sertifikat self-signed akan ditolak proxy Vercel** — penyebab kegagalan paling umum di langkah ini.
- **A2. Satu instance saja.** Jangan pasang replica atau autoscaling (F6).
- **A3. Firewall:** hanya 80/443 publik. Postgres jangan terekspos.
- **A4. Env API:**
  ```
  MOVON_DATABASE_URL=postgresql+asyncpg://...
  MOVON_APP_BASE_URL=https://<domain-vercel>
  MOVON_SESSION_COOKIE_SECURE=true
  MOVON_CORS_ORIGINS=["https://<domain-vercel>"]
  MOVON_GOOGLE_REDIRECT_URI=https://api.teamku.id/api/v1/settings/calendar/google/callback
  ```
  `MOVON_APP_BASE_URL` dipakai menyusun tautan undangan dan reset password, jadi harus domain yang dibuka user (Vercel), bukan domain API. `MOVON_CORS_ORIGINS` tidak load-bearing selama D1 dipakai, tapi tetap di-set.
- **A5. Google Cloud Console:** daftarkan ulang redirect URI di A4.
- **A6. Migrasi DB:** `alembic upgrade head` sebagai job terpisah sebelum rilis. Perlu dicatat: `apps/api/Dockerfile` meng-install dependency via `pip install` hardcoded, mengabaikan `pyproject.toml`/`uv.lock`, dan **tidak menyertakan alembic** — harus diperbaiki dulu.
- **A7. Monitoring:** `/health/live` dan `/health/ready` sudah tersedia.

## Status

- [x] Fase 1 — perubahan kode, terverifikasi lewat build
- [x] Fase 2 — project Vercel dibuat dan ter-deploy ke production
- [ ] Fase 3 — deploy API di Biznet (butuh akses server)

### Kondisi terpasang

| Item | Nilai |
|---|---|
| Project | `movon/teamku-web` |
| Production | `https://teamku-web.vercel.app`, `https://teamku-web-movon.vercel.app` |
| Region | `sin1` (diverifikasi di output build) |
| Next.js | 15.5.25 |
| `MOVON_API_ORIGIN` | `https://teamku-api.onrender.com` — **sementara**, sampai Biznet siap |

Origin API sengaja diarahkan ke Render dulu supaya FE langsung berfungsi. Saat API Biznet hidup, cukup ubah satu env var lalu redeploy — tidak ada perubahan kode.

### Yang masih terbuka

1. **Deployment Protection.** Production ada di balik Vercel Authentication (kebijakan tim movon), jadi belum bisa diakses publik maupun diverifikasi lewat curl. Perlu keputusan: matikan proteksi untuk production, atau pasang domain custom — pada Standard Protection, domain custom tetap publik sementara URL `*.vercel.app` tetap terlindungi.
2. **Env var Preview belum ter-set.** CLI menolak menambah env Preview untuk semua branch (`git_branch_required` meski argumen branch dihilangkan sesuai petunjuknya sendiri), dan varian per-branch gagal karena project belum tersambung ke Git. Tambahkan lewat dashboard, atau setelah Git tersambung.
3. **Git belum tersambung.** Deploy sekarang lewat CLI. Setelah repo disambungkan, set Root Directory `apps/web`, Build Command `npm run build`, dan Ignored Build Step (Fase 2 langkah 5).
4. **`MOVON_APP_BASE_URL` di API Render** masih menunjuk `teamku.onrender.com`, jadi tautan undangan dan reset password dari FE Vercel akan mengarah ke domain Render. Perlu diubah di sisi API.

## Verifikasi Cutover

- [ ] Login, logout, dan sesi bertahan setelah refresh
- [ ] Cookie `teamku_session` terlihat di DevTools dengan domain Vercel, `HttpOnly`, `Secure`
- [ ] Signup tenant baru
- [ ] Tautan undangan dan reset password mengarah ke domain Vercel
- [ ] Absensi (kamera + lokasi) berhasil, termasuk penolakan di luar radius
- [ ] Ajukan, setujui, dan batalkan cuti
- [ ] Payroll: hitung, finalisasi, publish
- [ ] Ask Teamku menjawab
- [ ] OAuth Google Calendar berhasil bolak-balik
- [ ] Preview deployment juga bisa login (validasi D1)
- [ ] Commit yang hanya menyentuh `apps/api` tidak memicu build Vercel (validasi D2)
- [ ] Data bertahan setelah restart API
- [ ] `docker compose up` lokal masih jalan (validasi D4)

## Risiko

| Risiko | Dampak | Mitigasi |
|---|---|---|
| `MOVON_API_ORIGIN` absen saat build | App rusak senyap, proxy ke localhost | Guard D3 |
| Build Command diubah ke `next build` | Guard D3 tidak jalan | Dicatat di README dan Fase 2 langkah 3 |
| TLS Biznet self-signed/rantai tidak lengkap | Semua request API gagal via proxy Vercel | Let's Encrypt; tes `curl -v` dari luar jaringan |
| Berharap allowlist IP Vercel di firewall Biznet | Tidak bisa dikerjakan | Vercel tidak menjamin IP egress stabil di luar Enterprise. Amankan dengan TLS + auth, bukan IP |
| API di-scale >1 instance | Kehilangan data tenant | A2 |
| Commit API memicu build FE | Kuota build terbuang | Ignored Build Step, Fase 2 langkah 5 |
| `MOVON_APP_BASE_URL` masih domain lama | Tautan undangan/reset salah arah | Fase 2 langkah 9 |

## Rollback

Deployment Vercel bersifat immutable — rollback instan lewat "Promote to Production" pada deployment sebelumnya. Selama DNS domain lama belum dicabut, pindahkan balik record-nya. Karena monorepo dipertahankan, tidak ada yang perlu digabung balik.

## Di Luar Scope

Ditemukan saat implementasi, sengaja tidak dikerjakan agar diff tetap sempit:

- **ESLint belum ada (F8).** `npm run lint` membuka prompt interaktif. Perlu keputusan config tersendiri.
- **`apps/api/Dockerfile`** meng-install dependency via `pip install` hardcoded dan tidak menyertakan `alembic`, sehingga A6 belum bisa dijalankan.

## Optimasi Lanjutan (jangan dikerjakan sekarang)

Kalau hop proxy terbukti jadi bottleneck, pindah ke pemanggilan API langsung dari browser. Syaratnya FE dan API berbagi registrable domain (`app.teamku.id` + `api.teamku.id`) agar `SameSite=Lax` tetap terpenuhi. Butuh ubah `BASE` di `lib/api.ts`, lengkapi `allow_methods` CORS, dan terima bahwa preview deployment kehilangan kemampuan login. Ukur dulu, jangan tebak.
