import { normalizeBaseUrl, resolveUrl } from "./url";

type Fetcher = (input: string, init?: RequestInit) => Promise<Response>;

export const isTauriRuntime = (): boolean => {
  return (
    typeof window !== "undefined" &&
    typeof (window as { __TAURI__?: unknown }).__TAURI__ !== "undefined"
  );
};

const getFetcher = async (): Promise<Fetcher> => {
  if (isTauriRuntime()) {
    const moduleId = "@tauri-apps/plugin-http";
    const { fetch } = await import(/* @vite-ignore */ moduleId);
    return fetch as Fetcher;
  }
  return fetch;
};

const shouldProxy = (resolvedUrl: string, baseUrl?: string): boolean => {
  if (!baseUrl) return false;
  if (isTauriRuntime()) return false;
  if (!import.meta.env.DEV) return false;
  try {
    const baseOrigin = new URL(normalizeBaseUrl(baseUrl)).origin;
    const targetOrigin = new URL(resolvedUrl).origin;
    return baseOrigin === targetOrigin;
  } catch {
    return false;
  }
};

export const toProxyUrl = (resolvedUrl: string): string => {
  const url = new URL(resolvedUrl);
  return `/__proxy${url.pathname}${url.search}`;
};

export const fetchWithAdapter = async (
  pathOrUrl: string,
  init: RequestInit = {},
  baseUrl?: string
): Promise<Response> => {
  const resolvedUrl = resolveUrl(pathOrUrl, baseUrl);
  const requestUrl = shouldProxy(resolvedUrl, baseUrl) ? toProxyUrl(resolvedUrl) : resolvedUrl;
  const fetcher = await getFetcher();
  return fetcher(requestUrl, init);
};
