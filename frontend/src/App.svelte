<script lang="ts">
  import { onMount } from "svelte";
  import { getCurrent } from "@tauri-apps/api/window";
  import { listen } from "@tauri-apps/api/event";
  import {
    getSnapshot,
    getDiagnostics,
    getSettings,
    getSubscriptions,
    getAutoJoin,
    refreshNow,
    updateServersUrl,
    updateTheme,
    updateNotifications,
    setSubscriptions,
    armAutoJoin,
    stopAutoJoin,
    copyDiagnostics
  } from "./lib/api";
  import { snapshot, diagnostics, settings, subscriptions, autojoin, activePage } from "./lib/stores";
  import type { AutoJoinState, ServerRow } from "./lib/types";
  import { flattenSnapshot } from "./lib/utils";
  import { derived, get } from "svelte/store";

  const appWindow = getCurrent();

  let selectedKey: string | null = null;
  let selectedRow: ServerRow | undefined;
  let searchTerm = "";
  let mapInput = "";
  let sortMode = "players";
  let scrollTop = 0;
  let now = Date.now();
  let showOverflow = false;
  const rowHeight = 56;

  const rowsStore = derived(snapshot, ($snapshot) => {
    const rows = flattenSnapshot($snapshot);
    return rows;
  });

  let rows: ServerRow[] = [];
  let filteredRows: ServerRow[] = [];
  let visibleRows = { rows: [] as ServerRow[], offset: 0, totalHeight: 0 };

  $: rows = $rowsStore;
  $: {
    const term = searchTerm.trim().toLowerCase();
    filteredRows = term
      ? rows.filter(
          (row) =>
            row.name.toLowerCase().includes(term) || row.map_display.toLowerCase().includes(term)
        )
      : [...rows];
    if (sortMode === "ping") {
      filteredRows.sort((a, b) => (a.ping === -1 ? 9999 : a.ping) - (b.ping === -1 ? 9999 : b.ping));
    } else {
      filteredRows.sort((a, b) => b.players - a.players);
    }
  }
  $: {
    const containerHeight = 520;
    const startIndex = Math.max(0, Math.floor(scrollTop / rowHeight) - 6);
    const endIndex = Math.min(
      filteredRows.length,
      Math.ceil((scrollTop + containerHeight) / rowHeight) + 6
    );
    visibleRows = {
      rows: filteredRows.slice(startIndex, endIndex),
      offset: startIndex * rowHeight,
      totalHeight: filteredRows.length * rowHeight
    };
  }

  let notificationLog: string[] = [];

  const updateNotification = (message: string) => {
    notificationLog = [message, ...notificationLog].slice(0, 6);
    const currentSettings = get(settings);
    if (currentSettings?.notifications_enabled && "Notification" in window) {
      if (Notification.permission === "granted") {
        new Notification(message);
      } else if (Notification.permission !== "denied") {
        Notification.requestPermission().then((permission) => {
          if (permission === "granted") {
            new Notification(message);
          }
        });
      }
    }
  };

  const getCooldownRemaining = (autojoinState: AutoJoinState | null) => {
    if (!autojoinState?.cooldown_until) return null;
    const remainingMs = new Date(autojoinState.cooldown_until).getTime() - now;
    if (remainingMs <= 0) return null;
    return Math.ceil(remainingMs / 1000);
  };

  const handleScroll = (event: Event) => {
    scrollTop = (event.currentTarget as HTMLDivElement).scrollTop;
  };

  const onThemeChange = (event: Event) => {
    updateTheme((event.currentTarget as HTMLSelectElement).value);
  };

  const onNotificationsChange = (event: Event) => {
    updateNotifications((event.currentTarget as HTMLSelectElement).value === "on");
  };

  const onServersUrlChange = (event: Event) => {
    updateServersUrl((event.currentTarget as HTMLInputElement).value);
  };

  onMount(() => {
    (async () => {
      snapshot.set(await getSnapshot());
      diagnostics.set(await getDiagnostics());
      settings.set(await getSettings());
      subscriptions.set(await getSubscriptions());
      autojoin.set(await getAutoJoin());

      await listen("snapshot-updated", (event) => {
        snapshot.set(event.payload as any);
      });

      await listen("diagnostics-updated", (event) => {
        diagnostics.set(event.payload as any);
      });

      await listen("autojoin-updated", (event) => {
        autojoin.set(event.payload as any);
      });

      await listen("subscription-notification", (event) => {
        const payload = event.payload as { message: string };
        updateNotification(payload.message);
      });
    })();

    const timer = setInterval(() => {
      now = Date.now();
    }, 500);

    return () => clearInterval(timer);
  });

  const selectServer = (row: ServerRow) => {
    selectedKey = row.server_key;
  };

  const updateSubscriptionList = async (maps: string[]) => {
    if (!selectedKey) return;
    await setSubscriptions(selectedKey, maps);
    subscriptions.set(await getSubscriptions());
    mapInput = "";
  };

  $: selectedRow = $rowsStore.find((row) => row.server_key === selectedKey);
</script>

<div class="app-shell">
  <header class="titlebar" data-tauri-drag-region>
    <div class="drag-region">
      <div class="app-icon" aria-hidden="true"></div>
      <strong>CS2ZE</strong>
      <span>{$activePage}</span>
    </div>
    <div class="drag-region" style="justify-self: stretch;">
      <input
        placeholder="Search servers or maps"
        bind:value={searchTerm}
        style="width: 100%;"
      />
    </div>
    <div style="display: flex; gap: 8px; align-items: center;">
      <button on:click={() => refreshNow()}>Refresh</button>
      <div class="overflow">
        <button type="button" on:click={() => (showOverflow = !showOverflow)}>⋯</button>
        {#if showOverflow}
          <div class="overflow-menu">
            <button type="button" on:click={() => (activePage.set("Diagnostics"), (showOverflow = false))}>
              Diagnostics
            </button>
            <button type="button" on:click={() => (activePage.set("Settings"), (showOverflow = false))}>
              Settings
            </button>
            <button type="button" on:click={() => (copyDiagnostics(), (showOverflow = false))}>
              Copy report
            </button>
          </div>
        {/if}
      </div>
      <button on:click={() => appWindow.minimize()}>—</button>
      <button on:click={() => appWindow.toggleMaximize()}>⬜</button>
      <button on:click={() => appWindow.close()}>✕</button>
    </div>
  </header>

  <div class="content">
    <nav class="nav">
      {#each ["Servers", "Subscriptions", "AutoJoin", "Diagnostics", "Settings"] as page}
        <button class:active={$activePage === page} on:click={() => activePage.set(page)}>{page}</button>
      {/each}
    </nav>

    <main class="page">
      {#if $activePage === "Servers"}
        <div class="panel" style="display: flex; gap: 12px;">
          <span class="tag">All</span>
          <span class="tag">Online</span>
          <span class="tag">Empty</span>
          <select bind:value={sortMode}>
            <option value="players">Sort: Players</option>
            <option value="ping">Sort: Ping</option>
          </select>
        </div>

        <div class="split">
          <div class="panel server-list" on:scroll={handleScroll}>
            <div style={`height: ${visibleRows.totalHeight}px; position: relative;`}>
              <div style={`transform: translateY(${visibleRows.offset}px);`}>
                {#each visibleRows.rows as row (row.server_key)}
                  <button
                    type="button"
                    class={`server-row ${row.server_key === selectedKey ? "active" : ""}`}
                    on:click={() => selectServer(row)}
                    style={`height: ${rowHeight}px;`}
                  >
                    <div>
                      <strong>{row.name}</strong>
                      <div class="tag">{row.community_id}</div>
                    </div>
                    <div>{row.players}/{row.max_players}</div>
                    <div>{row.online ? "Online" : "Offline"}</div>
                    <div>{row.map_display}</div>
                    <div>{row.ping === -1 ? "—" : `${row.ping} ms`}</div>
                  </button>
                {/each}
              </div>
            </div>
          </div>

          <div class="panel" style="position: sticky; top: 0; align-self: start;">
            {#if selectedRow}
              <h3>{selectedRow.name}</h3>
              <div class="actions">
                <button
                  on:click={() => armAutoJoin(selectedRow.server_key)}
                  class="primary"
                >
                  AutoJoin
                </button>
                <button on:click={() => stopAutoJoin()}>Stop</button>
                <button on:click={() => navigator.clipboard.writeText(selectedRow.connect_addr)}>
                  Copy connect
                </button>
              </div>

              {#if $autojoin?.state === "Cooldown" && $autojoin?.target_server_key === selectedRow.server_key}
                {#if getCooldownRemaining($autojoin) !== null}
                  <div>Cooldown remaining: {getCooldownRemaining($autojoin)}s</div>
                {/if}
              {/if}

              <h4>Subscriptions</h4>
              <div class="actions">
                {#if $subscriptions?.subscriptions[selectedRow.server_key]?.length}
                  {#each $subscriptions.subscriptions[selectedRow.server_key] as map}
                    <span class="tag">{map}</span>
                  {/each}
                {:else}
                  <span class="tag">None</span>
                {/if}
              </div>
              <div style="margin-top: 8px; display: flex; gap: 8px;">
                <input
                  placeholder="Add map name"
                  bind:value={mapInput}
                />
                <button
                  on:click={() =>
                    updateSubscriptionList([
                      ...($subscriptions?.subscriptions[selectedRow.server_key] ?? []),
                      mapInput
                    ])
                  }
                >
                  Add
                </button>
              </div>

              <h4>Details</h4>
              <div>Server Key: {selectedRow.server_key}</div>
              <div>Display IP: {selectedRow.display_ip}</div>
              <div>Connect Addr: {selectedRow.connect_addr}</div>
              <div>Game Type: {selectedRow.game_type}</div>
              <div>Query Source: {selectedRow.query_source ?? ""}</div>
              <div>Ping: {selectedRow.ping}</div>
              <div>AutoJoin state: {$autojoin?.state}</div>
            {:else}
              <p>Select a server to see details.</p>
            {/if}
          </div>
        </div>
      {:else if $activePage === "Subscriptions"}
        <div class="panel">
          <h3>Subscriptions</h3>
          {#if $subscriptions}
            {#each Object.entries($subscriptions.subscriptions) as [key, maps]}
              <div class="notification">
                <strong>{key}</strong>
                <div>{maps.join(", ")}</div>
              </div>
            {/each}
          {:else}
            <p>No subscriptions yet.</p>
          {/if}
          <h4>Recent notifications</h4>
          {#each notificationLog as note}
            <div class="notification">{note}</div>
          {/each}
        </div>
      {:else if $activePage === "AutoJoin"}
        <div class="panel">
          <h3>AutoJoin</h3>
          <p>Target: {$autojoin?.target_server_key ?? "None"}</p>
          <p>State: {$autojoin?.state ?? "Idle"}</p>
          {#if $autojoin?.state === "Cooldown"}
            {#if getCooldownRemaining($autojoin) !== null}
              <p>Cooldown remaining: {getCooldownRemaining($autojoin)}s</p>
            {/if}
          {/if}
          <p>Next poll: {$diagnostics?.next_poll_time ?? ""}</p>
          <p>Last snapshot: {$diagnostics?.last_snapshot_time ?? ""}</p>
          <div>
            <h4>History</h4>
            {#each $autojoin?.history ?? [] as entry}
              <div class="notification">
                {entry.timestamp}: {entry.state} - {entry.detail}
              </div>
            {/each}
          </div>
        </div>
      {:else if $activePage === "Diagnostics"}
        <div class="panel">
          <h3>Diagnostics</h3>
          <p>Servers URL: {$diagnostics?.servers_url}</p>
          <p>Last fetch: {$diagnostics?.last_fetch_time}</p>
          <p>Status: {$diagnostics?.last_status}</p>
          <p>Error: {$diagnostics?.last_error}</p>
          <p>ETag: {$diagnostics?.etag}</p>
          <p>304 hits: {$diagnostics?.hits_304}</p>
          <p>Jitter: {$diagnostics?.jitter_min_seconds}-{$diagnostics?.jitter_max_seconds}s</p>
          <p>Backoff: {$diagnostics?.current_backoff_seconds ?? "None"}s</p>
          <p>Diff changed servers: {$diagnostics?.diff_summary.changed_servers}</p>
          <p>Diff map changed: {$diagnostics?.diff_summary.map_changed}</p>
          <p>Diff online changed: {$diagnostics?.diff_summary.online_changed}</p>
          <button on:click={() => copyDiagnostics()}>Copy report</button>
        </div>
      {:else if $activePage === "Settings"}
        <div class="panel">
          <h3>Settings</h3>
          <label>
            Theme
            <select
              value={$settings?.theme ?? "system"}
              on:change={onThemeChange}
            >
              <option value="system">System</option>
              <option value="dark">Dark</option>
              <option value="light">Light</option>
            </select>
          </label>
          <label>
            Notifications
            <select
              value={$settings?.notifications_enabled ? "on" : "off"}
              on:change={onNotificationsChange}
            >
              <option value="on">On</option>
              <option value="off">Off</option>
            </select>
          </label>
          <label>
            servers.json URL
            <input
              value={$settings?.servers_url}
              on:change={onServersUrlChange}
              style="width: 100%;"
            />
          </label>
          <p>About: CS2ZE Desktop v0.1</p>
        </div>
      {/if}
    </main>
  </div>

  <footer class="status-bar">
    <div>Snapshot: {$diagnostics?.last_snapshot_time ?? "-"}</div>
    <div>Status: {$diagnostics?.last_status ?? "-"}</div>
    <div>304 hits: {$diagnostics?.hits_304 ?? 0}</div>
    <div>Backoff: {$diagnostics?.current_backoff_seconds ?? "None"}</div>
  </footer>
</div>
