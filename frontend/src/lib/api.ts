import { invoke } from "@tauri-apps/api/core";
import type { AutoJoinState, Diagnostics, Settings, Snapshot, SubscriptionsState } from "./types";

export const getSnapshot = () => invoke<Snapshot | null>("get_snapshot");
export const getDiagnostics = () => invoke<Diagnostics>("get_diagnostics");
export const getSettings = () => invoke<Settings>("get_settings");
export const getSubscriptions = () => invoke<SubscriptionsState>("get_subscriptions");
export const getAutoJoin = () => invoke<AutoJoinState>("get_autojoin");

export const refreshNow = () => invoke<void>("refresh_now");
export const updateServersUrl = (serversUrl: string) =>
  invoke<void>("update_servers_url", { serversUrl });
export const updateTheme = (theme: string) => invoke<void>("update_theme", { theme });
export const updateNotifications = (enabled: boolean) =>
  invoke<void>("update_notifications", { enabled });

export const setSubscriptions = (serverKey: string, maps: string[]) =>
  invoke<void>("set_subscriptions", { serverKey, maps });

export const armAutoJoin = (serverKey: string) => invoke<void>("arm_autojoin", { serverKey });
export const stopAutoJoin = () => invoke<void>("stop_autojoin");
export const joinNow = (connectAddr: string) => invoke<void>("join_now", { connectAddr });

export const copyDiagnostics = () => invoke<void>("copy_diagnostics");
