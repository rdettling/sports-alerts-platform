const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

if (!API_BASE_URL) {
  throw new Error("Missing required env var: VITE_API_BASE_URL");
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
  timeoutMs?: number;
  retries?: number;
};

function buildHeaders(options: RequestOptions): HeadersInit {
  return {
    "Content-Type": "application/json",
    ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
    ...(options.headers ?? {}),
  };
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const timeoutMs = options.timeoutMs ?? 15_000;
  const retries = options.retries ?? 0;

  let lastError: unknown;
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    const controller = new AbortController();
    const timeout = globalThis.setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(`${API_BASE_URL}${path}`, {
        ...options,
        signal: controller.signal,
        headers: buildHeaders(options),
      });

      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(normalizeErrorDetail((body as { detail?: unknown }).detail));
      }

      if (response.status === 204) {
        return undefined as T;
      }
      return response.json() as Promise<T>;
    } catch (error) {
      lastError = error;
      if (attempt === retries) break;
    } finally {
      globalThis.clearTimeout(timeout);
    }
  }

  if (lastError instanceof Error && lastError.name === "AbortError") {
    throw new Error("Request timed out");
  }

  if (lastError instanceof Error && /fetch/i.test(lastError.message)) {
    throw new Error(
      `Unable to reach API at ${API_BASE_URL}. Make sure the API service is running.`,
    );
  }

  throw lastError instanceof Error ? lastError : new Error("Request failed");
}
