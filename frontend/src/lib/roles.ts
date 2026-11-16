import type { Role } from "@/lib/types";

export const ROLE_LABELS: Record<Role, string> = {
  consumer: "Consumer",
  driver: "Driver",
  manager: "Operations manager",
  admin: "Administrator",
};

export function homeFor(role: Role): string {
  return `/${role}`;
}
