import { writable } from "svelte/store";

export type ViewMode = "grid" | "list";
export type ThemeMode = "light" | "dark";

export type AppSettings = {
  servers_source: string;
  ui_language: string;
  sidebar_collapsed: boolean;
  view_mode: ViewMode;
  theme: ThemeMode;
};

export const DEFAULT_SERVERS_SOURCE = "https://www.cs2ze.org/servers.json";
export const DEFAULT_UI_LANGUAGE = "zh-CN";

const readBoolean = (key: string, fallback: boolean) => {
  const raw = localStorage.getItem(key);
  if (raw === null) return fallback;
  return raw === "true";
};

const readString = (key: string, fallback: string) => {
  const raw = localStorage.getItem(key);
  if (raw === null) return fallback;
  const trimmed = raw.trim();
  return trimmed ? trimmed : fallback;
};

const readViewMode = () => {
  const raw = localStorage.getItem("view_mode");
  return raw === "grid" || raw === "list" ? raw : "list";
};

const readTheme = () => {
  const raw = localStorage.getItem("theme");
  if (raw === "dark" || raw === "light") return raw;
  const prefersDark =
    typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches;
  return prefersDark ? "dark" : "light";
};

const readUiLanguage = () => {
  const stored = readString("ui_language", "");
  if (stored) return stored;
  const legacy = readString("lang", "");
  return legacy || DEFAULT_UI_LANGUAGE;
};

const initialSettings: AppSettings = {
  servers_source: readString("servers_source", DEFAULT_SERVERS_SOURCE),
  ui_language: readUiLanguage(),
  sidebar_collapsed: readBoolean("sidebar_collapsed", false),
  view_mode: readViewMode(),
  theme: readTheme()
};

const settingsStore = writable<AppSettings>(initialSettings);

export const appSettings = {
  subscribe: settingsStore.subscribe,
  set: (settings: AppSettings) => {
    settingsStore.set(settings);
    persist(settings);
  },
  update: settingsStore.update
};

const persist = (settings: AppSettings) => {
  localStorage.setItem("servers_source", settings.servers_source);
  localStorage.setItem("ui_language", settings.ui_language);
  localStorage.setItem("sidebar_collapsed", String(settings.sidebar_collapsed));
  localStorage.setItem("view_mode", settings.view_mode);
  localStorage.setItem("theme", settings.theme);
};

const updateSetting = <K extends keyof AppSettings>(key: K, value: AppSettings[K]) => {
  settingsStore.update((current) => {
    const next = { ...current, [key]: value };
    persist(next);
    return next;
  });
};

export const setServersSource = (value: string) => {
  const trimmed = value.trim();
  updateSetting("servers_source", trimmed || DEFAULT_SERVERS_SOURCE);
};

export const setUiLanguage = (value: string) => {
  const trimmed = value.trim();
  updateSetting("ui_language", trimmed || DEFAULT_UI_LANGUAGE);
};

export const setSidebarCollapsed = (value: boolean) => {
  updateSetting("sidebar_collapsed", value);
};

export const setViewMode = (value: ViewMode) => {
  updateSetting("view_mode", value);
};

export const setTheme = (value: ThemeMode) => {
  updateSetting("theme", value);
};
