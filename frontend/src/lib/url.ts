export const DEFAULT_BASE_URL = "https://www.cs2ze.org";

export const normalizeBaseUrl = (input: string): string => {
  const trimmed = (input ?? "").trim();
  if (!trimmed) return DEFAULT_BASE_URL;
  let url = trimmed;
  if (url.startsWith("http://") || url.startsWith("https://")) {
    // keep scheme
  } else if (url.startsWith("//")) {
    url = `https:${url}`;
  } else {
    url = `https://${url}`;
  }
  try {
    const parsed = new URL(url);
    return parsed.origin;
  } catch {
    return DEFAULT_BASE_URL;
  }
};

export const resolveUrl = (pathOrUrl: string, baseUrl?: string): string => {
  const fallbackBase =
    typeof window !== "undefined" && window.location ? window.location.origin : DEFAULT_BASE_URL;
  const base = baseUrl ?? fallbackBase;
  try {
    return new URL(pathOrUrl, base).toString();
  } catch {
    return new URL("/", base).toString();
  }
};

export const buildServersUrl = (baseUrl: string): string => resolveUrl("/servers.json", baseUrl);
export const buildConfigUrl = (baseUrl: string): string => resolveUrl("/config.json", baseUrl);
export const buildLanguageUrl = (baseUrl: string): string => resolveUrl("/language.json", baseUrl);
export const buildMapTranslationsUrl = (baseUrl: string): string =>
  resolveUrl("/map_translations.json", baseUrl);
