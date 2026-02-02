<script lang="ts">
  import { onMount } from "svelte";
  import { loadStaticResources } from "./lib/resources";
  import { normalizeServersSource, refreshServersNow, startServersPoller, stopServersPoller } from "./lib/servers";
  import {
    filterCommunitiesBySearch,
    getMapTranslationEntry,
    matchesServerSearch,
    normalizeSearchText,
    sortServers
  } from "./lib/selectors";
  import {
    loadMapSubscriptions,
    removeMapSubscription,
    saveMapSubscriptions,
    upsertMapSubscription,
    type MapSubscription
  } from "./lib/mapSubscriptions";
  import type { ServerItem } from "./lib/types";
  import {
    communities as communitiesStore,
    languagePack,
    mapTranslations as mapTranslationsStore,
    resourceOffline,
    serverLoadError,
    serversByCommunity
  } from "./lib/stores";
  import {
    appSettings,
    DEFAULT_UI_LANGUAGE,
    setServersSource,
    setSidebarCollapsed,
    setTheme,
    setUiLanguage,
    setViewMode
  } from "./lib/settingsStore";

  type Community = {
    id: string;
    name: string;
    short_name?: string;
    logo?: string;
  };

  type Server = ServerItem & { map_display?: string };

  const ICONS = {
    server:
      '<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M9 2a3 3 0 0 0-3 3v14a3 3 0 0 0 3 3h6a3 3 0 0 0 3-3V5a3 3 0 0 0-3-3H9Zm-.5 4.75A.75.75 0 0 1 9.25 6h5.5a.75.75 0 0 1 0 1.5h-5.5a.75.75 0 0 1-.75-.75Zm0 11a.75.75 0 0 1 .75-.75h5.5a.75.75 0 0 1 0 1.5h-5.5a.75.75 0 0 1-.75-.75Zm0-3a.75.75 0 0 1 .75-.75h5.5a.75.75 0 0 1 0 1.5h-5.5a.75.75 0 0 1-.75-.75Z" fill="currentColor"/></svg>',
    search_sub:
      '<svg width="24" height="24" fill="none" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M10 2.5a7.5 7.5 0 0 1 5.964 12.048l4.743 4.745a1 1 0 0 1-1.32 1.497l-.094-.083-4.745-4.743A7.5 7.5 0 1 1 10 2.5Zm0 2a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11Z" fill="currentColor"/></svg>',
    stats:
      '<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M9 5.23a2.25 2.25 0 0 1 2.25-2.25h1.5A2.25 2.25 0 0 1 15 5.23V21H9V5.23ZM7.5 10H5.25A2.25 2.25 0 0 0 3 12.25v8c0 .415.336.75.75.75H7.5V10ZM16.5 21h3.75a.75.75 0 0 0 .75-.75v-11A2.25 2.25 0 0 0 18.75 7H16.5v14Z" fill="currentColor"/></svg>',
    feedback:
      '<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M5 3a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h4l3.2 3.2a.75.75 0 0 0 1.28-.53V17H19a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2H5Zm2.5 5.75a.75.75 0 0 1 .75-.75h7a.75.75 0 0 1 0 1.5h-7a.75.75 0 0 1-.75-.75Zm.75 3.25a.75.75 0 0 0 0 1.5H13a.75.75 0 0 0 0-1.5H8.25Z" fill="currentColor"/></svg>',
    map:
      '<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M8.5 4.358v12.465l-4.32 3.038a.75.75 0 0 1-1.174-.509l-.007-.104V8.615a.75.75 0 0 1 .238-.548l.08-.065L8.5 4.358Zm12.494.29.007.104v10.633a.75.75 0 0 1-.238.548l-.08.065L15.5 19.64V7.174l4.32-3.035a.75.75 0 0 1 1.174.509ZM10 4.359l4 2.812v12.467l-4-2.814V4.359Z" fill="currentColor"/></svg>',
    edit:
      '<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z" fill="currentColor"/></svg>',
    list:
      '<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M3 6a1 1 0 0 1 1-1h16a1 1 0 1 1 0 2H4a1 1 0 0 1-1-1zm0 6a1 1 0 0 1 1-1h16a1 1 0 1 1 0 2H4a1 1 0 0 1-1-1zm1 5a1 1 0 1 0 0 2h16a1 1 0 1 0 0-2H4z" fill="currentColor"/></svg>',
    grid:
      '<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M4 6a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6Zm10-2a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2V6ZM4 16a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-4Zm10-2a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-4Z" fill="currentColor"/></svg>',
    sort:
      '<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M3 18h6v-2H3v2zM3 6v2h18V6H3zm0 7h12v-2H3v2z" fill="currentColor"/></svg>',
    lang:
      '<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M18 2a1 1 0 1 0-2 0v1h-4a1 1 0 0 0-1 1v1.25a1 1 0 1 0 2 0V5h8v.25a1 1 0 1 0 2 0V4a1 1 0 0 0-1-1h-4V2ZM8.563 7.505l.056.117 5.307 13.005a1 1 0 0 1-1.801.86l-.05-.105L10.692 18H4.407l-1.49 3.407a1 1 0 0 1-1.208.555l-.11-.04a1 1 0 0 1-.555-1.208l.04-.11L6.777 7.6c.337-.77 1.395-.795 1.786-.094Zm-.902 3.062L5.282 16h4.595l-2.216-5.432ZM13.499 7a1 1 0 0 1 1-1h5a1 1 0 0 1 .708 1.707L18.414 9.5H22a1 1 0 1 1 0 2h-4v2.984a2.5 2.5 0 0 1-3.219 2.394l-.569-.17a1 1 0 1 1 .575-1.916l.569.17a.5.5 0 0 0 .643-.478V11.5H12a1 1 0 1 1 0-2h4a1 1 0 0 1 .292-.707L17.085 8H14.5a1 1 0 0 1-1-1Z" fill="currentColor"/></svg>',
    settings:
      '<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M12 8.6a3.4 3.4 0 1 0 0 6.8 3.4 3.4 0 0 0 0-6.8ZM4 13.5l-1.5 1.1 1.6 2.8 1.8-.5c.3.3.7.6 1.1.8l.3 1.9h3.2l.3-1.9c.4-.2.8-.5 1.1-.8l1.8.5 1.6-2.8-1.5-1.1c.1-.5.1-1 0-1.5l1.5-1.1-1.6-2.8-1.8.5c-.3-.3-.7-.6-1.1-.8l-.3-1.9h-3.2l-.3 1.9c-.4.2-.8.5-1.1.8l-1.8-.5-1.6 2.8L4 12c-.1.5-.1 1 0 1.5Z" fill="currentColor"/></svg>',
    theme:
      '<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10Zm0-2V4a8 8 0 1 1 0 16Z" fill="currentColor"/></svg>'
  };

  const LOGO_PATH = "/static/nerv_logo.png";

  let curLang = DEFAULT_UI_LANGUAGE;
  let isCollapsed = false;
  let isDark = false;
  let viewMode: "grid" | "list" = "list";
  let showLangMenu = false;
  let isMobile = false;
  let sortByPlayers = false;
  let curView: "servers" | "map_sub" | "stats" | "feedback" | "settings" = "servers";
  let isEditMode = false;

  let serverMapQueryInput = "";
  let serverMapQuery = "";
  let mapSubs: MapSubscription[] = [];
  let mapSearchInput = "";
  let mapSearch = "";
  let mapSearchResults: string[] = [];
  let selectedMap = "";
  let selectedComms: string[] = [];
  let showConfirmModal = false;

  let communities: Community[] = [];
  let filteredCommunities: Community[] = [];
  let serverSearchNotice = "";
  let emptyNotice = "";

  const getFallbackLanguage = (pack: Record<string, Record<string, string>>) => {
    if (pack["zh_cn"]) return "zh_cn";
    if (pack["zh-CN"]) return "zh-CN";
    const fallback = Object.keys(pack).find((lang) => lang.toLowerCase().startsWith("zh"));
    return fallback ?? DEFAULT_UI_LANGUAGE;
  };

  const t = (key: string) => {
    const pack = $languagePack ?? {};
    const fallbackLang = getFallbackLanguage(pack);
    return pack[curLang]?.[key] ?? pack[fallbackLang]?.[key] ?? String(key);
  };

  const getLanguageLabel = (code: string) => {
    const lower = code.toLowerCase();
    if (lower.startsWith("zh") && (lower.includes("tw") || lower.includes("hk") || lower.includes("hant"))) {
      return "繁體中文";
    }
    if (lower.startsWith("zh")) return "中文";
    if (lower.startsWith("en")) return "English";
    return code;
  };

  const getAvailableLanguages = () => {
    const pack = $languagePack ?? {};
    const keys = Object.keys(pack);
    return keys.length ? keys : [curLang];
  };

  const isTraditionalLanguage = (lang: string) => {
    const lower = lang.toLowerCase();
    return lower.includes("tw") || lower.includes("hk") || lower.includes("hant");
  };

  $: if ($communitiesStore.length) {
    communities = $communitiesStore as Community[];
  }

  $: {
    curLang = $appSettings.ui_language;
    isCollapsed = $appSettings.sidebar_collapsed;
    viewMode = $appSettings.view_mode;
    isDark = $appSettings.theme === "dark";
  }

  $: {
    document.title = t("app_title");
  }

  const getServers = (communityId: string) => {
    const list = ($serversByCommunity[communityId] ?? []).map((server) => {
      const entry = getMapTranslationEntry(server.map, server, $mapTranslationsStore);
      let mapDisplay = "";
      if (isTraditionalLanguage(curLang)) mapDisplay = entry.zh_tw || entry.zh_cn || "";
      if (!mapDisplay) mapDisplay = entry.zh_cn || "";
      return { ...server, map_display: mapDisplay };
    });
    const query = serverMapQuery.trim();
    let filtered = list;
    if (query) {
      filtered = list.filter((server) =>
        matchesServerSearch(server, query, $mapTranslationsStore, true)
      );
    }
    if (sortByPlayers) {
      filtered = sortServers(filtered);
    }
    return filtered;
  };

  $: serverMapQuery = serverMapQueryInput;
  $: mapSearch = mapSearchInput.trim();

  $: mapSearchResults = (() => {
    const maps = Object.keys($mapTranslationsStore ?? {});
    if (!mapSearch) return maps.slice(0, 50);
    const normalizedQuery = normalizeSearchText(mapSearch);
    const filtered = maps.filter((mapName) => {
      if (normalizeSearchText(mapName).includes(normalizedQuery)) return true;
      const entry = getMapTranslationEntry(mapName, null, $mapTranslationsStore);
      return [entry.zh_cn, entry.zh_tw].some((value) =>
        normalizeSearchText(value || "").includes(normalizedQuery)
      );
    });
    return filtered.filter((mapName) => normalizeSearchText(mapName) !== normalizedQuery);
  })();

  $: filteredCommunities = filterCommunitiesBySearch(
    communities,
    (comm) => getServers(comm.id).length > 0,
    serverMapQuery
  );

  $: serverSearchNotice = (() => {
    const query = serverMapQuery.trim();
    if (!query) return "";
    let count = 0;
    filteredCommunities.forEach((comm) => {
      count += getServers(comm.id).length;
    });
    if (count === 0) {
      return t("server_search_empty").replace("{map}", query);
    }
    return "";
  })();

  const toggleSidebar = () => {
    setSidebarCollapsed(!isCollapsed);
  };

  const toggleTheme = () => {
    setTheme(isDark ? "light" : "dark");
  };

  const toggleViewMode = () => {
    setViewMode(viewMode === "grid" ? "list" : "grid");
  };

  const toggleSortByPlayers = () => {
    sortByPlayers = !sortByPlayers;
  };

  const scrollToComm = (id: string) => {
    const el = document.getElementById(`comm-${id}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  const setLang = (lang: string) => {
    setUiLanguage(lang);
    showLangMenu = false;
    const url = new URL(window.location.href);
    if (lang === DEFAULT_UI_LANGUAGE) {
      url.searchParams.delete("lang");
    } else {
      url.searchParams.set("lang", lang);
    }
    window.history.replaceState({}, "", url.toString());
  };

  const handleResize = () => {
    isMobile = window.innerWidth <= 768;
  };

  $: {
    const totalServers = Object.values($serversByCommunity).reduce(
      (sum, list) => sum + list.length,
      0
    );
    emptyNotice = !$serverLoadError && totalServers === 0 ? t("server_empty") : "";
  }

  onMount(() => {
    const queryLang = new URLSearchParams(window.location.search).get("lang");
    if (queryLang) {
      setUiLanguage(queryLang);
    }

    handleResize();
    window.addEventListener("resize", handleResize);

    loadStaticResources();
    mapSubs = loadMapSubscriptions();
    startServersPoller();

    return () => {
      window.removeEventListener("resize", handleResize);
      stopServersPoller();
    };
  });

  $: {
    if (isCollapsed) {
      document.documentElement.classList.add("sidebar-is-collapsed");
    } else {
      document.documentElement.classList.remove("sidebar-is-collapsed");
    }
  }

  $: {
    if (isDark) {
      document.documentElement.setAttribute("data-theme", "dark");
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
  }

  let serversSourceInput = "";
  let serversSourceDirty = false;
  let normalizedServersSource = normalizeServersSource($appSettings.servers_source);
  $: if (!serversSourceDirty) {
    serversSourceInput = $appSettings.servers_source;
  }
  $: normalizedServersSource = normalizeServersSource(serversSourceInput);

  const saveServersSource = async () => {
    setServersSource(serversSourceInput);
    serversSourceDirty = false;
    await loadStaticResources();
    await refreshServersNow();
  };

  const handleLanguageChange = (event: Event) => {
    const target = event.currentTarget as HTMLSelectElement;
    setLang(target.value);
  };

  const selectMap = (mapName: string) => {
    selectedMap = mapName;
    selectedComms = [];
    showConfirmModal = false;
  };

  const toggleComm = (commId: string) => {
    if (commId === "all") {
      selectedComms = ["all"];
      return;
    }
    const next = new Set(selectedComms.filter((value) => value !== "all"));
    if (next.has(commId)) {
      next.delete(commId);
    } else {
      next.add(commId);
    }
    selectedComms = Array.from(next);
  };

  const openConfirmModal = () => {
    if (!selectedMap || selectedComms.length === 0) return;
    showConfirmModal = true;
  };

  const confirmSubscription = () => {
    if (!selectedMap || selectedComms.length === 0) return;
    mapSubs = upsertMapSubscription(mapSubs, selectedMap, selectedComms);
    saveMapSubscriptions(mapSubs);
    showConfirmModal = false;
    selectedComms = [];
    selectedMap = "";
  };

  const removeSubscription = (mapName: string) => {
    mapSubs = removeMapSubscription(mapSubs, mapName);
    saveMapSubscriptions(mapSubs);
  };

  const getMapLabel = (mapName: string) => {
    const entry = getMapTranslationEntry(mapName, null, $mapTranslationsStore);
    const trad = entry.zh_tw || entry.zh_cn;
    return trad ? `${mapName} · ${trad}` : mapName;
  };

  const formatCommLabel = (commId: string) => {
    if (commId === "all") return t("all");
    const match = communities.find((comm) => comm.id === commId);
    return match?.name ?? commId;
  };
</script>

<div
  id="app"
  on:click={() => (showLangMenu = false)}
  style={isMobile ? "" : "display: flex; width: 100%; height: 100%;"}
>
  <div id="sidebar" class:collapsed={isCollapsed} on:click|stopPropagation>
    <button class="hamburger-btn" type="button" on:click={toggleSidebar}>
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
        <path d="M3 6h18M3 12h18M3 18h18" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
      </svg>
    </button>
    <div class="sidebar-logo"><img src={LOGO_PATH} alt="Logo" decoding="async" /></div>

    <div class="nav-item" class:active={curView === "servers"} on:click={() => (curView = "servers")}>
      <div class="icon-svg">{@html ICONS.server}</div>
      {#if !isCollapsed}
        <span>{t("servers")}</span>
      {/if}
      {#if isCollapsed}
        <div class="tooltip">{t("servers")}</div>
      {/if}
    </div>

    <div class="nav-item" class:active={curView === "map_sub"} on:click={() => (curView = "map_sub")}>
      <div class="icon-svg">{@html ICONS.map}</div>
      {#if !isCollapsed}
        <span>{t("sub_menu")}</span>
      {/if}
      {#if isCollapsed}
        <div class="tooltip">{t("sub_menu")}</div>
      {/if}
    </div>

    <div class="nav-item" class:active={curView === "stats"} on:click={() => (curView = "stats")}>
      <div class="icon-svg">{@html ICONS.stats}</div>
      {#if !isCollapsed}
        <span>{t("stats")}</span>
      {/if}
      {#if isCollapsed}
        <div class="tooltip">{t("stats")}</div>
      {/if}
    </div>

    <div class="nav-item" class:active={curView === "feedback"} on:click={() => (curView = "feedback")}>
      <div class="icon-svg">{@html ICONS.feedback}</div>
      {#if !isCollapsed}
        <span>{t("feedback")}</span>
      {/if}
      {#if isCollapsed}
        <div class="tooltip">{t("feedback")}</div>
      {/if}
    </div>

    <div style="margin-top: auto; padding: 10px;">
      <div
        class="nav-item"
        class:edit-mode-active={isEditMode}
        on:click={() => (isEditMode = !isEditMode)}
      >
        <div class="icon-svg">{@html ICONS.edit}</div>
        {#if !isCollapsed}
          <span>{isEditMode ? t("exit_edit") : t("edit_order")}</span>
        {/if}
        {#if isCollapsed}
          <div class="tooltip">{t("edit_order")}</div>
        {/if}
      </div>
      <div
        class="nav-item"
        class:active={curView === "settings"}
        on:click={() => (curView = "settings")}
      >
        <div class="icon-svg">{@html ICONS.settings}</div>
        {#if !isCollapsed}
          <span>{t("settings")}</span>
        {/if}
        {#if isCollapsed}
          <div class="tooltip">{t("settings")}</div>
        {/if}
      </div>
    </div>
  </div>

  <div class="content-wrapper">
    {#if isEditMode}
      <div class="edit-banner"></div>
    {/if}
    <header>
      <div class="header-left">
        <div class="header-title-area">
          <div class="header-logo"><img src={LOGO_PATH} alt="Logo" /></div>
          {#if curView === "servers"}
            <h1>{t("app_title")}</h1>
          {/if}
          {#if curView === "map_sub"}
            <h1>{t("sub_menu")}</h1>
          {/if}
          {#if curView === "stats"}
            <h1>{t("stats")}</h1>
          {/if}
          {#if curView === "feedback"}
            <h1>{t("feedback")}</h1>
          {/if}
          {#if curView === "settings"}
            <h1>{t("settings")}</h1>
          {/if}
        </div>
      </div>

      <div class="header-toolbar" aria-hidden={curView !== "servers"}>
        {#if curView === "servers"}
          <button class="toolbar-btn" type="button" on:click={toggleViewMode}>
            <div class="icon-svg">{@html viewMode === "grid" ? ICONS.list : ICONS.grid}</div>
            <span>{viewMode === "grid" ? t("view_list") : t("view_grid")}</span>
          </button>
          <button
            class="toolbar-btn"
            type="button"
            class:active={sortByPlayers}
            on:click={toggleSortByPlayers}
          >
            <div class="icon-svg">{@html ICONS.sort}</div>
            <span>{t("sort_players")}</span>
          </button>
        {/if}
      </div>

      <div class="header-right">
        <div class="top-controls">
          <div style="position: relative;">
            <button
              class="control-btn"
              class:menu-active={showLangMenu}
              type="button"
              on:click|stopPropagation={() => (showLangMenu = !showLangMenu)}
            >
              <div class="icon-svg">{@html ICONS.lang}</div>
            </button>
            <div class="dropdown-menu" class:show={showLangMenu} on:click|stopPropagation>
              {#each getAvailableLanguages() as langKey}
                <div
                  class="dropdown-item"
                  class:active={curLang === langKey}
                  on:click={() => setLang(langKey)}
                >
                  {getLanguageLabel(langKey)}
                </div>
              {/each}
            </div>
          </div>
          <button class="control-btn" type="button" on:click={toggleTheme}>
            <div class="icon-svg">{@html ICONS.theme}</div>
          </button>
        </div>
      </div>
    </header>

    {#if curView === "servers"}
      <div class="community-nav">
        {#each filteredCommunities as comm}
          <div class="jump-pill" on:click={() => scrollToComm(comm.id)}>
            {#if comm.logo}
              <img src={comm.logo} alt={comm.name} loading="lazy" decoding="async" />
            {/if}
            <span>{comm.name}</span>
          </div>
        {/each}
      </div>

      <div class="server-search-bar">
        <input
          class="server-search-input"
          type="text"
          bind:value={serverMapQueryInput}
          placeholder={t("server_search_ph")}
        />
      </div>
    {/if}

    <div id="main-content">
      {#if curView === "servers"}
        <div class="animate-enter">
          {#if serverSearchNotice}
            <div class="server-search-hint">{serverSearchNotice}</div>
          {/if}
          {#if $resourceOffline}
            <div class="server-search-hint">{t("offline")}</div>
          {/if}
          {#if $serverLoadError}
            <div class="server-search-hint">{t("server_load_error")}</div>
          {/if}
          {#if emptyNotice}
            <div class="server-search-hint">{emptyNotice}</div>
          {/if}

          {#each filteredCommunities as comm}
            <div id={`comm-${comm.id}`} style="margin-bottom: 40px;">
              {#if !isMobile}
                <h3
                  class="desktop-header"
                  style="border-left: 4px solid var(--accent); padding-left: 10px; margin: 0 0 16px 0;"
                >
                  {comm.name}
                </h3>
              {/if}
              {#if isMobile}
                <div class="community-title-bar" id={`comm-mob-${comm.id}`}>
                  {#if comm.logo}
                    <img src={comm.logo} alt={comm.name} />
                  {/if}
                  {comm.name}
                </div>
              {/if}

              {#if getServers(comm.id).length === 0}
                {#if viewMode === "list" || isMobile}
                  <div class="skeleton-list">
                    {#each Array.from({ length: 5 }) as _, i}
                      <div class="skeleton-row" data-index={i}></div>
                    {/each}
                  </div>
                {:else}
                  <div class="skeleton-grid">
                    {#each Array.from({ length: 3 }) as _, i}
                      <div class="skeleton-card" data-index={i}></div>
                    {/each}
                  </div>
                {/if}
              {/if}

              {#if viewMode === "grid" && !isMobile}
                <div class="grid-container">
                  {#each getServers(comm.id) as server (server.display_ip || server.name)}
                    <div class={`card ${server.online ? "online" : ""}`}>
                      <div class="status-line"></div>
                      <div class="card-content">
                        <div>
                          <div class="card-header-row">
                            <div class="srv-name" title={server.name}>{server.name}</div>
                          </div>
                          <div class="info-block">
                            <div class="info-row">
                              <span class="info-label">{t("map")}</span>
                              <div class="map-info">
                                <span>{server.map ?? "-"}</span>
                                <div class="map-trans">
                                  <span>{server.map_display ?? ""}</span>
                                </div>
                              </div>
                            </div>
                            <div class="info-row">
                              <span class="info-label">{t("players")}</span>
                              <span>{server.players}/{server.max_players}</span>
                            </div>
                          </div>
                        </div>
                        <div class="actions">
                          <button class="btn btn-primary" type="button">{t("join_server")}</button>
                          <button class="btn btn-sec" type="button">{t("copy_console_cmd")}</button>
                        </div>
                      </div>
                    </div>
                  {/each}
                </div>
              {/if}

              {#if viewMode === "list" && !isMobile}
                <div class="list-container">
                  {#each getServers(comm.id) as server (server.display_ip || server.name)}
                    <div class={`list-row ${server.online ? "online" : ""}`}>
                      <div class="col-status"></div>
                      <div class="col-name" title={server.name}>{server.name}</div>
                      <div class="col-map">
                        <span class="map-name">{server.map ?? "-"}</span>
                        <span class="col-map-cn">{server.map_display ?? ""}</span>
                      </div>
                      <div class="col-players">{server.players}/{server.max_players}</div>
                      <div class="col-actions">
                        <button class="btn btn-primary" type="button">{t("join_server")}</button>
                        <button class="btn btn-sec" type="button">{t("copy_console_cmd")}</button>
                      </div>
                    </div>
                  {/each}
                </div>
              {/if}

              {#if isMobile}
                <div class="mobile-list-container">
                  {#each getServers(comm.id) as server (server.display_ip || server.name)}
                    <div class="mobile-item">
                      <div class="mobile-item-left">
                        <div class="mobile-srv-name">{server.name}</div>
                        <div class="mobile-map-name">
                          <span>{server.map ?? "-"}</span>
                          <span class="mobile-trans">{server.map_display ?? ""}</span>
                        </div>
                      </div>
                      <div class="mobile-item-right">
                        <div style={`color: ${server.online ? "var(--text-primary)" : "var(--status-offline)"}`}>
                          {server.online ? `${server.players}/${server.max_players}` : t("offline")}
                        </div>
                      </div>
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          {/each}
        </div>
      {:else if curView === "stats"}
        <div class="login-required">
          <strong>{t("stats")}</strong>
          <div>{t("not_implemented")}</div>
        </div>
      {:else if curView === "feedback"}
        <div class="login-required">
          <strong>{t("feedback")}</strong>
          <div>{t("not_implemented")}</div>
        </div>
      {:else if curView === "settings"}
        <div class="settings-panel animate-enter">
          <div class="settings-card">
            <div class="settings-field">
              <label class="settings-label" for="servers-source">{t("settings_server_source")}</label>
              <input
                id="servers-source"
                class="settings-input"
                type="text"
                bind:value={serversSourceInput}
                on:input={() => (serversSourceDirty = true)}
                placeholder={t("settings_server_source_ph")}
              />
              <div class="settings-hint">
                {t("settings_normalized")} {normalizedServersSource}
              </div>
              <div class="settings-actions">
                <button class="btn btn-primary" type="button" on:click={saveServersSource}>
                  {t("settings_save")}
                </button>
              </div>
            </div>

            <div class="settings-field">
              <label class="settings-label" for="ui-language">{t("settings_ui_language")}</label>
              <select
                id="ui-language"
                class="settings-select"
                value={curLang}
                on:change={handleLanguageChange}
              >
                {#each getAvailableLanguages() as langKey}
                  <option value={langKey}>{getLanguageLabel(langKey)}</option>
                {/each}
              </select>
            </div>

            <div class="settings-note">{t("feedback")} {t("not_implemented")}</div>
          </div>
        </div>
      {:else if curView === "map_sub"}
        <div class="settings-panel animate-enter">
          <div class="settings-card">
            <div class="settings-field">
              <label class="settings-label" for="map-sub-search">{t("sub_menu")}</label>
              <input
                id="map-sub-search"
                class="settings-input"
                type="text"
                bind:value={mapSearchInput}
                placeholder={t("server_search_ph")}
              />
              <div class="subscription-results">
                {#if mapSearch}
                  <button class="sub-result-btn" type="button" on:click={() => selectMap(mapSearch)}>
                    {mapSearch}
                  </button>
                {/if}
                {#each mapSearchResults as mapName}
                  <button class="sub-result-btn" type="button" on:click={() => selectMap(mapName)}>
                    {getMapLabel(mapName)}
                  </button>
                {/each}
              </div>
            </div>

            <div class="settings-field">
              <label class="settings-label">{t("sub_menu")}</label>
              <div class="subscription-selected">
                {#if selectedMap}
                  <strong>{getMapLabel(selectedMap)}</strong>
                {:else}
                  <span>{t("server_search_empty").replace("{map}", mapSearch || "...")}</span>
                {/if}
              </div>
              <div class="subscription-comms">
                <label class="subscription-comm">
                  <input
                    type="checkbox"
                    checked={selectedComms.includes("all")}
                    on:change={() => toggleComm("all")}
                  />
                  <span>{t("all")}</span>
                </label>
                {#each communities as comm}
                  <label class="subscription-comm">
                    <input
                      type="checkbox"
                      checked={selectedComms.includes(comm.id)}
                      on:change={() => toggleComm(comm.id)}
                    />
                    <span>{comm.name}</span>
                  </label>
                {/each}
              </div>
              <div class="settings-actions">
                <button
                  class="btn btn-primary"
                  type="button"
                  disabled={!selectedMap || selectedComms.length === 0}
                  on:click={openConfirmModal}
                >
                  {t("settings_save")}
                </button>
              </div>
            </div>
          </div>

          <div class="settings-card">
            <div class="settings-field">
              <label class="settings-label">{t("sub_menu")}</label>
              {#if mapSubs.length === 0}
                <div class="settings-note">{t("not_implemented")}</div>
              {:else}
                <div class="subscription-list">
                  {#each mapSubs as sub}
                    <div class="subscription-item">
                      <div>
                        <div class="subscription-map">{getMapLabel(sub.map)}</div>
                        <div class="subscription-comms-list">
                          {sub.comms.map(formatCommLabel).join(", ")}
                        </div>
                      </div>
                      <button class="btn btn-sec" type="button" on:click={() => removeSubscription(sub.map)}>
                        {t("remove")}
                      </button>
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          </div>
        </div>
      {/if}
    </div>
  </div>
</div>

{#if showConfirmModal}
  <div class="modal-backdrop" on:click={() => (showConfirmModal = false)}>
    <div class="modal-card" on:click|stopPropagation>
      <h3>{t("sub_menu")}</h3>
      <p>{getMapLabel(selectedMap)}</p>
      <p>{selectedComms.map(formatCommLabel).join(", ")}</p>
      <div class="modal-actions">
        <button class="btn btn-sec" type="button" on:click={() => (showConfirmModal = false)}>
          {t("cancel")}
        </button>
        <button class="btn btn-primary" type="button" on:click={confirmSubscription}>
          {t("settings_save")}
        </button>
      </div>
    </div>
  </div>
{/if}
