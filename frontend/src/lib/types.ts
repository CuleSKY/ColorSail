export interface ServerItem {
  name: string;
  ip: string;
  connect_ip: string;
  port: number;
  display_ip: string;
  map: string;
  players: number;
  max_players: number;
  online: boolean;
  ping: number;
  game_type: string;
  image_url?: string | null;
  map_cn?: string | null;
  map_tw?: string | null;
  query_source?: string | null;
}

export type Snapshot = Record<string, ServerItem[]>;

export interface DiffSummary {
  changed_servers: number;
  map_changed: number;
  online_changed: number;
}

export interface Diagnostics {
  servers_url: string;
  last_fetch_time?: string | null;
  last_status?: string | null;
  last_error?: string | null;
  etag?: string | null;
  hits_304: number;
  jitter_min_seconds: number;
  jitter_max_seconds: number;
  current_backoff_seconds?: number | null;
  next_poll_time?: string | null;
  last_snapshot_time?: string | null;
  diff_summary: DiffSummary;
}

export interface Settings {
  servers_url: string;
  theme: string;
  notifications_enabled: boolean;
}

export interface SubscriptionsState {
  subscriptions: Record<string, string[]>;
  last_seen_map: Record<string, string>;
}

export interface AutoJoinHistoryEntry {
  timestamp: string;
  state: string;
  detail: string;
}

export interface AutoJoinState {
  state: string;
  target_server_key?: string | null;
  granted_until?: string | null;
  cooldown_until?: string | null;
  attempts?: number;
  max_attempts?: number;
  history: AutoJoinHistoryEntry[];
}

export interface ServerRow extends ServerItem {
  server_key: string;
  connect_addr: string;
  map_display: string;
  community_id: string;
}
