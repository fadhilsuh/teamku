// Browser requests stay same-origin. Next.js forwards this prefix to FastAPI,
// avoiding localhost/IPv6 mismatches and keeping CORS out of the UI contract.
const BASE = "/api";
export async function api<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const response = await fetch(`${BASE}${path}`, { ...init, headers: { "Content-Type": "application/json", ...(token ? { "X-Demo-User": token } : {}), ...(init.headers || {}) } });
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || "Terjadi kesalahan");
  return response.json();
}
