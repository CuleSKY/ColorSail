export type GenericServerRecord = Record<string, any>;

const allowedJoinStrategies = new Set([
  'rungameid',
  'steam_connect',
  'server_browser',
  'clipboard_only'
]);

export const formatTemplate = (template: string, vars: Record<string, any> = {}): string => {
  return template.replace(/\{(\w+)\}/g, (_, key: string) => vars[key] ?? '');
};

export const getServerKey = (srv: GenericServerRecord): string => `${srv.ip}:${srv.port}`;

export const normalizeJoinStrategy = (value: unknown): string | null => {
  if (!value) return null;
  const normalized = String(value).trim().toLowerCase();
  return allowedJoinStrategies.has(normalized) ? normalized : null;
};

export const getConnectAddress = (srv: GenericServerRecord): string => {
  const host = srv.connect_ip || srv.ip;
  if (host && srv.port) {
    return `${host}:${srv.port}`;
  }
  return srv.display_ip || `${srv.ip}:${srv.port}`;
};

export const getFastJoinUrl = (srv: GenericServerRecord): string => {
  const address = getConnectAddress(srv);
  const appid = String(srv.game || 'cs2').toLowerCase() === 'css' ? 240 : 730;
  return `steam://rungameid/${appid}//+connect%20${address}`;
};
