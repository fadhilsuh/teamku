// Next membakukan rewrites() ke routes-manifest.json pada waktu build, jadi
// MOVON_API_ORIGIN dibutuhkan saat build dan bukan saat runtime. Bila kosong,
// build tetap "sukses" tetapi mem-proxy /api/* ke localhost — gagal senyap
// yang mahal untuk didiagnosis.
//
// Guard ini tidak bisa ditaruh di next.config.ts: "next lint" dan "next build"
// sama-sama melaporkan phase-production-build dan NODE_ENV=production,
// sehingga keduanya mustahil dibedakan dari dalam config.
//
// Hanya aktif di Vercel/CI supaya build lokal tetap bisa memakai default
// localhost, dan developer yang menyimpan env di .env.local tidak kena
// false positive (skrip Node tidak memuat .env.local).
if ((process.env.VERCEL || process.env.CI) && !process.env.MOVON_API_ORIGIN) {
  console.error(
    "\nMOVON_API_ORIGIN belum di-set.\n" +
      "Set di Vercel > Settings > Environment Variables untuk Production,\n" +
      "Preview, dan Development, lalu deploy ulang.\n",
  );
  process.exit(1);
}
