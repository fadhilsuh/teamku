// Browser requests stay same-origin. Next.js forwards this prefix to FastAPI,
// avoiding localhost/IPv6 mismatches and keeping CORS out of the UI contract.
const BASE = "/api";
export async function api<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const controller = init.signal ? undefined : new AbortController();
  const timeout = controller ? window.setTimeout(() => controller.abort(), 15_000) : undefined;
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, { ...init, signal: init.signal || controller?.signal, headers: { "Content-Type": "application/json", ...(token ? { "X-Demo-User": token } : {}), ...(init.headers || {}) } });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw new Error("Server tidak merespons. Silakan coba lagi.");
    throw error;
  } finally {
    if (timeout) window.clearTimeout(timeout);
  }
  if (!response.ok) {
    if (response.status === 401 && token && typeof window !== "undefined" && localStorage.getItem("movon_user") === token) {
      localStorage.removeItem("movon_user");
      window.location.assign("/login");
    }
    throw new Error((await response.json().catch(() => ({}))).detail || "Terjadi kesalahan");
  }
  return response.json();
}
