import { buildApiUrl } from "@/lib/api";
import { createLocalUuid } from "@/lib/local-id";

export const ANONYMOUS_ID_STORAGE_KEY = "smartinsure_anonymous_id";

interface AnonymousIdentityResponse {
  anonymous_id?: unknown;
}

interface IdentityOptions {
  fetcher?: typeof fetch;
}

function getStorage(): Storage | null {
  return typeof window === "undefined" ? null : window.localStorage;
}

export function createLocalAnonymousId(): string {
  return `anon_local_${createLocalUuid()}`;
}

export function getStoredAnonymousId(): string | null {
  const value = getStorage()?.getItem(ANONYMOUS_ID_STORAGE_KEY)?.trim();
  return value || null;
}

export function saveAnonymousId(anonymousId: string): void {
  getStorage()?.setItem(ANONYMOUS_ID_STORAGE_KEY, anonymousId);
}

export function clearAnonymousId(): void {
  getStorage()?.removeItem(ANONYMOUS_ID_STORAGE_KEY);
}

export async function createAnonymousIdentity(options: IdentityOptions = {}): Promise<string> {
  const fetcher = options.fetcher ?? fetch;

  try {
    const response = await fetcher(buildApiUrl("/api/anonymous-identities"), {
      method: "POST",
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to create anonymous identity (${response.status})`);
    }

    const data = (await response.json()) as AnonymousIdentityResponse;
    if (typeof data.anonymous_id === "string" && data.anonymous_id.trim()) {
      return data.anonymous_id;
    }
  } catch {
    return createLocalAnonymousId();
  }

  return createLocalAnonymousId();
}

export async function initializeAnonymousIdentity(options: IdentityOptions = {}): Promise<string> {
  const storedAnonymousId = getStoredAnonymousId();
  if (storedAnonymousId) {
    return storedAnonymousId;
  }

  const anonymousId = await createAnonymousIdentity(options);
  saveAnonymousId(anonymousId);
  return anonymousId;
}
