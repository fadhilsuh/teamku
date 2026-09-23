// Browser requests stay same-origin. Next.js forwards this prefix to FastAPI,
// avoiding localhost/IPv6 mismatches and keeping CORS out of the UI contract.
const BASE = "/api";

const publicAuthPaths = new Set([
  "/auth/login",
  "/auth/signup",
  "/auth/forgot-password",
  "/auth/reset-password",
  "/auth/accept-invite",
]);

export class ApiError extends Error {
  status: number;
  fieldErrors: Record<string, string>;

  constructor(message: string, status: number, fieldErrors: Record<string, string> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fieldErrors = fieldErrors;
  }
}

const fieldLabels: Record<string, string> = {
  company_name: "Nama perusahaan", admin_name: "Nama Anda", email: "Email kerja",
  password: "Kata sandi", new_password: "Kata sandi baru", current_password: "Kata sandi saat ini",
};

function responseError(payload: unknown, status: number): ApiError {
  const fallback = "Data belum dapat diproses. Periksa isian Anda lalu coba lagi.";
  if (status >= 500) return new ApiError("Layanan sedang mengalami gangguan. Silakan coba lagi beberapa saat lagi.", status);
  if (status === 429) return new ApiError("Terlalu banyak percobaan. Tunggu beberapa saat sebelum mencoba lagi.", status);
  const detail = payload && typeof payload === "object" && "detail" in payload ? payload.detail : undefined;
  if (typeof detail === "string" && detail.trim() && !detail.includes("[object Object]")) {
    return new ApiError(detail.trim(), status);
  }
  const fields: Record<string, string> = Object.create(null);
  const messages: string[] = [];
  if (Array.isArray(detail)) {
    for (const item of detail) {
      if (!item || typeof item !== "object") continue;
      const field = Array.isArray(item.loc) ? item.loc.at(-1) : undefined;
      const label = typeof field === "string" && Object.hasOwn(fieldLabels, field) ? fieldLabels[field] : "Isian";
      let message = `${label} tidak valid. Periksa kembali isian Anda.`;
      if (item.type === "missing") message = `${label} wajib diisi.`;
      if (item.type === "string_too_short" && Number.isInteger(item.ctx?.min_length)) message = `${label} minimal ${item.ctx.min_length} karakter.`;
      if (item.type === "string_too_long" && Number.isInteger(item.ctx?.max_length)) message = `${label} maksimal ${item.ctx.max_length} karakter.`;
      messages.push(message);
      if (typeof field === "string" && !Object.hasOwn(fields, field)) fields[field] = message;
    }
  }
  return new ApiError([...new Set(messages)].join(" ") || fallback, status, fields);
}

export async function api<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const controller = init.signal ? undefined : new AbortController();
  const timeout = controller ? window.setTimeout(() => controller.abort(), 15_000) : undefined;
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      credentials: "include",
      signal: init.signal || controller?.signal,
      headers: {
        "Content-Type": "application/json",
        ...(token ? {"X-Demo-User": token} : {}),
        ...(init.headers || {}),
      },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("Server tidak merespons. Silakan coba lagi.");
    }
    throw new Error("Tidak dapat terhubung ke server. Periksa koneksi internet Anda lalu coba lagi.");
  } finally {
    if (timeout) window.clearTimeout(timeout);
  }
  if (!response.ok) {
    if (
      response.status === 401 &&
      typeof window !== "undefined" &&
      !publicAuthPaths.has(path) &&
      !window.location.pathname.startsWith("/login") &&
      !window.location.pathname.startsWith("/signup") &&
      !window.location.pathname.startsWith("/invite") &&
      !window.location.pathname.startsWith("/forgot-password") &&
      !window.location.pathname.startsWith("/reset-password")
    ) {
      localStorage.removeItem("movon_user");
      window.location.assign("/login");
    }
    throw responseError(await response.json().catch(() => null), response.status);
  }
  return response.json();
}
