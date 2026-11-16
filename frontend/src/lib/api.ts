"use client";

/** Browser API client. Same-origin `/api/v1` is proxied to Flask. */

export class ApiError extends Error {
  code: string;
  status: number;
  fields: Record<string, string>;
  details: Record<string, unknown>;

  constructor(
    message: string,
    code = "request_failed",
    status = 0,
    fields: Record<string, string> = {},
    details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.fields = fields;
    this.details = details;
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

type Method = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
type Options = { method?: Method; body?: unknown; signal?: AbortSignal; form?: FormData };

async function requestRaw(path: string, options: Options = {}) {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET") headers["X-CSRF-Token"] = await ensureCsrfToken();
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, {
      method,
      headers,
      body: options.form ?? (options.body !== undefined ? JSON.stringify(options.body) : undefined),
      credentials: "same-origin",
      cache: "no-store",
      signal: options.signal,
    });
  } catch {
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
      error.details ?? {},
    );
  }
  return payload;
}

export async function apiGet<T>(path: string): Promise<T> {
  return (await requestRaw(path))?.data as T;
}

export async function apiGetList<T>(
  path: string,
): Promise<{ data: T[]; meta?: Record<string, any> }> {
  const payload = await requestRaw(path);
  return { data: (payload?.data ?? []) as T[], meta: payload?.meta };
}

export async function apiPost<T>(path: string, body: unknown = {}): Promise<T> {
  return (await requestRaw(path, { method: "POST", body }))?.data as T;
}

export async function apiPut<T>(path: string, body: unknown = {}): Promise<T> {
  return (await requestRaw(path, { method: "PUT", body }))?.data as T;
}

export async function apiPatch<T>(path: string, body: unknown = {}): Promise<T> {
  return (await requestRaw(path, { method: "PATCH", body }))?.data as T;
}

export async function apiDelete<T>(path: string): Promise<T> {
  return (await requestRaw(path, { method: "DELETE" }))?.data as T;
}

export async function apiUpload<T>(path: string, form: FormData): Promise<T> {
  return (await requestRaw(path, { method: "POST", form }))?.data as T;
}
