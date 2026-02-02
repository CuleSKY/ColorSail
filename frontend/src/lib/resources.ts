import { get } from "svelte/store";
import { communities, configMeta, languagePack, mapTranslations, resourceOffline } from "./stores";
import { appSettings } from "./settingsStore";
import { fetchWithAdapter } from "./http";
import {
  buildConfigUrl,
  buildLanguageUrl,
  buildMapTranslationsUrl,
  normalizeBaseUrl,
  resolveUrl
} from "./url";

export type CommunityMeta = {
  id: string;
  name: string;
  short_name?: string;
  logo?: string;
  [key: string]: unknown;
};

export type LanguagePack = Record<string, Record<string, string>>;

export type MapTranslationEntry = { zh_cn: string; zh_tw: string };
export type MapTranslations = Record<string, MapTranslationEntry>;

type ResourceName = "config" | "map_translations" | "language";

type CacheEntry<T> = {
  etag: string | null;
  data: T;
};

type StorageDriver = {
  read: <T>(key: string) => Promise<CacheEntry<T> | null>;
  write: <T>(key: string, entry: CacheEntry<T>) => Promise<void>;
};

type ConfigPayload = {
  communities: CommunityMeta[];
  languageUrl?: string | null;
};

type ResourceSpec = {
  getUrl: (baseUrl: string) => string;
  normalize: (data: unknown) => unknown;
  apply: (data: unknown) => void;
};

const RESOURCE_SPECS: Record<ResourceName, ResourceSpec> = {
  config: {
    getUrl: (baseUrl) => buildConfigUrl(baseUrl),
    normalize: (data) => {
      if (Array.isArray(data)) {
        return { communities: data as CommunityMeta[], languageUrl: null } satisfies ConfigPayload;
      }
      if (data && typeof data === "object") {
        const raw = data as {
          communities?: unknown;
          language_url?: unknown;
          languageUrl?: unknown;
        };
        const communities = Array.isArray(raw.communities) ? (raw.communities as CommunityMeta[]) : [];
        const languageUrl =
          typeof raw.language_url === "string"
            ? raw.language_url
            : typeof raw.languageUrl === "string"
              ? raw.languageUrl
              : null;
        return { communities, languageUrl } satisfies ConfigPayload;
      }
      return { communities: [], languageUrl: null } satisfies ConfigPayload;
    },
    apply: (data) => {
      const payload = data as ConfigPayload;
      communities.set(payload.communities ?? []);
      configMeta.set({ languageUrl: payload.languageUrl ?? null });
    }
  },
  map_translations: {
    getUrl: (baseUrl) => buildMapTranslationsUrl(baseUrl),
    normalize: (data) => normalizeTranslations(data),
    apply: (data) => {
      mapTranslations.set((data as MapTranslations) ?? {});
    }
  },
  language: {
    getUrl: (baseUrl) => resolveLanguageUrl(baseUrl),
    normalize: (data) => normalizeLanguagePack(data),
    apply: (data) => {
      applyLanguagePack(data);
    }
  }
};

const cacheKey = (name: ResourceName) => `resource_${name}`;
const storagePrefix = "cs2ze:";

let storagePromise: Promise<StorageDriver> | null = null;
const inMemoryEtag: Partial<Record<ResourceName, string | null>> = {};
const inMemorySerialized: Partial<Record<ResourceName | "language", string>> = {};
let currentBaseUrl = "";

const normalizeTranslations = (data: unknown): MapTranslations => {
  if (!data || typeof data !== "object") return {};
  const normalized: MapTranslations = {};
  Object.entries(data as Record<string, unknown>).forEach(([key, value]) => {
    if (typeof value === "string") {
      normalized[key] = { zh_cn: value, zh_tw: value };
      return;
    }
    if (value && typeof value === "object") {
      const raw = value as { zh_cn?: string; zh_tw?: string; cn?: string; tw?: string };
      normalized[key] = {
        zh_cn: raw.zh_cn ?? raw.cn ?? "",
        zh_tw: raw.zh_tw ?? raw.tw ?? raw.zh_cn ?? raw.cn ?? ""
      };
    }
  });
  return normalized;
};

const getStorageDriver = async (): Promise<StorageDriver> => {
  if (storagePromise) return storagePromise;
  storagePromise = (async () => {
    const hasTauri =
      typeof window !== "undefined" && typeof (window as { __TAURI__?: unknown }).__TAURI__ !== "undefined";
    if (hasTauri) {
      try {
        const tauriModuleUrl = new URL("./resources.tauri", import.meta.url).href;
        const { createTauriStorageDriver } = await import(/* @vite-ignore */ tauriModuleUrl);
        return await createTauriStorageDriver();
      } catch {
        // fall through to localStorage
      }
    }

    return {
      read: async <T>(key: string) => {
        const raw = localStorage.getItem(`${storagePrefix}${key}`);
        if (!raw) return null;
        try {
          return JSON.parse(raw) as CacheEntry<T>;
        } catch {
          return null;
        }
      },
      write: async <T>(key: string, entry: CacheEntry<T>) => {
        localStorage.setItem(`${storagePrefix}${key}`, JSON.stringify(entry));
      }
    };
  })();
  return storagePromise;
};

const applyIfChanged = (name: ResourceName, data: unknown) => {
  const serialized = JSON.stringify(data ?? {});
  if (inMemorySerialized[name] === serialized) return;
  inMemorySerialized[name] = serialized;
  RESOURCE_SPECS[name].apply(data);
};

const getBaseUrl = () => {
  const baseUrl = normalizeBaseUrl(get(appSettings).servers_source);
  if (baseUrl !== currentBaseUrl) {
    currentBaseUrl = baseUrl;
    (Object.keys(RESOURCE_SPECS) as ResourceName[]).forEach((key) => {
      inMemoryEtag[key] = null;
    });
  }
  return baseUrl;
};

const resolveLanguageUrl = (baseUrl: string) => {
  const candidate = get(configMeta)?.languageUrl;
  if (candidate && candidate.trim()) {
    return resolveUrl(candidate.trim(), baseUrl);
  }
  return buildLanguageUrl(baseUrl);
};

const normalizeLanguagePack = (data: unknown) => {
  if (data && typeof data === "object") return data as LanguagePack;
  return {};
};

const applyLanguagePack = (data: unknown) => {
  const normalized = normalizeLanguagePack(data);
  languagePack.set(normalized);
};

const loadCachedResource = async (name: ResourceName) => {
  const storage = await getStorageDriver();
  const cached = await storage.read<unknown>(cacheKey(name));
  if (!cached) return;
  if (cached.etag) inMemoryEtag[name] = cached.etag;
  applyIfChanged(name, cached.data);
};

const refreshResource = async (name: ResourceName) => {
  const spec = RESOURCE_SPECS[name];
  const headers: Record<string, string> = {};
  if (inMemoryEtag[name]) {
    headers["If-None-Match"] = String(inMemoryEtag[name]);
  }
  const baseUrl = getBaseUrl();
  const url = spec.getUrl(baseUrl);
  const res = await fetchWithAdapter(url, { headers }, baseUrl);
  if (res.status === 304) return;
  if (!res.ok) throw new Error(`Failed ${name}: ${res.status}`);
  const etag = res.headers.get("ETag") || res.headers.get("etag");
  const payload = await res.json();
  const normalized = spec.normalize(payload);
  const storage = await getStorageDriver();
  applyIfChanged(name, normalized);
  const entry = { etag: etag ?? null, data: normalized };
  if (etag) inMemoryEtag[name] = etag;
  await storage.write(cacheKey(name), entry);
};

export const loadStaticResources = async () => {
  resourceOffline.set(false);
  await Promise.all(Object.keys(RESOURCE_SPECS).map((name) => loadCachedResource(name as ResourceName)));

  const markOfflineIfCached = () => {
    const hasCache =
      !!get(languagePack) ||
      Object.keys(get(mapTranslations)).length > 0 ||
      (get(communities) || []).length > 0;
    if (hasCache) resourceOffline.set(true);
  };

  await refreshResource("config").catch(markOfflineIfCached);
  const refreshes = [
    refreshResource("map_translations").catch(markOfflineIfCached),
    refreshResource("language").catch(markOfflineIfCached)
  ];
  await Promise.all(refreshes);
};
