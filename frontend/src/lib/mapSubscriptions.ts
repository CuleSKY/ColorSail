export type MapSubscription = {
  map: string;
  comms: string[];
};

const STORAGE_KEY = "map_subs";

const normalizeEntry = (entry: unknown): MapSubscription | null => {
  if (!entry || typeof entry !== "object") return null;
  const raw = entry as { map?: unknown; comms?: unknown };
  if (typeof raw.map !== "string" || !Array.isArray(raw.comms)) return null;
  return {
    map: raw.map,
    comms: raw.comms.filter((value) => typeof value === "string") as string[]
  };
};

export const loadMapSubscriptions = (): MapSubscription[] => {
  if (typeof localStorage === "undefined") return [];
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.map(normalizeEntry).filter((item): item is MapSubscription => !!item);
  } catch {
    return [];
  }
};

export const saveMapSubscriptions = (items: MapSubscription[]): void => {
  if (typeof localStorage === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
};

export const upsertMapSubscription = (
  items: MapSubscription[],
  map: string,
  comms: string[]
): MapSubscription[] => {
  const normalizedMap = map.trim();
  const normalizedComms = comms.map((value) => value.trim()).filter(Boolean);
  const next = items.filter((item) => item.map !== normalizedMap);
  next.unshift({ map: normalizedMap, comms: normalizedComms });
  return next;
};

export const removeMapSubscription = (items: MapSubscription[], map: string): MapSubscription[] => {
  return items.filter((item) => item.map !== map);
};
