import { writable } from "svelte/store";
import type { AutoJoinState, Diagnostics, Settings, Snapshot, SubscriptionsState } from "./types";
import type { CommunityMeta, LanguagePack, MapTranslations } from "./resources";

export const snapshot = writable<Snapshot | null>(null);
export const diagnostics = writable<Diagnostics | null>(null);
export const settings = writable<Settings | null>(null);
export const subscriptions = writable<SubscriptionsState | null>(null);
export const autojoin = writable<AutoJoinState | null>(null);

export const activePage = writable("Servers");

export const configMeta = writable<{ languageUrl?: string | null } | null>(null);
export const communities = writable<CommunityMeta[]>([]);
export const languagePack = writable<LanguagePack | null>(null);
export const mapTranslations = writable<MapTranslations>({});
export const resourceOffline = writable(false);
export const serversByCommunity = writable<Record<string, Snapshot[string]>>({});
export const serverLoadError = writable(false);
