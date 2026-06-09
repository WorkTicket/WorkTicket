import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const dashboardUrl = process.env.NEXT_PUBLIC_DASHBOARD_URL || "http://localhost:3000";

export function signUpUrl() {
  return `${dashboardUrl}/sign-up`;
}

export function signInUrl() {
  return `${dashboardUrl}/sign-in`;
}
