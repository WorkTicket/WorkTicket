export type UserRole = "owner" | "admin" | "dispatcher" | "technician" | "read_only";

export type Permission =
  | "billing:view"
  | "billing:manage"
  | "team:view"
  | "team:manage"
  | "settings:view"
  | "settings:manage"
  | "customers:view"
  | "customers:manage"
  | "jobs:view"
  | "jobs:manage"
  | "jobs:delete"
  | "estimates:view"
  | "estimates:manage"
  | "scheduling:view"
  | "scheduling:manage"
  | "media:view"
  | "media:upload";

const ROLE_PERMISSIONS: Record<UserRole, Permission[]> = {
  owner: [
    "billing:view",
    "billing:manage",
    "team:view",
    "team:manage",
    "settings:view",
    "settings:manage",
    "customers:view",
    "customers:manage",
    "jobs:view",
    "jobs:manage",
    "jobs:delete",
    "estimates:view",
    "estimates:manage",
    "scheduling:view",
    "scheduling:manage",
    "media:view",
    "media:upload",
  ],
  admin: [
    "billing:view",
    "team:view",
    "team:manage",
    "settings:view",
    "settings:manage",
    "customers:view",
    "customers:manage",
    "jobs:view",
    "jobs:manage",
    "jobs:delete",
    "estimates:view",
    "estimates:manage",
    "scheduling:view",
    "scheduling:manage",
    "media:view",
    "media:upload",
  ],
  dispatcher: [
    "customers:view",
    "customers:manage",
    "jobs:view",
    "jobs:manage",
    "estimates:view",
    "estimates:manage",
    "scheduling:view",
    "scheduling:manage",
    "media:view",
    "media:upload",
    "team:view",
  ],
  technician: [
    "jobs:view",
    "media:view",
    "media:upload",
    "scheduling:view",
  ],
  read_only: [
    "customers:view",
    "jobs:view",
    "estimates:view",
    "scheduling:view",
    "media:view",
    "team:view",
    "billing:view",
    "settings:view",
  ],
};

export function normalizeRole(role: string | undefined): UserRole {
  if (!role) return "read_only";
  if (role in ROLE_PERMISSIONS) return role as UserRole;
  if (role === "office_manager") return "dispatcher";
  return "read_only";
}

export function hasPermission(role: UserRole, permission: Permission): boolean {
  return ROLE_PERMISSIONS[role]?.includes(permission) ?? false;
}

export function canAccessRoute(role: UserRole, path: string): boolean {
  const routePermissions: Record<string, Permission> = {
    "/billing": "billing:view",
    "/team": "team:view",
    "/settings": "settings:view",
    "/customers": "customers:view",
    "/jobs": "jobs:view",
    "/estimates": "estimates:view",
    "/scheduling": "scheduling:view",
    "/photos": "media:view",
    "/voice-notes": "media:view",
  };

  for (const [prefix, permission] of Object.entries(routePermissions)) {
    if (path === prefix || path.startsWith(`${prefix}/`)) {
      return hasPermission(role, permission);
    }
  }
  return true;
}
