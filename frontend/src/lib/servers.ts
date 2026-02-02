import { get } from "svelte/store";
import { communities, serverLoadError, serversByCommunity } from "./stores";
import { appSettings } from "./settingsStore";
import type { CommunityMeta } from "./resources";
import type { ServerItem } from "./types";
import { fetchWithAdapter } from "./http";
import { buildServersUrl, normalizeBaseUrl } from "./url";

type ServerCacheEntry = ServerItem & { _lastSeen: number };

const JITTER_MIN_MS = 6000;
const JITTER_MAX_MS = 10000;
const HIDDEN_MIN_MS = 15000;
const STALE_MS = 60000;

let refreshEtag: string | null = null;
let refreshInFlight = false;
let refreshTimer: ReturnType<typeof setTimeout> | null = null;
let currentBaseUrl = normalizeBaseUrl(get(appSettings).servers_source);

const serverCache: Record<string, Record<string, ServerCacheEntry>> = {};

export const normalizeServersSource = (input: string): string => normalizeBaseUrl(input);

const syncBaseUrl = (raw: string) => {
  const normalized = normalizeBaseUrl(raw);
  if (normalized === currentBaseUrl) return false;
  currentBaseUrl = normalized;
  refreshEtag = null;
  return true;
};

const getServerKey = (srv: ServerItem): string => {
  if (srv.ip && srv.port) return `${srv.ip}:${srv.port}`;
  if (srv.display_ip) return srv.display_ip;
  return `${srv.name ?? "unknown"}`;
};

const normalizePayload = (payload: unknown): Record<string, ServerItem[]> => {
  if (Array.isArray(payload)) {
    return payload.reduce<Record<string, ServerItem[]>>((acc, item) => {
      if (!item || typeof item !== "object") return acc;
      const server = item as ServerItem & { cid?: string };
      if (!server.cid) return acc;
      if (!acc[server.cid]) acc[server.cid] = [];
      acc[server.cid].push(server);
      return acc;
    }, {});
  }
  if (payload && typeof payload === "object") {
    const data = payload as { data?: unknown; servers?: unknown };
    if (Array.isArray(data.data)) return { all: data.data as ServerItem[] };
    if (Array.isArray(data.servers)) return { all: data.servers as ServerItem[] };
    const values = Object.values(payload);
    if (values.length > 0 && values.every((value) => Array.isArray(value))) {
      return payload as Record<string, ServerItem[]>;
    }
  }
  return {};
};

const updateCommunitiesFallback = (payload: Record<string, ServerItem[]>) => {
  if (get(communities).length > 0) return;
  const fallback: CommunityMeta[] = Object.keys(payload).map((id) => ({
    id,
    name: id.toUpperCase(),
    short_name: id.toUpperCase()
  }));
  if (fallback.length > 0) communities.set(fallback);
};

const applyServerCache = (payload: Record<string, ServerItem[]>) => {
  const now = Date.now();
  const allCommunityIds = new Set<string>([
    ...Object.keys(serverCache),
    ...Object.keys(payload)
  ]);

  allCommunityIds.forEach((cid) => {
    const cache = serverCache[cid] ?? {};
    const data = Array.isArray(payload[cid]) ? payload[cid] : [];
    data.forEach((server) => {
      const key = getServerKey(server);
      cache[key] = { ...server, _lastSeen: now };
    });
    Object.keys(cache).forEach((key) => {
      if (now - cache[key]._lastSeen > STALE_MS) {
        delete cache[key];
      }
    });
    serverCache[cid] = cache;
  });

  const snapshot: Record<string, ServerItem[]> = {};
  Object.keys(serverCache).forEach((cid) => {
    snapshot[cid] = Object.values(serverCache[cid]).map(({ _lastSeen, ...rest }) => rest);
  });
  serversByCommunity.set(snapshot);
};

const refreshServers = async () => {
  if (refreshInFlight) return;
  refreshInFlight = true;
  try {
    const headers: Record<string, string> = {};
    if (refreshEtag) headers["If-None-Match"] = refreshEtag;
    const serversUrl = buildServersUrl(currentBaseUrl);
    const res = await fetchWithAdapter(serversUrl, { headers }, currentBaseUrl);
    if (res.status === 304) {
      serverLoadError.set(false);
      return;
    }
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const etag = res.headers.get("ETag") || res.headers.get("etag");
    if (etag) refreshEtag = etag;
    const payload = normalizePayload(await res.json());
    updateCommunitiesFallback(payload);
    applyServerCache(payload);
    serverLoadError.set(false);
  } catch {
    serverLoadError.set(true);
  } finally {
    refreshInFlight = false;
  }
};

const getNextInterval = () => {
  const jitter = Math.floor(Math.random() * (JITTER_MAX_MS - JITTER_MIN_MS + 1)) + JITTER_MIN_MS;
  if (document.visibilityState !== "visible") {
    return Math.max(jitter, HIDDEN_MIN_MS);
  }
  return jitter;
};

const scheduleNext = () => {
  if (refreshTimer) clearTimeout(refreshTimer);
  refreshTimer = setTimeout(async () => {
    await refreshServers();
    scheduleNext();
  }, getNextInterval());
};

export const startServersPoller = () => {
  if (refreshTimer) return;
  syncBaseUrl(get(appSettings).servers_source);
  refreshServers().finally(() => {
    scheduleNext();
  });
  document.addEventListener("visibilitychange", () => {
    if (refreshTimer) scheduleNext();
  });
};

export const stopServersPoller = () => {
  if (refreshTimer) {
    clearTimeout(refreshTimer);
    refreshTimer = null;
  }
};

export const refreshServersNow = async () => {
  await refreshServers();
};

appSettings.subscribe((settings) => {
  if (syncBaseUrl(settings.servers_source)) {
    refreshServersNow().catch(() => {
      // refresh handles errors internally
    });
  }
});
