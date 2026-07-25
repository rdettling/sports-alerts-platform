import { apiRequest } from "../client";
import type { AuthResponse, MagicLinkStartResponse, UserProfile } from "../types";

export function startMagicLink(email: string): Promise<MagicLinkStartResponse> {
  return apiRequest<MagicLinkStartResponse>("/auth/magic-link/start", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function warmAuthDb(): Promise<void> {
  const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/auth/warm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) {
    throw new Error("Auth warmup failed");
  }
}

export function verifyMagicLink(token: string): Promise<AuthResponse> {
  return apiRequest<AuthResponse>("/auth/magic-link/verify", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export function verifyMagicCode(email: string, code: string): Promise<AuthResponse> {
  return apiRequest<AuthResponse>("/auth/magic-code/verify", {
    method: "POST",
    body: JSON.stringify({ email, code }),
  });
}

export function me(token: string): Promise<UserProfile> {
  return apiRequest<UserProfile>("/auth/me", { token });
}
