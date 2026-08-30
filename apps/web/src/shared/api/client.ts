const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
const REQUEST_TIMEOUT_MS = 15_000;

if (!API_BASE_URL) {
  throw new Error("Missing required env var: VITE_API_BASE_URL");
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function isUnauthorizedError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

function normalizeErrorDetail(detail: unknown): string {
  if (typeof detail === "string" && detail.trim().length > 0) {
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item && typeof item.msg === "string") {
          return item.msg;
        }
        return null;
      })
      .filter((message): message is string => Boolean(message));

    if (messages.length > 0) {
      return messages.join(", ");
    }
  }

  return "Request failed";
}

type RequestOptions = RequestInit & {
  token?: string;
};

function buildHeaders(token: string | undefined, headers: HeadersInit | undefined): HeadersInit {
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(headers ?? {}),
  };
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { token, ...requestOptions } = options;
  const controller = new AbortController();
  const timeout = globalThis.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let requestError: unknown;

  try {
    const response = await fetch(apiUrl(path), {
      ...requestOptions,
      signal: controller.signal,
      headers: buildHeaders(token, requestOptions.headers),
    });

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new ApiError(
        normalizeErrorDetail((body as { detail?: unknown }).detail),
        response.status,
      );
    }

    if (response.status === 204) {
      return undefined as T;
    }
    return response.json() as Promise<T>;
  } catch (error) {
    requestError = error;
  } finally {
    globalThis.clearTimeout(timeout);
  }

  if (requestError instanceof Error && requestError.name === "AbortError") {
    throw new Error("Request timed out");
  }

  if (requestError instanceof Error && /fetch/i.test(requestError.message)) {
    throw new Error(
      `Unable to reach API at ${API_BASE_URL}. Make sure the API service is running.`,
    );
  }

  throw requestError instanceof Error ? requestError : new Error("Request failed");
}
