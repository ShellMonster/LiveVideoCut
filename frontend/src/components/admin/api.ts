export const API_BASE = import.meta.env.VITE_API_URL || "";

export async function fetchJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const resp = await fetch(url, { signal });
  const contentType = resp.headers.get("content-type") || "";
  if (!resp.ok || !contentType.includes("application/json")) {
    throw new Error(`Unexpected response for ${url}`);
  }
  return (await resp.json()) as T;
}

export async function sendJson<T>(url: string, payload: unknown, method = "POST"): Promise<T> {
  const resp = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const contentType = resp.headers.get("content-type") || "";
  if (!resp.ok || !contentType.includes("application/json")) {
    throw new Error(`Unexpected response for ${url}`);
  }
  return (await resp.json()) as T;
}
