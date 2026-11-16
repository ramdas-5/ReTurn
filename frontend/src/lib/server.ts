import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { AuthMe, Role } from "@/lib/types";

const API_BASE =
  process.env.API_INTERNAL_URL ?? process.env.FLASK_API_URL ?? "http://127.0.0.1:5000";

export class ServerUnauthorizedError extends Error {}

export async function serverFetch<T>(path: string): Promise<T> {
  // Read cookies before the try block: Next throws its dynamic-rendering bailout
  // from cookies(), and that must not be reported as an unreachable API.
  const cookieHeader = (await cookies()).toString();
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api/v1${path}`, {
      headers: { Accept: "application/json", Cookie: cookieHeader },
      cache: "no-store",
    });
  } catch {
    throw new Error(
      "The ReTurn API is unavailable. Start the Flask service (port 5000) and reload.",
    );
  }
  if (response.status === 401) {
    throw new ServerUnauthorizedError("authentication_required");
  }
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(payload?.error?.message ?? `API request failed (${response.status}).`);
  }
  return payload?.data as T;
}

export async function serverFetchList<T>(
  path: string,
): Promise<{ data: T[]; meta?: { unread_count?: number; total?: number } }> {
  const cookieHeader = (await cookies()).toString();
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api/v1${path}`, {
      headers: { Accept: "application/json", Cookie: cookieHeader },
      cache: "no-store",
    });
  } catch {
    throw new Error("The ReTurn API is unavailable. Start the Flask service and reload.");
  }
  if (response.status === 401) throw new ServerUnauthorizedError("authentication_required");
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(payload?.error?.message ?? `API request failed (${response.status}).`);
  }
  return { data: (payload?.data ?? []) as T[], meta: payload?.meta };
}

export async function getMe(): Promise<AuthMe | null> {
  try {
    return await serverFetch<AuthMe>("/auth/me");
  } catch (error) {
    if (error instanceof ServerUnauthorizedError) return null;
    throw error;
  }
}

export async function requireUser(role?: Role): Promise<AuthMe> {
  const me = await getMe();
  if (!me) redirect(`/auth?next=${encodeURIComponent(role ? `/${role}` : "/")}`);
  if (role && me.user.role !== role) redirect("/forbidden");
  return me;
}
