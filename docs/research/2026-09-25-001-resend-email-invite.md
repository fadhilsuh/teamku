# Resend untuk email "Undang via email" (Employee Master)

Tanggal riset: 2026-09-25. Target: API FastAPI `apps/api` (deploy Dokploy, `api-teamku.movoncreative.dev`) dan web Next.js `apps/web` (deploy Vercel). Kode diaudit pada `main` = `origin/main` @ `be3811d` (sudah `git fetch`, tidak ada selisih).

Sumber primer: kode repo ini; dokumentasi Resend (`resend.com/docs`, dibaca lewat versi `.md` Mintlify); halaman `resend.com/pricing`; source SDK resmi `github.com/resend/resend-python` @ `390da5f` (2026-09-18); metadata PyPI `pypi.org/project/resend`; docs Dokploy (`docs.dokploy.com`). Konfigurasi akun Resend dibaca lewat Resend API (MCP, read-only) pada 2026-09-25. Tidak ada email yang dikirim.

---

## Ringkasan (jawaban dulu)

- **Stack API: Python 3.12 + FastAPI, dikelola `uv`.** `fastapi` 0.141.1, `pydantic` 2.13.5, `pydantic-settings` 2.15.0 (`apps/api/pyproject.toml:4-15`, `apps/api/uv.lock:262-264,596-598,686-688`). Image produksi **tidak** memakai `uv`: `Dockerfile` meng-install daftar paket sendiri via `pip` (`apps/api/Dockerfile:3`), jadi dependency baru wajib ditambah di dua tempat.
- **Alur undangan sudah lengkap, hanya transport email-nya palsu.** Tombol memanggil `POST /api/v1/invites`, yang membuat `Invitation` bertoken (berlaku 7 hari, dipersist ke tabel `invitations`) lalu memanggil `send_email()`. `send_email()` hanya menaruh pesan di list in-memory `outbox` dan `logger.info(...)` (`apps/api/src/movon_hr/core/mailer.py:24-35`). Tidak ada SMTP, nodemailer, `SMTP_*`/`MAIL_*`, maupun Resend di repo.
- **Hari ini tombol "berhasil" tapi tidak ada email yang keluar.** Response 200 berisi `invite_url`, lalu web menampilkan toast "Undangan terkirim" plus tautannya (`apps/web/src/app/app/people/page.tsx:80-83`). Log `INFO` dari `movon_hr.mailer` kemungkinan besar juga tidak tampil di produksi karena aplikasi tidak mengonfigurasi logging (inferensi, lihat §1.4).
- **SDK: `resend` (PyPI) v2.47.0**, rilis 2026-09-18. Gagal = **exception** (`ResendError` dan subclass-nya), bukan `{data, error}`. Sukses = `{"id": ...}`. Ada `idempotency_key`, `tags`, `Batch`, `send_async`. Param `react` hanya ada di Node.js SDK.
- **Free tier:** 100 email/hari (reset 00:00 UTC), 3.000/bulan, maks 3 domain terverifikasi, 10 req/detik per team, retensi data 30 hari. Kalau pakai `onboarding@resend.dev`, email hanya bisa dikirim ke email pemilik akun.
- **Akun sudah punya domain terverifikasi `movoncreative.dev`** (region Tokyo), jadi batasan sandbox tidak berlaku. Pengirim `…@movoncreative.dev` bisa mengirim ke Gmail mana pun.
- **Rekomendasi:** ganti isi `core/mailer.py` dengan port `Mailer` yang punya dua adapter, `ConsoleMailer` (dev/test, tetap mengisi `outbox`) dan `ResendMailer`. Pilih adapter lewat `Settings`. Kalau email gagal, **undangan tetap tersimpan**, response tetap 200 dengan `email_status`, dan `invite_url` tetap dikembalikan sebagai fallback. Karyawan baru dibuat saat invite diterima, jadi tidak ada karyawan yang perlu di-rollback.

---

## 1. Codebase

### 1.1 Stack

| Hal | Nilai | Sumber |
|---|---|---|
| Bahasa | Python `>=3.12`, image `python:3.12-slim` | `apps/api/pyproject.toml:4`, `apps/api/Dockerfile:1` |
| Framework | FastAPI 0.141.1 (lock), uvicorn | `apps/api/pyproject.toml:6-7`, `apps/api/uv.lock:262-264` |
| Config | `pydantic-settings` `BaseSettings`, `env_prefix="MOVON_"`, `env_file=".env"` | `apps/api/src/movon_hr/core/settings.py:5-6` |
| Package manager | `uv` (`uv.lock`, `uv run uvicorn …`) | `apps/api/uv.lock:1`, `scripts/run-api.sh:16` |
| Build produksi | `pip install fastapi uvicorn pydantic pydantic-settings argon2-cffi "sqlalchemy[asyncio]" asyncpg` (tanpa pin, tanpa lockfile) | `apps/api/Dockerfile:3` |
| Dev deps | pytest, httpx, ruff | `apps/api/pyproject.toml:17-18` |
| Web | Next.js 15.5.25, React 19, Node 22; `/api/*` di-proxy ke FastAPI via `MOVON_API_ORIGIN` | `apps/web/package.json:5-19`, `apps/web/next.config.ts:9-16` |

### 1.2 Alur "Undang via email" end to end

1. **Web**: modal "Tambah karyawan" (`apps/web/src/app/app/people/page.tsx:172`) punya tombol Batal / Simpan langsung / Undang via email (`page.tsx:200-202`). `invite()` memanggil `api("/invites", {method:"POST", body: payload()})`, lalu toast `"Undangan terkirim"` dengan `Tautan aktivasi: ${result.invite_url}` (`page.tsx:76-88`). Timeout fetch klien 15 detik (`apps/web/src/lib/api.ts:15`).
2. **Proxy**: `/api/:path*` diteruskan ke `${MOVON_API_ORIGIN}/api/v1/:path*` (`apps/web/next.config.ts:16`).
3. **API**: `POST /api/v1/invites` → `create_invite` (`apps/api/src/movon_hr/modules/api.py:1381-1424`):
   - hanya untuk `hr_admin` (`api.py:1388`), dan menolak email yang sudah dipakai dengan 409 (`api.py:1391-1392`);
   - membuat `Invitation(token=token_urlsafe(24), expires_at=now+7 hari, …)` (`api.py:1393-1407`);
   - `invite_url = app_url(f"/invite?token=…")` (`api.py:1408`), dengan `app_url` = `settings.app_base_url` (`api.py:523-524`);
   - `send_email(email, "Undangan Teamku — {tenant}", body plain text)` (`api.py:1409-1418`);
   - `audit("invite.created")` dan return `{email, expires_at, invite_url}` (`api.py:1419-1424`).
4. **Accept**: halaman web `/invite` memanggil `GET /invites/{token}` (`apps/web/src/app/invite/page.tsx:23`, `api.py:1427-1442`), lalu `POST /auth/accept-invite`. **Di tahap inilah `Employee` dibuat** (`api.py:1445-1478`).
5. **Persistence**: middleware menyimpan seluruh store ke Postgres setelah setiap request mutasi dengan status `< 500` (`apps/api/src/movon_hr/main.py:77-93`). Tabel `invitations` didefinisikan di `apps/api/src/movon_hr/core/persistence.py:213-229` (migrasi `apps/api/alembic/versions/0001_tenant_isolation.py:129-142`).

**Model undangan sudah ada:** dataclass `Invitation` (`api.py:84-98`), token sebagai primary key yang disimpan plaintext (`persistence.py:216`), dan `find_invitation` (`api.py:507-512`).

### 1.3 Mailer yang ada

- `core/mailer.py` adalah satu-satunya abstraksi: `EmailMessage(to, subject, body)`, `outbox: list`, `send_email()`, `reset_outbox()`, `last_email_to()` (`apps/api/src/movon_hr/core/mailer.py:16-43`). Docstring-nya menyebut desain ini sengaja "tanpa SMTP" (`mailer.py:1-5`).
- Pemanggil `send_email`: undangan (`api.py:1409`), lupa password (`api.py:1496`), alert kehadiran (`api.py:961`), email cuti (`api.py:624-627`). Semuanya dipanggil **tanpa try/except**.
- Tes bergantung pada `outbox`/`last_email_to` (`apps/api/tests/test_tenancy_auth.py:3,106,125`, `apps/api/tests/test_attendance_alerts.py:5,66`). `reset_outbox()` dipanggil saat reset demo store (`api.py:292`).
- Tidak ada `SMTP_*`, `MAIL_*`, `RESEND_*`, maupun nodemailer di kode atau di `.env.example` (`.env.example:1-12`).
- **Keputusan sebelumnya (belum diimplementasi):** `docs/plans/2026-09-07-001-feat-leave-email-calendar-plan.md` merencanakan SMTP **per tenant** yang disimpan di tabel `email_settings` dan diatur HR dari UI (`plan:23,43,45`). Rencana itu juga mengatakan `MOVON_SMTP_*` tidak diperlukan di v1 (`plan:45`). Aturan yang tetap relevan: `send_email` mempertahankan signature-nya, *mailer menelan error, log exception, tetap append outbox, jangan raise ke caller* (`plan:146,148`), dan tanpa konfigurasi perilakunya tetap log+outbox (`plan:27`). Keputusan Resend (satu akun global via env) **menggantikan sumber transport** dari rencana itu tapi tetap sejalan dengan aturan penanganan error-nya. `docs/runbook.md:3` juga mencatat: "Invite and reset emails currently log to the API process; wire SMTP before production onboarding."

### 1.4 Apa yang terjadi hari ini saat tombol ditekan

1. Undangan dibuat dan dipersist ke Postgres.
2. `send_email` menambah item ke `outbox` in-memory, yang tidak pernah dibersihkan di produksi dan terus tumbuh (`mailer.py:24,33`), lalu memanggil `logger.info("Email queued to=… subject=…\n<body berisi token>")` (`mailer.py:34`).
3. Response 200, dan web menampilkan "Undangan terkirim" beserta tautan aktivasi. **Tidak ada error dan tidak ada email.** HR hanya bisa menyalin tautan dari toast secara manual.
4. *Inferensi, belum terverifikasi*: aplikasi tidak memanggil `logging.basicConfig`/`dictConfig` (hanya `getLogger`: `main.py:38`, `api.py:47`, `mailer.py:13`). Uvicorn hanya mengonfigurasi logger `uvicorn.*`, dan root logger Python default-nya `WARNING`, sehingga baris `INFO` itu kemungkinan besar **tidak muncul** di log Dokploy. Saya mencoba cek via Dokploy `application-readLogs`, tapi hasilnya HTTP 500 sehingga belum bisa dikonfirmasi. Seandainya pun muncul, log itu memuat token undangan dalam plaintext.

### 1.5 Config/env dan URL tautan

- Semua config dibaca oleh `Settings` di `core/settings.py:5-31` dengan prefix `MOVON_`. Validasi hanya sebatas tipe Pydantic, tanpa pengecekan "wajib di produksi".
- Tautan accept dibentuk dari `MOVON_APP_BASE_URL` (default `http://localhost:3000`, `settings.py:17`; `.env.example:7`) dan menunjuk ke `<web>/invite?token=…`. Plan migrasi Vercel mengharuskan nilainya berupa domain Vercel, bukan domain API (`docs/plans/2026-09-12-001-migrate-web-to-vercel-plan.md:134,162`).

---

## 2. Resend Python SDK

| Hal | Fakta | Sumber |
|---|---|---|
| Paket | `resend` v**2.47.0**, upload 2026-09-18, `requires_python >=3.7`; deps `requests>=2.31.0`, `typing_extensions>=4.4.0`, extra `async` → `httpx>=0.24.0` | https://pypi.org/project/resend/ , `resend/version.py` di https://github.com/resend/resend-python |
| Install | `pip install resend` (async: `pip install resend[async]`). Di repo ini: `uv add "resend[async]"` + tambah ke `apps/api/Dockerfile:3` | https://resend.com/docs/send-with-python , README resend-python |
| Init | `resend.api_key = …`. Default-nya sudah membaca env `RESEND_API_KEY`, dan `RESEND_API_URL` default `https://api.resend.com` | `resend/__init__.py:105-106` |
| Kirim | `resend.Emails.send(params, options=None)` / `await resend.Emails.send_async(params, options)` | `resend/emails/_emails.py:492,644` |
| Params | `from`, `to` (str/list, maks 50), `subject`, `html`, `text`, `cc`, `bcc`, `reply_to`, `headers`, `attachments`, `tags`, `scheduled_at`, `template{id, variables}`. **`react` hanya ada di Node.js SDK** | `_emails.py:215-270`, https://resend.com/docs/api-reference/emails/send-email |
| Return | Sukses: `{"id": "49a3999c-…"}`. Gagal: **raise exception** | https://resend.com/docs/send-with-python |
| Exceptions | Base `ResendError` (atribut `code`, `error_type`, `message`, `suggested_action`, `headers`). Mapping: 400/422 `validation_error` → `ValidationError`; 422 `missing_required_field(s)` → `MissingRequiredFieldsError`; 401 `missing_api_key` → `MissingApiKeyError`; 403 `invalid_api_key` → `InvalidApiKeyError`; 429 `rate_limit_exceeded`/`daily_quota_exceeded`/`monthly_quota_exceeded` → `RateLimitError`; 500 → `ApplicationError`. Tipe lain, termasuk **403 `validation_error` untuk domain belum terverifikasi atau sandbox**, jatuh ke `ResendError` generik. Param yang kurang memunculkan `ValueError` | `resend/exceptions.py:10-40,203-218,254-285`, https://resend.com/docs/api-reference/errors |
| Timeout | Default 30 dtk untuk `RequestsClient`/`HTTPXClient(timeout=30)`; bisa di-override via `resend.default_async_http_client = resend.HTTPXClient(timeout=…)` | `resend/http_client_requests.py:13`, `resend/http_client_httpx.py:13`, README |
| Idempotency | `options={"idempotency_key": "..."}` dikirim sebagai header `Idempotency-Key`. Maks 256 char, berlaku 24 jam; didukung di `POST /emails` dan `/emails/batch`. Error 409 `concurrent_idempotent_requests` / `invalid_idempotent_request` | `resend/request.py:82-83`, https://resend.com/docs/dashboard/emails/idempotency-keys |
| Tags | `[{"name": ..., "value": ...}]`, hanya ASCII huruf/angka/`_`/`-`, maks 256 char | `resend/emails/_tag.py` |
| Batch | `resend.Batch.send([...], options)`, maks 100 email per call, tanpa attachments; `batch_validation: strict\|permissive`. Satu batch dihitung 1 request untuk rate limit | `resend/emails/_batch.py:45-64,81`, https://resend.com/docs/api-reference/emails/send-batch-emails , https://resend.com/docs/knowledge-base/account-quotas-and-limits |

**Catatan async:** `Emails.send` memakai `requests` yang blocking. Kalau dipanggil langsung dari `async def create_invite`, event loop uvicorn ikut terblokir. Pakai `send_async` (extra `async`) atau `run_in_threadpool`.

### Templating: rekomendasi

| Opsi | Cocok? |
|---|---|
| **React Email** | Tidak cocok untuk sekarang. Param `react` hanya ada di Node SDK (https://resend.com/docs/api-reference/emails/send-email). Di Python harus render ke HTML lewat toolchain Node terpisah (https://resend.com/docs/knowledge-base/template-emails-with-react-email), padahal API ini murni Python. |
| **Resend hosted Templates** | Bisa (`template: {id, variables}`, harus di-*publish*, tidak boleh digabung dengan `html`/`text`) (https://resend.com/docs/dashboard/templates/introduction , https://resend.com/docs/api-reference/emails/send-batch-emails). Kekurangannya: isi email tinggal di dashboard (di luar git/review/tes)). |
| **HTML + text di Python** (direkomendasikan) | Cukup string template di repo dengan `html.escape()` untuk nama/tenant, kirim `html` + `text`. Bisa dites via `ConsoleMailer`/`outbox`, tanpa dependency baru. Body plain text yang ada (`api.py:1413-1416`) bisa langsung dipakai sebagai `text`. |

---

## 3. Free tier, sandbox, domain

| Batas (Free, Transactional) | Nilai | Sumber |
|---|---|---|
| Harian | 100 email/hari, hari kalender UTC (reset 00:00 UTC), **termasuk email masuk**; setiap alamat `to/cc/bcc` dihitung terpisah | https://resend.com/docs/knowledge-base/account-quotas-and-limits , https://resend.com/pricing |
| Bulanan | 3.000 email/bulan | idem |
| Domain | maks **3** domain terverifikasi | idem |
| Rate limit | 10 req/detik **per team** (bukan per API key), tanpa burst; 429 `rate_limit_exceeded`. Header `ratelimit-*`, `x-resend-daily-quota`, `x-resend-monthly-quota` | https://resend.com/docs/api-reference/rate-limit |
| Kuota habis | 429 `daily_quota_exceeded` / `monthly_quota_exceeded` | https://resend.com/docs/api-reference/errors |
| Retensi | 30 hari (semua plan kecuali Enterprise) | https://resend.com/docs/knowledge-base/account-quotas-and-limits |
| Kesehatan akun | bounce < 4%, spam < 0.08%; di atas itu pengiriman bisa di-pause | idem |
| Pro | $20/bln untuk 50k email, tanpa batas harian, 10 domain | https://resend.com/pricing |

- **Sandbox `resend.dev`**: "can only send emails to the email address associated with your Resend account". Kalau dilanggar, hasilnya 403 "You can only send testing emails to your own email address…" (https://resend.com/docs/knowledge-base/403-error-resend-dev-domain).
- **Alamat tes**: `delivered@`, `bounced@`, `complained@`, `suppressed@resend.dev`, mendukung label `+` (kecuali `suppressed`). **Tetap dihitung ke kuota** (https://resend.com/docs/dashboard/emails/send-test-emails).
- **Verifikasi domain**: tambahkan record DKIM dan SPF (`TXT` dan `MX` atau `CNAME`) persis seperti yang di-generate Resend. Return-Path default `send.<domain>`. Jangan aktifkan proxy Cloudflare untuk CNAME. Biasanya selesai dalam ≤15 menit, paling lama 72 jam. DMARC dianjurkan setelah domain terverifikasi. Resend "strongly recommend" memakai subdomain (mis. `notifications.example.com`), dan setiap subdomain diverifikasi terpisah (https://resend.com/docs/add-a-domain , https://resend.com/docs/knowledge-base/is-it-better-to-send-emails-from-a-subdomain-or-the-root-domain). Setelah domain terverifikasi, alamat apa pun di domain itu bisa dipakai sebagai pengirim (https://resend.com/docs/dashboard/domains/introduction).
- **Untuk mengundang email bebas (Gmail dsb.) wajib ada domain terverifikasi** sebagai `from`. Sandbox tidak cukup.

## 4. Konfigurasi Resend saat ini

Sumber: Resend API via MCP (read-only), dibaca 2026-09-25. ID sengaja tidak dicantumkan.

| Item | Kondisi |
|---|---|
| Domain | `movoncreative.dev` (dibuat 2026-09-25). *Verified*, sending aktif, receiving mati, open/click tracking mati, region `ap-northeast-1` (Tokyo) |
| API key | `teamku-dev-api-key` (2026-09-25). **Permission dan scope domain tidak diketahui**, karena endpoint list tidak menampilkannya |
| Webhook | 0 |
| Email terkirim | belum ada |

Implikasi:
- **Sandbox tidak berlaku.** Dengan `movoncreative.dev` sudah verified, `from` seperti `Teamku <noreply@movoncreative.dev>` bisa mengirim ke alamat mana pun (https://resend.com/docs/dashboard/domains/introduction). **Keputusan (2026-09-25): sementara pakai root, `noreply@movoncreative.dev`.** Resend menyarankan subdomain untuk isolasi reputasi, dan root `movoncreative.dev` juga menaungi project lain (`phantomx`, `finsight`, `api-widget`). Sebelum produksi, pindah ke `teamku.movoncreative.dev`: verifikasi domain baru, ganti `MOVON_MAIL_FROM`, lalu hapus root dari Resend bila tidak dipakai. Tidak perlu ubah kode. Free tier mengizinkan maks 3 domain (https://resend.com/docs/knowledge-base/account-quotas-and-limits).
- **Kuota dan rate limit berlaku per team.** Batas 100/hari, 3.000/bulan, dan 10 req/detik dihitung untuk seluruh team Resend (idem, https://resend.com/docs/api-reference/rate-limit), jadi pemakaian lain di team yang sama ikut mengurangi kuota Teamku.
- **Batasi `teamku-dev-api-key`.** Resend mendukung `permission: sending_access` + `domain_id` (https://resend.com/docs/api-reference/api-keys/create-api-key). Karena scope key yang ada tidak bisa dipastikan, sebaiknya buat ulang (atau cek di dashboard) key dengan akses *sending only* untuk `movoncreative.dev` saja, supaya key yang bocor dari server API tidak bisa mengelola domain atau key lain di akun.
- **Region Tokyo.** Region menentukan dari mana email *dikirim*, bukan lokasi data (data tetap di AS). Pilihan region hanya us-east-1, eu-west-1, sa-east-1, ap-northeast-1 (https://resend.com/docs/dashboard/domains/regions), jadi Tokyo adalah pilihan terdekat untuk penerima di Indonesia. Latensi panggilan API dari server Dokploy tetap ke `https://api.resend.com` (`resend/__init__.py:106`). Docs tidak menyebut adanya endpoint API per region. Pindah region berarti hapus lalu tambah ulang domain (idem).

---

## 5. Rekomendasi integrasi

### 5.1 Env vars (ikuti prefix `MOVON_` di `settings.py:6`)

| Env | Contoh | Catatan |
|---|---|---|
| `MOVON_MAIL_PROVIDER` | `console` \| `resend` | default `console`, sehingga dev/tes tidak butuh jaringan |
| `MOVON_RESEND_API_KEY` | (secret) | field `resend_api_key: SecretStr \| None` di `Settings`. SDK bisa membaca `RESEND_API_KEY` sendiri (`resend/__init__.py:105`), tapi `MOVON_` membuat semua config lewat `Settings`. Pilih salah satu nama dan konsisten |
| `MOVON_MAIL_FROM` | `Teamku <noreply@movoncreative.dev>` | harus domain verified |
| `MOVON_MAIL_REPLY_TO` | opsional | |
| `MOVON_APP_BASE_URL` | domain Vercel | sudah ada (`settings.py:17`) |

Tambahkan `model_validator`: jika `mail_provider == "resend"`, maka `resend_api_key` dan `mail_from` wajib diisi (fail fast saat startup). Update `.env.example`.

### 5.2 Letak file dan interface

Konvensinya: adapter infrastruktur ada di `core/` (`core/mailer.py`, `core/ai_provider.py` yang memisahkan boundary provider dengan `FakePolicyProvider` + `ProviderError`, `core/ai_provider.py:1-24`).

- `apps/api/src/movon_hr/core/mailer.py`: port + adapter + factory. **Pertahankan** `send_email`, `outbox`, `reset_outbox`, dan `last_email_to` supaya tes lama tetap hijau.
- `apps/api/src/movon_hr/core/email_templates.py`: `invite_email(name, inviter, tenant, url) -> (subject, html, text)`.
- `apps/api/tests/test_mailer.py`: adapter Resend dengan fake client, dan skenario error tidak meledak.

```python
@dataclass
class EmailMessage:
    to: str; subject: str; body: str            # body = text, kompatibel dengan tes lama
    html: str | None = None
    tags: dict[str, str] = field(default_factory=dict)
    idempotency_key: str | None = None

@dataclass(frozen=True)
class SendResult:
    ok: bool; provider_id: str | None = None; error: str | None = None

class Mailer(Protocol):
    async def send(self, msg: EmailMessage) -> SendResult: ...

class ConsoleMailer:   # outbox.append + logger.info (hanya dev)
class ResendMailer:    # await resend.Emails.send_async(params, {"idempotency_key": ...})
                       # except resend.exceptions.ResendError as e -> SendResult(ok=False, error=e.error_type)

async def deliver(msg: EmailMessage) -> SendResult:  # menelan exception, selalu log hasil
```

Untuk `ResendMailer`: set `resend.default_async_http_client = resend.HTTPXClient(timeout=10)`, di bawah timeout klien web 15 dtk (`apps/web/src/lib/api.ts:15`). Gunakan `idempotency_key=f"invite/{invitation.token}"` dan `tags=[{"name":"type","value":"invite"},{"name":"tenant","value":<tenant_id yang sudah disanitasi>}]`. Pemanggil lain (reset, alert, cuti) bisa tetap memakai wrapper sinkron `send_email` sampai dimigrasi. Karena rencana 2026-09-07 menetapkan mailer tidak boleh raise ke caller (`plan:146,148`), `deliver` wajib menelan error.

### 5.3 Pemanggilan dari `create_invite` dan penanganan gagal

- Simpan undangan dulu (sudah terjadi di `api.py:1407`), lalu `result = await deliver(invite_email(...))`.
- **Jangan rollback, jangan 5xx.** Karyawan belum dibuat saat undang (baru dibuat di `api.py:1459-1473`). Jika merespons ≥500, middleware tidak menyimpan store (`main.py:83`) padahal undangan sudah ada di memori, sehingga state jadi tidak konsisten. Return 200 dengan `{"email_status": "sent" | "failed", "invite_url": ...}`, lalu `audit("invite.email_failed")` jika gagal.
- Web (`page.tsx:83`): toast berbeda untuk `failed`, misalnya "Undangan dibuat, email gagal terkirim, salin tautan ini". Pertimbangkan endpoint "kirim ulang undangan" (idempotency key baru per percobaan).
- Kuota 429 (`RateLimitError`) juga diperlakukan sebagai `failed`, tanpa retry sinkron.
- `ConsoleMailer` jangan dipakai di produksi (token ikut ter-log), dan `outbox` perlu dibatasi (mis. `deque(maxlen=…)`).

### 5.4 Set env di Dokploy

App API: `teamku-api-8umq6u` (domain `api-teamku.movoncreative.dev`). Buka Dokploy → project → service API → tab **Environment**, tambahkan `MOVON_MAIL_PROVIDER=resend`, `MOVON_MAIL_FROM=…`, `MOVON_RESEND_API_KEY=<paste dari dashboard Resend>`, lalu **Save** dan **Redeploy**. Dokploy mendukung variabel level service, environment, dan project (shared, `${{project.X}}`), serta secrets provider eksternal (https://docs.dokploy.com/docs/core/variables). Taruh key di level **service**, jangan di project-shared. Jangan commit key, dan jangan salin ke Vercel karena web tidak butuh. Wajib juga menambah `resend[async]` ke `apps/api/Dockerfile:3`, kalau tidak build produksi akan `ImportError`.

---

## 6. Pertanyaan terbuka / risiko

1. **Domain pengirim**: *diputuskan* sementara root `noreply@movoncreative.dev`; pindah ke `teamku.movoncreative.dev` sebelum produksi. Yang masih terbuka: siapa yang memegang DNS-nya, dan DMARC belum ada (`_dmarc.movoncreative.dev` kosong per 2026-09-25), jadi perlu ditambah minimal `v=DMARC1; p=none;`.
2. **Kepemilikan akun**: siapa owner akun Resend ini? Untuk produksi sebaiknya team Resend terpisah agar kuota, rate limit, reputasi, dan akses key terisolasi.
3. **Scope `teamku-dev-api-key`** belum diketahui (§4). Perlu dicek di dashboard atau diganti dengan key `sending_access` + domain `movoncreative.dev`.
4. **Kuota**: 100/hari (termasuk inbound, dihitung per team) cukup untuk dev, tapi onboarding massal satu tenant bisa langsung habis. Produksi perlu Pro ($20/bln) atau akun terpisah.
5. **Nama env**: `MOVON_RESEND_API_KEY` (konsisten dengan `Settings`) atau `RESEND_API_KEY` (default SDK)? Pilih satu.
6. **Rencana SMTP per tenant** (`docs/plans/2026-09-07-001-feat-leave-email-calendar-plan.md`) masih berstatus `ready` (`plan:5`). Apakah Resend global menggantikannya atau menjadi fallback platform bila tenant tidak mengisi SMTP?
7. **Logging**: pastikan `logging` dikonfigurasi di `main.py` supaya kegagalan kirim terlihat di Dokploy, tanpa mencetak token atau body.
8. **Build produksi tanpa lockfile** (`apps/api/Dockerfile:3`): versi `resend` tidak dipin di image, sehingga produksi dan `uv.lock` bisa berbeda.
9. **Tanpa webhook**, bounce/complaint tidak tercatat di Teamku. Jika bounce > 4%, seluruh akun bisa di-pause.
