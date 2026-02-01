import type { MapTranslations } from "./resources";
import type { ServerItem } from "./types";

export type MapTranslationEntry = { zh_cn: string; zh_tw: string };

export const normalizeMapKey = (value?: string | null): string => {
  if (!value) return "";
  let mapKey = value.toString().trim().toLowerCase();
  mapKey = mapKey.replace(/\\/g, "/").split("?", 1)[0];
  if (mapKey.endsWith(".bsp")) mapKey = mapKey.slice(0, -4);
  if (mapKey.startsWith("workshop/")) {
    const parts = mapKey.split("/");
    mapKey = parts[parts.length - 1] || mapKey;
  } else {
    mapKey = mapKey.split("/").pop() ?? mapKey;
  }
  return mapKey;
};

export const getMapTranslationEntry = (
  mapName: string | undefined,
  serverEntry: Pick<ServerItem, "map_cn" | "map_tw"> | null,
  translations: MapTranslations
): MapTranslationEntry => {
  if (!mapName) return { zh_cn: "", zh_tw: "" };
  if (translations[mapName]) return translations[mapName];
  const normalizedKey = normalizeMapKey(mapName);
  if (normalizedKey && translations[normalizedKey]) return translations[normalizedKey];
  if (serverEntry) {
    return {
      zh_cn: serverEntry.map_cn ?? "",
      zh_tw: serverEntry.map_tw ?? ""
    };
  }
  return { zh_cn: "", zh_tw: "" };
};

export const normalizeSearchText = (value: string | null | undefined): string =>
  (value ?? "").toString().toLowerCase().replace(/\s+/g, "");

export const matchesServerSearch = (
  serverEntry: Pick<ServerItem, "map" | "name" | "map_cn" | "map_tw">,
  query: string,
  translations: MapTranslations,
  includeServerName = true
): boolean => {
  const mapName = serverEntry.map ?? "";
  const entry = getMapTranslationEntry(mapName, serverEntry, translations);
  const candidates = [
    mapName,
    normalizeMapKey(mapName),
    entry.zh_cn || "",
    entry.zh_tw || ""
  ];
  if (includeServerName) candidates.push(serverEntry.name ?? "");
  const normalizedQuery = normalizeSearchText(query);
  return candidates.some((item) => normalizeSearchText(item).includes(normalizedQuery));
};

export const sortServers = <T extends Pick<ServerItem, "online" | "players">>(
  servers: T[]
): T[] =>
  [...servers].sort((a, b) => {
    if (a.online && !b.online) return -1;
    if (!a.online && b.online) return 1;
    return (b.players ?? 0) - (a.players ?? 0);
  });

export const filterCommunitiesBySearch = <T>(
  communities: T[],
  hasResults: (community: T) => boolean,
  query: string
): T[] => {
  if (!normalizeSearchText(query)) return communities;
  return communities.filter(hasResults);
};

// Self-check examples (manual):
// normalizeMapKey("workshop/123/ze_test.bsp?foo") -> "ze_test"
// normalizeMapKey("maps\\ze_demo.bsp") -> "ze_demo"
// matchesServerSearch({ map: "ze_test", name: "Server", map_cn: "", map_tw: "" }, "test", {}, true) -> true
