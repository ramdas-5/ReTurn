import type { Role } from "@/lib/types";

/** Client-safe role landing paths (no server-only imports). */
export function homeFor(role: Role): string {
  if (role === "admin") return "/admin";
  if (role === "partner") return "/partner";
  return "/customer";
}
