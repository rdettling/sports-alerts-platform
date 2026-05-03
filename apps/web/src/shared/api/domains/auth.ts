import { apiRequest } from "../client";
import type { AuthResponse, MagicLinkStartResponse, UserProfile } from "../types";

export function startMagicLink(email: string): Promise<MagicLinkStartResponse> {
  return apiRequest<MagicLinkStartResponse>("/auth/magic-link/start", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function verifyMagicLink(token: string): Promise<AuthResponse> {
  return apiRequest<AuthResponse>("/auth/magic-link/verify", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export function me(token: string): Promise<UserProfile> {
  return apiRequest<UserProfile>("/auth/me", { token });
}
