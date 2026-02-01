use std::{
    collections::{HashMap, VecDeque},
    fs,
    path::PathBuf,
    time::Duration,
};

use chrono::{DateTime, Utc};
use rand::Rng;
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Emitter, Manager, State};
use tauri_plugin_clipboard_manager::ClipboardExt;
use tauri_plugin_shell::ShellExt;
use tokio::sync::{Mutex, Notify};

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ServerItem {
    name: String,
    ip: String,
    connect_ip: String,
    port: u16,
    display_ip: String,
    map: String,
    players: u32,
    max_players: u32,
    online: bool,
    ping: i32,
    game_type: String,
    image_url: Option<String>,
    map_cn: Option<String>,
    map_tw: Option<String>,
    query_source: Option<String>,
}

type Snapshot = HashMap<String, Vec<ServerItem>>;
type CmdResult<T> = Result<T, String>;

#[derive(Debug, Clone, Serialize, Deserialize)]
struct DiffSummary {
    changed_servers: usize,
    map_changed: usize,
    online_changed: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct Diagnostics {
    servers_url: String,
    last_fetch_time: Option<DateTime<Utc>>,
    last_status: Option<String>,
    last_error: Option<String>,
    etag: Option<String>,
    hits_304: u64,
    jitter_min_seconds: u64,
    jitter_max_seconds: u64,
    current_backoff_seconds: Option<u64>,
    next_poll_time: Option<DateTime<Utc>>,
    last_snapshot_time: Option<DateTime<Utc>>,
    diff_summary: DiffSummary,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct Settings {
    servers_url: String,
    theme: String,
    notifications_enabled: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct SubscriptionsState {
    subscriptions: HashMap<String, Vec<String>>,
    last_seen_map: HashMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct AutoJoinHistoryEntry {
    timestamp: DateTime<Utc>,
    state: String,
    detail: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct AutoJoinState {
    state: String,
    target_server_key: Option<String>,
    granted_until: Option<DateTime<Utc>>,
    cooldown_until: Option<DateTime<Utc>>,
    #[serde(default)]
    attempts: u32,
    #[serde(default = "default_max_attempts")]
    max_attempts: u32,
    history: VecDeque<AutoJoinHistoryEntry>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct PersistedState {
    settings: Settings,
    subscriptions: SubscriptionsState,
    autojoin: AutoJoinState,
}

struct RuntimeState {
    snapshot: Option<Snapshot>,
    previous_snapshot: Option<Snapshot>,
    diagnostics: Diagnostics,
    settings: Settings,
    subscriptions: SubscriptionsState,
    autojoin: AutoJoinState,
    startup_notifications_sent: bool,
}

struct PollControl {
    notify: Notify,
}

#[derive(Clone)]
struct AppState {
    runtime: std::sync::Arc<Mutex<RuntimeState>>,
    poll: std::sync::Arc<PollControl>,
}

const JITTER_MIN: u64 = 6;
const JITTER_MAX: u64 = 10;
const AUTOJOIN_COOLDOWN: u64 = 10;
const HISTORY_LIMIT: usize = 40;
const AUTOJOIN_MAX_ATTEMPTS: u32 = 10;

fn default_settings() -> Settings {
    Settings {
        servers_url: "https://www.cs2ze.org/servers.json".to_string(),
        theme: "system".to_string(),
        notifications_enabled: true,
    }
}

fn default_subscriptions() -> SubscriptionsState {
    SubscriptionsState {
        subscriptions: HashMap::new(),
        last_seen_map: HashMap::new(),
    }
}

fn default_autojoin() -> AutoJoinState {
    AutoJoinState {
        state: "Idle".to_string(),
        target_server_key: None,
        granted_until: None,
        cooldown_until: None,
        attempts: 0,
        max_attempts: AUTOJOIN_MAX_ATTEMPTS,
        history: VecDeque::new(),
    }
}

fn default_max_attempts() -> u32 {
    AUTOJOIN_MAX_ATTEMPTS
}

fn default_diagnostics(servers_url: String) -> Diagnostics {
    Diagnostics {
        servers_url,
        last_fetch_time: None,
        last_status: None,
        last_error: None,
        etag: None,
        hits_304: 0,
        jitter_min_seconds: JITTER_MIN,
        jitter_max_seconds: JITTER_MAX,
        current_backoff_seconds: None,
        next_poll_time: None,
        last_snapshot_time: None,
        diff_summary: DiffSummary {
            changed_servers: 0,
            map_changed: 0,
            online_changed: 0,
        },
    }
}

fn push_history(autojoin: &mut AutoJoinState, state: &str, detail: impl Into<String>) {
    autojoin.history.push_front(AutoJoinHistoryEntry {
        timestamp: Utc::now(),
        state: state.to_string(),
        detail: detail.into(),
    });
    while autojoin.history.len() > HISTORY_LIMIT {
        autojoin.history.pop_back();
    }
}

fn app_data_path(app: &AppHandle) -> PathBuf {
    app.path()
        .app_data_dir()
        .unwrap_or_else(|_| std::env::current_dir().unwrap_or_else(|_| PathBuf::from(".")))
        .join("cs2ze_state.json")
}

fn load_state(app: &AppHandle) -> PersistedState {
    let path = app_data_path(app);
    if let Ok(contents) = fs::read_to_string(path) {
        if let Ok(state) = serde_json::from_str::<PersistedState>(&contents) {
            return state;
        }
    }
    PersistedState {
        settings: default_settings(),
        subscriptions: default_subscriptions(),
        autojoin: default_autojoin(),
    }
}

fn save_state(app: &AppHandle, runtime: &RuntimeState) {
    let path = app_data_path(app);
    if let Some(parent) = path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    let payload = PersistedState {
        settings: runtime.settings.clone(),
        subscriptions: runtime.subscriptions.clone(),
        autojoin: runtime.autojoin.clone(),
    };
    if let Ok(contents) = serde_json::to_string_pretty(&payload) {
        let _ = fs::write(path, contents);
    }
}

fn server_key(item: &ServerItem) -> String {
    format!("{}:{}", item.ip, item.port)
}

fn compute_diff(prev: &Snapshot, next: &Snapshot) -> DiffSummary {
    let mut prev_map: HashMap<String, &ServerItem> = HashMap::new();
    let mut next_map: HashMap<String, &ServerItem> = HashMap::new();

    for servers in prev.values() {
        for item in servers {
            prev_map.insert(server_key(item), item);
        }
    }

    for servers in next.values() {
        for item in servers {
            next_map.insert(server_key(item), item);
        }
    }

    let mut changed_servers = 0;
    let mut map_changed = 0;
    let mut online_changed = 0;

    for (key, next_item) in &next_map {
        if let Some(prev_item) = prev_map.get(key) {
            let mut changed = false;
            if prev_item.players != next_item.players
                || prev_item.max_players != next_item.max_players
                || prev_item.online != next_item.online
                || prev_item.map != next_item.map
            {
                changed = true;
            }
            if changed {
                changed_servers += 1;
            }
            if prev_item.map != next_item.map {
                map_changed += 1;
            }
            if prev_item.online != next_item.online {
                online_changed += 1;
            }
        }
    }

    DiffSummary {
        changed_servers,
        map_changed,
        online_changed,
    }
}

fn notify_snapshot(app: &AppHandle, snapshot: &Snapshot) {
    let _ = app.emit("snapshot-updated", snapshot);
}

fn notify_diagnostics(app: &AppHandle, diagnostics: &Diagnostics) {
    let _ = app.emit("diagnostics-updated", diagnostics);
}

fn notify_autojoin(app: &AppHandle, autojoin: &AutoJoinState) {
    let _ = app.emit("autojoin-updated", autojoin);
}

fn notify_subscription(app: &AppHandle, message: &str, server_key: &str) {
    let _ = app.emit(
        "subscription-notification",
        serde_json::json!({
            "message": message,
            "server_key": server_key,
        }),
    );
}

async fn evaluate_subscriptions(app: &AppHandle, runtime: &mut RuntimeState, snapshot: &Snapshot) {
    for (_community_id, servers) in snapshot {
        for server in servers {
            let key = server_key(server);
            let map_value = server.map.trim();
            if map_value.is_empty() || map_value == "-" {
                runtime
                    .subscriptions
                    .last_seen_map
                    .insert(key.clone(), server.map.clone());
                continue;
            }
            let subscribed_maps = runtime.subscriptions.subscriptions.get(&key);
            if subscribed_maps.is_none() {
                runtime
                    .subscriptions
                    .last_seen_map
                    .insert(key.clone(), server.map.clone());
                continue;
            }
            let subscribed_maps = subscribed_maps.unwrap();
            let is_subscribed = subscribed_maps.iter().any(|m| m == map_value);
            if !is_subscribed {
                runtime
                    .subscriptions
                    .last_seen_map
                    .insert(key.clone(), server.map.clone());
                continue;
            }

            if !runtime.startup_notifications_sent {
                let map_display = display_map(server);
                let message = format!("Currently running: {} on {}", map_display, server.name);
                notify_subscription(app, &message, &key);
            } else {
                let last_seen = runtime
                    .subscriptions
                    .last_seen_map
                    .get(&key)
                    .cloned()
                    .unwrap_or_default();
                if last_seen != server.map {
                    let map_display = display_map(server);
                    let message = format!("Currently running: {} on {}", map_display, server.name);
                    notify_subscription(app, &message, &key);
                }
            }

            runtime
                .subscriptions
                .last_seen_map
                .insert(key.clone(), server.map.clone());

        }
    }
    runtime.startup_notifications_sent = true;
}

fn display_map(server: &ServerItem) -> String {
    let map_cn = server.map_cn.clone().unwrap_or_default();
    let map_tw = server.map_tw.clone().unwrap_or_default();
    if !map_cn.trim().is_empty() {
        return map_cn;
    }
    if !map_tw.trim().is_empty() {
        return map_tw;
    }
    if !server.map.trim().is_empty() && server.map.trim() != "-" {
        return server.map.clone();
    }
    "Unknown".to_string()
}

fn grant_condition(server: &ServerItem) -> bool {
    server.online && server.players < server.max_players && !server.map.is_empty() && server.map != "-"
}

fn update_autojoin_on_snapshot(
    app: &AppHandle,
    runtime: &mut RuntimeState,
    snapshot: &Snapshot,
) {
    let target_key = match &runtime.autojoin.target_server_key {
        Some(key) => key.clone(),
        None => return,
    };

    if runtime.autojoin.state == "Armed" {
        runtime.autojoin.state = "Waiting".to_string();
        push_history(
            &mut runtime.autojoin,
            "Waiting",
            "AutoJoin armed and waiting for slot",
        );
        notify_autojoin(app, &runtime.autojoin);
    }

    if runtime.autojoin.state != "Waiting" {
        return;
    }

    let mut server_match: Option<&ServerItem> = None;
    for servers in snapshot.values() {
        for server in servers {
            if server_key(server) == target_key {
                server_match = Some(server);
                break;
            }
        }
    }

    if let Some(server) = server_match {
        if grant_condition(server) {
            if runtime.autojoin.attempts >= runtime.autojoin.max_attempts {
                runtime.autojoin.state = "Stopped".to_string();
                runtime.autojoin.cooldown_until = None;
                push_history(
                    &mut runtime.autojoin,
                    "Stopped",
                    "AutoJoin stopped after max attempts",
                );
                notify_autojoin(app, &runtime.autojoin);
                return;
            }

            runtime.autojoin.attempts += 1;
            runtime.autojoin.state = "Cooldown".to_string();
            runtime.autojoin.granted_until = None;
            runtime.autojoin.cooldown_until =
                Some(Utc::now() + chrono::Duration::seconds(AUTOJOIN_COOLDOWN as i64));
            let attempts = runtime.autojoin.attempts;
            let server_name = server.name.clone();
            push_history(
                &mut runtime.autojoin,
                "Cooldown",
                format!("AutoJoin attempt {} for {}", attempts, server_name),
            );
            notify_autojoin(app, &runtime.autojoin);

            attempt_autojoin(app, server);
        }
    }
}

fn attempt_autojoin(app: &AppHandle, server: &ServerItem) {
    let connect_addr = format!("{}:{}", server.connect_ip, server.port);
    let clipboard = app.clipboard();
    if let Err(err) = clipboard.write_text(connect_addr.clone()) {
        eprintln!("Failed to copy AutoJoin address to clipboard: {}", err);
    }
    let steam_uri = format!("steam://rungameid/730/+connect {}", connect_addr);
    if let Err(err) = app.shell().open(&steam_uri, None) {
        eprintln!("Failed to open Steam URI {}: {}", steam_uri, err);
    }
}

async fn autojoin_timer_loop(app: AppHandle, state: AppState) {
    loop {
        tokio::time::sleep(Duration::from_millis(500)).await;
        let mut runtime = state.runtime.lock().await;
        let now = Utc::now();
        let mut updated = false;

        if runtime.autojoin.state == "Cooldown" {
            if let Some(cooldown_until) = runtime.autojoin.cooldown_until {
                if now >= cooldown_until {
                    runtime.autojoin.state = "Waiting".to_string();
                    runtime.autojoin.cooldown_until = None;
                    push_history(
                        &mut runtime.autojoin,
                        "Waiting",
                        "Cooldown finished",
                    );
                    updated = true;
                }
            }
        }

        if updated {
            notify_autojoin(&app, &runtime.autojoin);
            save_state(&app, &runtime);
        }
    }
}

async fn poll_loop(app: AppHandle, state: AppState) {
    let client = reqwest::Client::new();
    loop {
        let (servers_url, etag, backoff) = {
            let runtime = state.runtime.lock().await;
            (
                runtime.diagnostics.servers_url.clone(),
                runtime.diagnostics.etag.clone(),
                runtime.diagnostics.current_backoff_seconds,
            )
        };

        let delay = if let Some(backoff) = backoff {
            backoff
        } else {
            rand::thread_rng().gen_range(JITTER_MIN..=JITTER_MAX)
        };

        let next_poll_time = Utc::now() + chrono::Duration::seconds(delay as i64);
        {
            let mut runtime = state.runtime.lock().await;
            runtime.diagnostics.next_poll_time = Some(next_poll_time);
            notify_diagnostics(&app, &runtime.diagnostics);
        }

        let sleep = tokio::time::sleep(Duration::from_secs(delay));
        tokio::select! {
            _ = sleep => {},
            _ = state.poll.notify.notified() => {},
        }

        let mut request = client.get(&servers_url);
        if let Some(tag) = etag.clone() {
            request = request.header("If-None-Match", tag);
        }

        let response = request.send().await;
        let now = Utc::now();
        match response {
            Ok(resp) => {
                let status = resp.status();
                let new_etag = resp.headers().get("ETag").and_then(|v| v.to_str().ok()).map(|v| v.to_string());
                if status.as_u16() == 304 {
                    let mut runtime = state.runtime.lock().await;
                    runtime.diagnostics.last_fetch_time = Some(now);
                    runtime.diagnostics.last_status = Some("304".to_string());
                    runtime.diagnostics.last_error = None;
                    runtime.diagnostics.hits_304 += 1;
                    if let Some(etag) = new_etag {
                        runtime.diagnostics.etag = Some(etag);
                    }
                    runtime.diagnostics.current_backoff_seconds = None;
                    notify_diagnostics(&app, &runtime.diagnostics);
                    save_state(&app, &runtime);
                    continue;
                }

                if status.is_success() {
                    let snapshot = resp.json::<Snapshot>().await;
                    match snapshot {
                        Ok(snapshot) => {
                            let mut runtime = state.runtime.lock().await;
                            runtime.diagnostics.last_fetch_time = Some(now);
                            runtime.diagnostics.last_status = Some(status.as_u16().to_string());
                            runtime.diagnostics.last_error = None;
                            runtime.diagnostics.current_backoff_seconds = None;
                            if let Some(etag) = new_etag {
                                runtime.diagnostics.etag = Some(etag);
                            }
                            runtime.diagnostics.last_snapshot_time = Some(now);

                            let diff_summary = if let Some(prev) = &runtime.snapshot {
                                compute_diff(prev, &snapshot)
                            } else {
                                DiffSummary {
                                    changed_servers: 0,
                                    map_changed: 0,
                                    online_changed: 0,
                                }
                            };
                            runtime.diagnostics.diff_summary = diff_summary;

                            runtime.previous_snapshot = runtime.snapshot.clone();
                            runtime.snapshot = Some(snapshot.clone());

                            evaluate_subscriptions(&app, &mut runtime, &snapshot).await;
                            update_autojoin_on_snapshot(&app, &mut runtime, &snapshot);

                            notify_snapshot(&app, &snapshot);
                            notify_diagnostics(&app, &runtime.diagnostics);
                            notify_autojoin(&app, &runtime.autojoin);
                            save_state(&app, &runtime);
                        }
                        Err(err) => {
                            let mut runtime = state.runtime.lock().await;
                            runtime.diagnostics.last_fetch_time = Some(now);
                            runtime.diagnostics.last_status = Some(status.as_u16().to_string());
                            runtime.diagnostics.last_error = Some(err.to_string());
                            runtime.diagnostics.current_backoff_seconds = Some(next_backoff(runtime.diagnostics.current_backoff_seconds));
                            notify_diagnostics(&app, &runtime.diagnostics);
                            save_state(&app, &runtime);
                        }
                    }
                } else {
                    let mut runtime = state.runtime.lock().await;
                    runtime.diagnostics.last_fetch_time = Some(now);
                    runtime.diagnostics.last_status = Some(status.as_u16().to_string());
                    runtime.diagnostics.last_error = Some(format!("HTTP {}", status.as_u16()));
                    runtime.diagnostics.current_backoff_seconds = Some(next_backoff(runtime.diagnostics.current_backoff_seconds));
                    notify_diagnostics(&app, &runtime.diagnostics);
                    save_state(&app, &runtime);
                }
            }
            Err(err) => {
                let mut runtime = state.runtime.lock().await;
                runtime.diagnostics.last_fetch_time = Some(now);
                runtime.diagnostics.last_status = Some("error".to_string());
                runtime.diagnostics.last_error = Some(err.to_string());
                runtime.diagnostics.current_backoff_seconds = Some(next_backoff(runtime.diagnostics.current_backoff_seconds));
                notify_diagnostics(&app, &runtime.diagnostics);
                save_state(&app, &runtime);
            }
        }
    }
}

fn next_backoff(current: Option<u64>) -> u64 {
    let next = match current {
        Some(value) => value.saturating_mul(2),
        None => JITTER_MIN,
    };
    next.min(60)
}

#[tauri::command]
async fn refresh_now(state: State<'_, AppState>) -> CmdResult<()> {
    state.poll.notify.notify_one();
    Ok(())
}

#[tauri::command]
async fn get_snapshot(state: State<'_, AppState>) -> CmdResult<Option<Snapshot>> {
    let runtime = state.runtime.lock().await;
    Ok(runtime.snapshot.clone())
}

#[tauri::command]
async fn get_diagnostics(state: State<'_, AppState>) -> CmdResult<Diagnostics> {
    let runtime = state.runtime.lock().await;
    Ok(runtime.diagnostics.clone())
}

#[tauri::command]
async fn get_settings(state: State<'_, AppState>) -> CmdResult<Settings> {
    let runtime = state.runtime.lock().await;
    Ok(runtime.settings.clone())
}

#[tauri::command]
async fn get_subscriptions(state: State<'_, AppState>) -> CmdResult<SubscriptionsState> {
    let runtime = state.runtime.lock().await;
    Ok(runtime.subscriptions.clone())
}

#[tauri::command]
async fn get_autojoin(state: State<'_, AppState>) -> CmdResult<AutoJoinState> {
    let runtime = state.runtime.lock().await;
    Ok(runtime.autojoin.clone())
}

#[tauri::command]
async fn update_servers_url(
    state: State<'_, AppState>,
    app: AppHandle,
    servers_url: String,
) -> CmdResult<()> {
    let mut runtime = state.runtime.lock().await;
    runtime.settings.servers_url = servers_url.clone();
    runtime.diagnostics.servers_url = servers_url;
    runtime.diagnostics.etag = None;
    runtime.diagnostics.current_backoff_seconds = None;
    save_state(&app, &runtime);
    notify_diagnostics(&app, &runtime.diagnostics);
    state.poll.notify.notify_one();
    Ok(())
}

#[tauri::command]
async fn update_theme(
    state: State<'_, AppState>,
    app: AppHandle,
    theme: String,
) -> CmdResult<()> {
    let mut runtime = state.runtime.lock().await;
    runtime.settings.theme = theme;
    save_state(&app, &runtime);
    Ok(())
}

#[tauri::command]
async fn update_notifications(
    state: State<'_, AppState>,
    app: AppHandle,
    enabled: bool,
) -> CmdResult<()> {
    let mut runtime = state.runtime.lock().await;
    runtime.settings.notifications_enabled = enabled;
    save_state(&app, &runtime);
    Ok(())
}

#[tauri::command]
async fn set_subscriptions(
    state: State<'_, AppState>,
    app: AppHandle,
    server_key: String,
    maps: Vec<String>,
) -> CmdResult<()> {
    let mut runtime = state.runtime.lock().await;
    if maps.is_empty() {
        runtime.subscriptions.subscriptions.remove(&server_key);
    } else {
        runtime.subscriptions.subscriptions.insert(server_key, maps);
    }
    save_state(&app, &runtime);
    Ok(())
}

#[tauri::command]
async fn arm_autojoin(
    state: State<'_, AppState>,
    app: AppHandle,
    server_key: String,
) -> CmdResult<()> {
    let mut runtime = state.runtime.lock().await;
    runtime.autojoin.state = "Armed".to_string();
    runtime.autojoin.target_server_key = Some(server_key.clone());
    runtime.autojoin.granted_until = None;
    runtime.autojoin.cooldown_until = None;
    runtime.autojoin.attempts = 0;
    push_history(
        &mut runtime.autojoin,
        "Armed",
        format!("Armed AutoJoin for {}", server_key),
    );
    notify_autojoin(&app, &runtime.autojoin);
    save_state(&app, &runtime);
    Ok(())
}

#[tauri::command]
async fn stop_autojoin(state: State<'_, AppState>, app: AppHandle) -> CmdResult<()> {
    let mut runtime = state.runtime.lock().await;
    runtime.autojoin.state = "Stopped".to_string();
    runtime.autojoin.target_server_key = None;
    runtime.autojoin.granted_until = None;
    runtime.autojoin.cooldown_until = None;
    runtime.autojoin.attempts = 0;
    push_history(&mut runtime.autojoin, "Stopped", "AutoJoin stopped");
    notify_autojoin(&app, &runtime.autojoin);
    save_state(&app, &runtime);
    Ok(())
}

#[tauri::command]
async fn join_now(
    state: State<'_, AppState>,
    app: AppHandle,
    connect_addr: String,
) -> CmdResult<()> {
    {
        let mut runtime = state.runtime.lock().await;
        if runtime.autojoin.state != "Granted" {
            return Ok(());
        }
        runtime.autojoin.state = "Joining".to_string();
        push_history(
            &mut runtime.autojoin,
            "Joining",
            format!("Attempting join for {}", connect_addr),
        );
        notify_autojoin(&app, &runtime.autojoin);
        save_state(&app, &runtime);
    }

    let clipboard = app.clipboard();
    clipboard
        .write_text(connect_addr.clone())
        .map_err(|e| e.to_string())?;

    let steam_uri = format!("steam://rungameid/730/+connect {}", connect_addr);
    if let Err(err) = app.shell().open(&steam_uri, None) {
        eprintln!("Failed to open Steam URI {}: {}", steam_uri, err);
    }

    let mut runtime = state.runtime.lock().await;
    runtime.autojoin.state = "Cooldown".to_string();
    runtime.autojoin.cooldown_until =
        Some(Utc::now() + chrono::Duration::seconds(AUTOJOIN_COOLDOWN as i64));
    runtime.autojoin.granted_until = None;
    push_history(&mut runtime.autojoin, "Cooldown", "Join attempt triggered");
    notify_autojoin(&app, &runtime.autojoin);
    save_state(&app, &runtime);
    Ok(())
}

#[tauri::command]
async fn copy_diagnostics(state: State<'_, AppState>, app: AppHandle) -> CmdResult<()> {
    let runtime = state.runtime.lock().await;
    let diagnostics = &runtime.diagnostics;
    let report = format!(
        "CS2ZE Diagnostics\nURL: {}\nLast fetch: {:?}\nLast status: {:?}\nLast error: {:?}\nETag: {:?}\n304 hits: {}\nJitter: {}-{}s\nBackoff: {:?}\nLast snapshot: {:?}\nDiff: changed={}, map_changed={}, online_changed={}",
        diagnostics.servers_url,
        diagnostics.last_fetch_time,
        diagnostics.last_status,
        diagnostics.last_error,
        diagnostics.etag,
        diagnostics.hits_304,
        diagnostics.jitter_min_seconds,
        diagnostics.jitter_max_seconds,
        diagnostics.current_backoff_seconds,
        diagnostics.last_snapshot_time,
        diagnostics.diff_summary.changed_servers,
        diagnostics.diff_summary.map_changed,
        diagnostics.diff_summary.online_changed,
    );
    let clipboard = app.clipboard();
    clipboard.write_text(report).map_err(|e| e.to_string())?;
    Ok(())
}

fn setup_runtime(app: &AppHandle) -> RuntimeState {
    let persisted = load_state(app);
    let diagnostics = default_diagnostics(persisted.settings.servers_url.clone());
    RuntimeState {
        snapshot: None,
        previous_snapshot: None,
        diagnostics,
        settings: persisted.settings,
        subscriptions: persisted.subscriptions,
        autojoin: persisted.autojoin,
        startup_notifications_sent: false,
    }
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_clipboard_manager::init())
        .setup(|app| {
            let app_handle = app.handle();
            let runtime_state = setup_runtime(&app_handle);
            let state = AppState {
                runtime: std::sync::Arc::new(Mutex::new(runtime_state)),
                poll: std::sync::Arc::new(PollControl { notify: Notify::new() }),
            };

            app.manage(state.clone());

            tauri::async_runtime::spawn(poll_loop(app_handle.clone(), state.clone()));
            tauri::async_runtime::spawn(autojoin_timer_loop(app_handle.clone(), state.clone()));
            state.poll.notify.notify_one();

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            refresh_now,
            get_snapshot,
            get_diagnostics,
            get_settings,
            get_subscriptions,
            get_autojoin,
            update_servers_url,
            update_theme,
            update_notifications,
            set_subscriptions,
            arm_autojoin,
            stop_autojoin,
            join_now,
            copy_diagnostics,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
