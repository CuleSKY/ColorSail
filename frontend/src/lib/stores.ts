import { writable } from "svelte/store";
import type { AutoJoinState, Diagnostics, Settings, Snapshot, SubscriptionsState } from "./types";

export const snapshot = writable<Snapshot | null>(null);
export const diagnostics = writable<Diagnostics | null>(null);
export const settings = writable<Settings | null>(null);
export const subscriptions = writable<SubscriptionsState | null>(null);
export const autojoin = writable<AutoJoinState | null>(null);

export const activePage = writable("Servers");
