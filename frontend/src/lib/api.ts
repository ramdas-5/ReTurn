"use client";

/** Browser API client. Uses the same-origin /api/v1 rewrite to Flask. */

export class ApiError extends Error {
  code: string;
  status: number;
  fields: Record<string, string>;

  constructor(message: string, code = "request_failed", status = 0, fields: Record<string, string> = {}) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.fields = fields;
  }
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.split("; ").find((entry) => entry.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.split("=").slice(1).join("=")) : null;
}

let csrfRequest: Promise<string> | null = null;

export async function ensureCsrfToken(): Promise<string> {
  const existing = readCookie("rt_csrf");
  if (existing) return existing;
  if (!csrfRequest) {
    csrfRequest = fetch("/api/v1/auth/csrf", {
      credentials: "same-origin",
      cache: "no-store",
    })
      .then(async (response) => {
        const json = await response.json();
        return (json?.data?.csrf_token as string) ?? "";
      })
      .finally(() => {
        csrfRequest = null;
      });
  }
  return csrfRequest;
}

type Options = {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
};

async function requestRaw(path: string, options: Options = {}) {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET") {
    headers["X-CSRF-Token"] = await ensureCsrfToken();
  }
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, {
      method,
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      credentials: "same-origin",
      cache: "no-store",
      signal: options.signal,
    });
  } catch (error) {
    throw new ApiError(
      "The ReTurn API could not be reached. Check that the Flask service is running.",
      "network_error",
      0,
    );
  }
  let payload: any = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) {
    const error = payload?.error ?? {};
    throw new ApiError(
      error.message ?? `Request failed (${response.status}).`,
      error.code ?? "request_failed",
      response.status,
      error.fields ?? {},
    );
  }
  return payload;
}

export async function apiGet<T>(path: string): Promise<T> {
  const payload = await requestRaw(path);
  return payload?.data as T;
}

export async function apiGetList<T>(
  path: string,
): Promise<{ data: T[]; meta?: { unread_count?: number; total?: number } }> {
  const payload = await requestRaw(path);
  return { data: (payload?.data ?? []) as T[], meta: payload?.meta };
}

export async function apiPost<T>(path: string, body: unknown = {}): Promise<T> {
  const payload = await requestRaw(path, { method: "POST", body });
  return payload?.data as T;
}

export async function apiPatch<T>(path: string, body: unknown = {}): Promise<T> {
  const payload = await requestRaw(path, { method: "PATCH", body });
  return payload?.data as T;
}
