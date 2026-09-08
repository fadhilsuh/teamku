---
title: Leave email and calendar sync
type: requirements
date: 2026-09-07
status: ready
---

# Leave email and calendar sync

## Summary

HR mengatur email perusahaan dari Pengaturan. Setelah itu, permohonan cuti/izin mengirim email ke orang yang harus bertindak. Setelah disetujui, tanggal cuti muncul sebagai Out of Office di kalender karyawan dan sebagai event di kalender bersama tim.

## Problem Frame

Cuti hari ini hanya hidup di Teamku. Manager dapat inbox in-app saat ada pengajuan, karyawan dapat inbox saat keputusan keluar, dan email undangan/reset/alert kehadiran hanya tertulis di log proses. Tidak ada SMTP sungguhan, tidak ada event kalender. Akibatnya tim tidak melihat siapa yang off di Outlook atau Google Calendar, dan manager yang tidak membuka Teamku bisa melewatkan permohonan.

## Key Decisions

- **Email dulu, kalender kemudian.** Tanpa SMTP yang bisa dikonfigurasi, undangan dan cuti tetap tidak sampai ke inbox sungguhan.
- **Kalender hanya setelah disetujui.** Event pending yang ditolak menjadi cuti hantu di kalender tim.
- **Dua kalender, satu sumber kebenaran.** Teamku menulis OOO di kalender karyawan dan salinan di kalender tim. Ubah di Outlook/Google tidak mengubah cuti di Teamku.
- **Satu provider per tenant.** HR memilih Microsoft 365 atau Google Calendar, bukan keduanya sekaligus.
- **Alasan cuti tidak masuk judul kalender.** Judul cukup `Cuti · Nama`. Detail tetap di Teamku.
- **Gagal kirim email atau kalender tidak membatalkan keputusan cuti.** Approval tetap tersimpan; kegagalan saluran dicatat.

## Actors

- A1. Karyawan — mengajukan atau membatalkan cuti/izin sendiri.
- A2. Manager — menyetujui atau menolak permohonan di departemennya.
- A3. HR Admin — mengatur email dan kalender di Pengaturan; bisa memutuskan permohonan semua departemen.
- A4. Tim — melihat siapa yang off lewat kalender bersama, tanpa membuka alasan cuti.

## Requirements

**Email settings**

- R1. HR Admin mengatur konfigurasi email tenant dari `/app/settings`, terpisah dari pengaturan kantor/geofence.
- R2. Field wajib: toggle aktif, from-name, from-address, host SMTP, port, username, password, encryption (none / STARTTLS / TLS).
- R3. GET settings tidak mengembalikan password SMTP. UI menampilkan placeholder bahwa password sudah tersimpan.
- R4. HR bisa mengirim email uji ke alamatnya sendiri tanpa mengubah cuti atau undangan.
- R5. Jika email mati atau SMTP belum diisi, `send_email` tetap menulis log/outbox seperti sekarang. Fitur cuti dan undangan tidak error.

**Leave email**

- R6. Saat cuti diajukan, email + inbox pergi ke manager satu departemen dan semua HR Admin aktif.
- R7. Saat disetujui atau ditolak, email + inbox pergi ke karyawan pemohon, dengan catatan keputusan.
- R8. Saat pending dibatalkan, email pergi ke manager/HR yang tadi diberitahu. Saat approved dibatalkan, email pergi ke karyawan, manager departemen, dan HR Admin.
- R9. Isi email bahasa Indonesia, teks polos, berisi nama, tanggal, durasi hari kerja, dan tautan ke `/app/approvals` atau `/app/time/time-off`. Alasan cuti boleh ada di email penerima yang berwenang (manager/HR), tidak di kalender.

**Calendar**

- R10. Setelah status menjadi `approved`, Teamku membuat event Out of Office / Busy di kalender karyawan dan event all-day di kalender bersama tim.
- R11. HR memilih satu provider (Microsoft 365 atau Google) dan menghubungkan tenant sekali lewat admin consent. Karyawan tidak connect kalender satu-satu.
- R12. HR menunjuk kalender bersama (satu per perusahaan di v1; filter visual per departemen lewat judul `Cuti · Nama`).
- R13. Pembatalan atau perubahan rentang tanggal pada cuti approved menghapus atau mengganti kedua event.
- R14. Penolakan tidak membuat event. Permohonan pending tidak membuat event.
- R15. Sync kalender gagal tidak mengubah status cuti. Status sync terlihat untuk HR (berhasil / gagal / belum).

## Key Flows

- F1. HR menyalakan email
  - **Trigger:** HR membuka Pengaturan → Email.
  - **Actors:** A3
  - **Steps:** Isi SMTP, simpan, kirim email uji ke dirinya. Toggle aktif.
  - **Outcome:** Undangan, reset password, alert kehadiran, dan email cuti memakai SMTP tenant.
  - **Covered by:** R1, R2, R3, R4, R5

- F2. Karyawan mengajukan cuti
  - **Trigger:** Submit di Agenda & Cuti.
  - **Actors:** A1, A2, A3
  - **Steps:** Simpan `pending`. Inbox + email ke manager departemen dan HR. Tidak ada event kalender.
  - **Outcome:** Approver bisa bertindak dari email tanpa membuka Teamku dulu.
  - **Covered by:** R6, R14

- F3. Manager menyetujui
  - **Trigger:** Setujui di Persetujuan.
  - **Actors:** A2, A1, A4
  - **Steps:** Status `approved`. Email ke karyawan. Tulis OOO karyawan + event kalender tim.
  - **Outcome:** Tim melihat blok tanggal di kalender kerja.
  - **Covered by:** R7, R10, R15

- F4. Cuti approved dibatalkan
  - **Trigger:** Karyawan membatalkan di Agenda & Cuti.
  - **Actors:** A1, A2, A3, A4
  - **Steps:** Status `cancelled`. Email ke karyawan, manager, HR. Hapus kedua event kalender.
  - **Outcome:** Kalender kembali kosong pada tanggal itu.
  - **Covered by:** R8, R13

## Acceptance Examples

- AE1. Covers R5 / F1. SMTP belum diisi. Karyawan mengajukan cuti. Permohonan tersimpan. Email tercatat di outbox/log. Tidak ada error 500.
- AE2. Covers R6 / F2. Raka (Engineering) mengajukan 10–11 Oktober. Manager Engineering dan HR Admin menerima email. Manager Sales tidak.
- AE3. Covers R14 / F2. Setelah AE2, belum ada event di kalender karyawan atau kalender tim.
- AE4. Covers R7 / R10 / F3. Manager menyetujui. Raka menerima email keputusan. Event `Cuti · Raka Pratama` muncul di OOO-nya dan di kalender tim untuk 10–11 Oktober. Alasan tidak ada di judul event.
- AE5. Covers R13 / F4. Raka membatalkan cuti approved. Kedua event hilang. Manager dan HR menerima email pembatalan.
- AE6. Covers R15. Graph/Google timeout saat approve. Status cuti tetap `approved`. Sync ditandai gagal. HR bisa memicu ulang dari Pengaturan atau detail permohonan.

## Scope Boundaries

**In scope**

- Panel Email di Pengaturan (HR Admin)
- SMTP tenant di belakang `send_email` yang sudah ada
- Email siklus cuti: ajukan, setujui, tolak, batalkan
- Panel Kalender di Pengaturan: pilih M365 atau Google, admin consent, pilih kalender tim
- Tulis/hapus/ganti event setelah approve

**Deferred for later**

- Campur Outlook + Gmail dalam satu tenant (OAuth per karyawan)
- Satu kalender bersama per departemen
- Sync dua arah dari Outlook/Google ke Teamku
- Tipe event terpisah untuk izin vs cuti
- Agenda harian check-in masuk kalender
- Encrypted-at-rest untuk password SMTP (v1: jangan echo secret; simpan terpisah dari response)

**Outside this product's identity**

- Teamku sebagai server email atau klien kalender penuh
- Invite meeting ke seluruh perusahaan
- Hukuman otomatis jika orang cuti tetap check-in

## Dependencies / Assumptions

- Alamat email karyawan adalah akun kerja di tenant M365 atau Google yang sama.
- SMTP yang diisi HR bisa mengirim ke domain kerja itu.
- Admin consent Graph/Google memberi izin tulis kalender pengguna dan kalender bersama.
- Redis/Celery belum ada di kode. v1 sync kalender berjalan di request approve/cancel, gagal-aman.

## Outstanding Questions

- Resolve before implementation if it blocks UX: apakah kalender tim satu untuk seluruh perusahaan (keputusan v1: ya) sudah diterima HR Movon?
- Deferred: provider default untuk tenant baru — kosong sampai HR memilih.
