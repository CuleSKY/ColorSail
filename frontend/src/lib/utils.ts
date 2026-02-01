import type { ServerItem, ServerRow, Snapshot } from "./types";

export const mapDisplay = (server: ServerItem): string => {
  const mapCn = server.map_cn?.trim();
  const mapTw = server.map_tw?.trim();
  if (mapCn) return mapCn;
  if (mapTw) return mapTw;
  if (server.map && server.map !== "-") return server.map;
  return "Unknown";
};

export const serverKey = (server: ServerItem): string => `${server.ip}:${server.port}`;

export const connectAddr = (server: ServerItem): string => `${server.connect_ip}:${server.port}`;

export const flattenSnapshot = (snapshot: Snapshot | null): ServerRow[] => {
  if (!snapshot) return [];
  const rows: ServerRow[] = [];
  Object.entries(snapshot).forEach(([communityId, servers]) => {
    servers.forEach((server) => {
      rows.push({
        ...server,
        server_key: serverKey(server),
        connect_addr: connectAddr(server),
        map_display: mapDisplay(server),
        community_id: communityId
      });
    });
  });
  return rows;
};
