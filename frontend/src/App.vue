<template>
  <div
    :class="{ 'app-blurred': showLoginPrompt }"
    :style="isMobile ? {} : { display: 'flex', width: '100%', height: '100%' }"
    @click="closeDropdowns"
  >
    <div class="login-overlay" v-if="!embedMode && showLoginPrompt">
      <div class="login-modal">
        <h3>{{ t('steam_prompt_title') }}</h3>
        <p>{{ t('steam_prompt_desc') }}</p>
        <div class="login-modal-actions">
          <button class="auth-btn steam-login-btn" :disabled="steamAuthPending" @click.stop="startSteamLogin">
            <img class="steam-logo" :src="steamLogoPath" alt="Steam">
            {{ t('steam_login') }}
          </button>
          <button class="login-skip" @click.stop="dismissLoginPrompt">{{ t('steam_skip') }}</button>
        </div>
      </div>
    </div>

    <div id="sidebar" v-if="!embedMode" :class="{ collapsed: isCollapsed }" @click.stop>
      <button class="hamburger-btn" @click="toggleSidebar">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M3 6h18M3 12h18M3 18h18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
      </button>
      <div class="sidebar-logo"><img :src="currentLogoPath" alt="Logo" width="40" height="40" decoding="async"></div>

      <div class="nav-item" :class="{active: curView === 'servers'}" @click="goToView('servers')">
        <div class="icon-svg" v-html="icons.server"></div>
        <span v-if="!isCollapsed">{{ t('servers') }}</span>
        <div class="tooltip" v-if="isCollapsed">{{ t('servers') }}</div>
      </div>

      <div v-if="!isCollapsed && isEditMode" class="animate-enter">
        <div class="drag-hint">{{ t('drag_hint') }}</div>
        <div
          class="draggable-item"
          v-for="(comm, idx) in communities"
          :key="comm.id"
          draggable="true"
          @dragstart="onDragStart($event, idx)"
          @dragover.prevent
          @dragenter="onDragEnter($event, idx)"
          @dragleave="onDragLeave($event)"
          @drop="onDrop($event, idx)"
          :class="{ 'dragging': draggedIndex === idx, 'drag-over': dragOverIndex === idx }"
          style="padding: 10px; font-size:13px; background: rgba(128,128,128,0.05); margin-bottom:4px; border-radius:4px; display:flex; align-items:center; gap:8px;"
        >
          <div class="icon-svg" v-html="icons.drag" style="width:16px; opacity:0.5"></div>
          <span>{{ comm.name }}</span>
        </div>
      </div>

      <div class="nav-item" v-if="isLoggedIn" :class="{active: curView === 'map_sub'}" @click="goToView('map_sub')">
        <div class="icon-svg" v-html="icons.search_sub"></div>
        <span v-if="!isCollapsed">{{ t('sub_menu') }}</span>
        <div class="tooltip" v-if="isCollapsed">{{ t('sub_menu') }}</div>
      </div>

      <div class="nav-item" @click="goToView('map_cooldown')" v-if="hasFeature('map_cd')" :class="{active: curView === 'map_cooldown'}">
        <div class="icon-svg" v-html="icons.map"></div>
        <div v-if="!isCollapsed" style="display:flex; flex-direction:column; justify-content:center; line-height:1.2;">
          <span>{{ t('mapcd') }}</span>
          <span style="font-size: 10px; opacity: 0.7;">{{ t('exg_only') }}</span>
        </div>
        <div class="tooltip" v-if="isCollapsed">{{ t('mapcd') }}</div>
      </div>

      <div class="nav-item" v-if="isLoggedIn" :class="{active: curView === 'stats', disabled: !isLoggedIn}" @click="goToView('stats')">
        <div class="icon-svg" v-html="icons.stats"></div>
        <div v-if="!isCollapsed" style="display:flex; flex-direction:column; justify-content:center; line-height:1.2;">
          <span>{{ t('stats') }}</span>
          <span style="font-size: 10px; opacity: 0.7;">{{ t('stats_note') }}</span>
          <span v-if="!isLoggedIn" style="font-size: 10px; opacity: 0.7;">{{ t('login_required_short') }}</span>
        </div>
        <div class="tooltip" v-if="isCollapsed">{{ t('stats') }}</div>
      </div>
      <div class="nav-item" v-if="isLoggedIn" :class="{active: curView === 'feedback', disabled: !isLoggedIn}" @click="goToView('feedback')">
        <div class="icon-svg" v-html="icons.feedback"></div>
        <span v-if="!isCollapsed">{{ t('feedback') }}</span>
        <div class="tooltip" v-if="isCollapsed">{{ t('feedback') }}</div>
      </div>

      <div style="margin-top: auto; padding: 10px;">
        <div class="nav-item" @click="toggleEditMode" :class="{'edit-mode-active': isEditMode}">
          <div class="icon-svg" v-html="icons.edit"></div>
          <span v-if="!isCollapsed">{{ isEditMode ? t('exit_edit') : t('edit_order') }}</span>
          <div class="tooltip" v-if="isCollapsed">{{ t('edit_order') }}</div>
        </div>
      </div>
    </div>

    <div class="content-wrapper">
      <div class="edit-banner" v-if="!embedMode && isEditMode"></div>
      <header v-if="!embedMode">
        <div class="header-left">
          <div class="header-title-area">
            <div class="header-logo"><img :src="currentLogoPath" alt="Logo" width="32" height="32" decoding="async"></div>
            <h1 v-if="curView === 'servers'">{{ t('app_title') }}</h1>
            <h1 v-if="curView === 'map_sub'">{{ t('sub_menu') }}</h1>
            <h1 v-if="curView === 'map_cooldown'">{{ t('mapcd') }}</h1>
            <h1 v-if="curView === 'stats'">{{ t('stats') }}</h1>
            <h1 v-if="curView === 'feedback'">{{ t('feedback') }}</h1>
          </div>
        </div>

        <div class="header-right">
          <div class="auth-panel" v-if="!isMobile">
            <div class="auth-actions">
              <button class="auth-btn steam-login-btn" v-if="!isLoggedIn" :disabled="steamAuthPending" @click.stop="startSteamLogin">
                <img class="steam-logo" :src="steamLogoPath" alt="Steam">
                {{ t('steam_login') }}
              </button>
              <div v-if="isLoggedIn" class="user-menu-wrapper">
                <button class="profile-btn" @click.stop="toggleProfileMenu">
                  <img class="profile-avatar" :src="steamProfileAvatar" alt="Steam Avatar">
                </button>
                <div class="dropdown-menu profile-menu" :class="{show: showProfileMenu}" @click.stop>
                  <div class="dropdown-item">
                    <a v-if="steamId" :href="steamProfileUrlPrefix + steamId" target="_blank" class="profile-link">
                      {{ steamProfileName }} <span style="font-size:10px; opacity:0.5">↗</span>
                    </a>
                    <span v-else class="profile-name">{{ steamProfileName }}</span>
                  </div>
                  <div class="dropdown-item logout-item" @click.stop="logout">{{ t('logout') }}</div>
                </div>
              </div>
            </div>
          </div>
          <div class="header-toolbar" v-if="curView === 'servers'">
            <button class="toolbar-btn" @click.stop="toggleViewMode" :title="t('switch_view')">
              <div class="icon-svg" v-html="viewMode === 'grid' ? icons.list : icons.grid"></div>
              <span>{{ viewMode === 'grid' ? t('view_list') : t('view_grid') }}</span>
            </button>
            <button class="toolbar-btn" @click.stop="toggleSortByPlayers" :class="{active: sortByPlayers}" :title="t('sort_players')">
              <div class="icon-svg" v-html="icons.sort"></div>
              <span>{{ t('sort_btn') }}</span>
            </button>
          </div>

          <div class="top-controls">
            <div class="desktop-only-icon" v-if="isLoggedIn" style="position: relative;">
              <button class="control-btn" :class="{'menu-active': showSubPopover}" @click.stop="toggleSubPopover" :title="t('my_subs')">
                <div class="icon-svg" v-html="icons.bell"></div>
              </button>
              <div class="dropdown-menu sub-popover" :class="{show: showSubPopover}" @click.stop>
                <div v-if="subscriptions.length === 0" class="sub-pop-empty">{{ t('no_subs') }}</div>
                <div v-else>
                  <div class="sub-pop-item" v-for="sub in subscriptions.slice(0, 5)" :key="sub.map">
                    <div class="sub-pop-info">
                      <div class="sub-pop-map">{{ sub.map }}</div>
                      <div class="sub-pop-trans" v-if="isChineseLang && getMapTranslation(sub.map)">{{ getMapTranslation(sub.map) }}</div>
                    </div>
                    <div class="sub-pop-del" @click.stop="removeSubscriptionByMap(sub.map)" :title="t('unsubscribe')">
                      <div class="icon-svg" v-html="icons.trash" style="width:14px;"></div>
                    </div>
                  </div>
                </div>
                <div class="sub-pop-footer" @click.stop="goToSubPage">{{ t('manage_all') }}</div>
              </div>
            </div>

            <div style="position: relative;">
              <button class="control-btn" :class="{'menu-active': showLangMenu}" @click.stop="toggleLangMenu">
                <div class="icon-svg" v-html="icons.lang"></div>
              </button>
              <div class="dropdown-menu" :class="{show: showLangMenu}" @click.stop>
                <div class="dropdown-item" :class="{active: curLang.startsWith('zh')}" @click="setLang(defaultChineseLang)">中文</div>
                <div class="dropdown-item" :class="{active: curLang==='en'}" @click="setLang('en')">English</div>
              </div>
            </div>
            <button class="control-btn" @click="toggleTheme"><div class="icon-svg" v-html="icons.theme"></div></button>
          </div>
        </div>
      </header>

      <div class="community-nav" v-show="curView === 'servers'">
        <div class="jump-pill" v-for="comm in filteredCommunities" :key="comm.id" @click="scrollToComm(comm.id)">
        <img
          v-if="getCommunityLogoMeta(comm).url"
          :src="getCommunityLogoMeta(comm).url"
          :class="{
            'logo-svg': getCommunityLogoMeta(comm).isSvg,
            'logo-invert': getCommunityLogoMeta(comm).isSvg && isDark
          }"
          loading="lazy"
          decoding="async"
          width="16"
          height="16"
        />
        <span>{{ comm.name }}</span>
        </div>
      </div>

      <div class="server-search-bar" v-show="curView === 'servers'">
        <input class="server-search-input" type="text" v-model="serverMapQueryInput" :placeholder="t('server_search_ph')">
      </div>

      <div id="main-content" ref="mainContentRef" :class="{ 'is-mapcd-view': curView === 'map_cooldown' }">
        <div v-show="curView === 'servers'" class="animate-enter">
          <div v-if="serverSearchNotice" class="server-search-hint">
            {{ serverSearchNotice }}
          </div>
          <div v-for="comm in filteredCommunities" :key="comm.id" :id="'comm-' + comm.id" style="margin-bottom: 40px;">
            <h3 class="desktop-header" v-if="!isMobile" style="border-left: 4px solid var(--accent); padding-left: 10px; margin: 0 0 16px 0;">{{ comm.name }}</h3>
            <div class="community-title-bar" v-if="isMobile" :id="'comm-mob-' + comm.id">
              <img v-if="getCommunityLogoMeta(comm).url" :src="getCommunityLogoMeta(comm).url" :class="{ 'logo-svg': getCommunityLogoMeta(comm).isSvg, 'logo-invert': getCommunityLogoMeta(comm).isSvg && isDark }" width="20" height="20" loading="lazy" decoding="async">
              {{ comm.name }}
            </div>
            <div v-if="(!getServers(comm.id) || getServers(comm.id).length === 0)">
              <div v-if="viewMode === 'list' || isMobile" class="skeleton-list">
                <div class="skeleton-row" v-for="i in 5" :key="i"></div>
              </div>

              <div v-else class="skeleton-grid">
                <div class="skeleton-card" v-for="i in 3" :key="i"></div>
              </div>
            </div>

            <div v-if="viewMode === 'grid' && !isMobile" class="grid-container">
              <div class="card" :class="{ 'online': s.online, 'has-image': s.image_url }" v-for="s in getServers(comm.id)" :key="s.display_ip">
                <div class="status-line"></div>
                <img class="card-bg-layer"
                  v-if="s.image_url"
                  :src="s.image_url"
                  loading="lazy"
                  decoding="async"
                  alt="Map">
                <div class="card-overlay" v-if="s.image_url"></div>
                <div class="card-content">
                  <div>
                    <div class="card-header-row">
                      <div class="srv-name" :title="s.name">{{ s.name }}</div>
                    </div>
                    <div class="info-block">
                      <div class="info-row"><span class="info-label">{{ t('map') }}</span> <div class="map-info"><span>{{ s.map || '-' }}</span><div class="map-trans" v-if="isChineseLang"><span v-if="getServerMapTranslation(s)">{{ getServerMapTranslation(s) }}</span><span v-if="!getServerMapTranslation(s) && s.map!='-'" style="opacity:0.6">{{ t('no_trans') }}</span></div></div></div>
                      <div class="info-row"><span class="info-label">{{ t('players') }}</span> <span>{{ s.players }}/{{ s.max_players }}</span></div>
                    </div>
                  </div>
                  <div class="actions">
                    <button class="btn btn-primary" @click="joinServer(s, comm)">{{ t('join_server') }}</button>
                    <button class="btn btn-sec" v-if="isLoggedIn" @click="copyCmd(s)">{{ t('copy_console_cmd') }}</button>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="viewMode === 'list' && !isMobile" class="list-container">
              <div class="list-row" :class="{ 'online': s.online }" v-for="s in getServers(comm.id)" :key="s.display_ip">
                <div class="col-status"></div>
                <div class="col-name" :title="s.name">{{ s.name }}</div>
                <div class="col-map"><span class="map-name">{{ s.map || '-' }}</span><span class="col-map-cn" v-if="isChineseLang">{{ getServerMapTranslation(s) || (s.map!='-' ? t('no_trans') : '') }}</span></div>
                <div class="col-players">{{ s.players }}/{{ s.max_players }}</div>
                <div class="col-actions">
                  <button class="btn btn-primary" @click="joinServer(s, comm)">{{ t('join_server') }}</button>
                  <button class="btn btn-sec" v-if="isLoggedIn" @click="copyCmd(s)">{{ t('copy_console_cmd') }}</button>
                </div>
              </div>
            </div>

            <div class="mobile-list-container" v-if="isMobile">
              <div class="mobile-item" v-for="s in getServers(comm.id)" :key="s.display_ip">
                <div class="mobile-item-left"><div class="mobile-srv-name">{{ s.name }}</div><div class="mobile-map-name"><span>{{ s.map || '-' }}</span><span class="mobile-trans" v-if="isChineseLang"> {{ getServerMapTranslation(s) || (s.map!='-' ? t('no_trans') : '') }}</span></div></div>
                <div class="mobile-item-right"><div :style="{color: s.online ? 'var(--text-primary)' : 'var(--status-offline)'}">{{ s.online ? s.players + '/' + s.max_players : t('offline') }}</div></div>
              </div>
            </div>
          </div>
        </div>

        <div v-show="curView === 'map_sub' && isLoggedIn" class="animate-enter map-sub-view">
          <div class="sub-container">
            <div class="perm-warning" v-if="notificationPermission !== 'granted'" @click="requestPerm">
              {{ t('notify_warn') }}
            </div>
            <div class="keep-alive-hint" v-if="notificationPermission === 'granted'">
              {{ t('keep_open_hint') }}
            </div>

            <div class="sub-search-area">
              <input type="text" class="sub-search-box" v-model="subSearchQuery" :placeholder="t('sub_search_ph')" @input="searchMaps">

              <div class="search-results-panel" v-if="searchResults.length > 0">
                <div class="search-res-item" :class="{selected: selectedMap === m.key}" v-for="m in searchResults" @click="selectMapToSub(m)">
                  <b>{{ m.key }}</b> <span v-if="m.val" style="opacity:0.8">({{ m.val }})</span>
                </div>
              </div>

              <div class="comm-select-area" v-if="selectedMap">
                <div style="font-weight:600; margin-bottom:8px;">{{ t('sub_confirm_title') }}: <span style="color:var(--accent)">{{ selectedMap }}</span></div>
                <div style="font-size:12px; color:var(--text-secondary); margin-bottom:8px;">{{ t('sub_select_comm') }}:</div>

                <div class="comm-options">
                  <div class="comm-pill" :class="{active: newSubComms.includes('all')}" @click="toggleSubComm('all')">
                    {{ t('all_comm') }}
                  </div>
                  <div class="comm-pill" :class="{active: newSubComms.includes(c.id)}" v-for="c in communities" @click="toggleSubComm(c.id)">
                    {{ c.short_name || c.name }}
                  </div>
                </div>

                <button class="btn btn-primary" style="margin-top:16px; width:100%" @click="addSubscription">
                  {{ t('subscribe_confirm') }}
                </button>
              </div>
            </div>

            <div style="border-top:1px solid var(--card-border); margin: 30px 0;"></div>

            <h3 style="margin-bottom:16px; opacity:0.8">{{ t('my_subs') }}</h3>
            <div class="sub-table" v-if="subscriptions.length > 0">
              <div class="sub-row" v-for="(sub, idx) in subscriptions" :key="idx">
                <div class="sub-col-info">
                  <div class="sub-map-key">{{ sub.map }}</div>
                  <div class="sub-map-val" v-if="isChineseLang && getMapIndexDisplayName(sub.map)">{{ getMapIndexDisplayName(sub.map) }}</div>
                  <div class="sub-tags">
                    <div class="sub-comms">{{ formatSubComms(sub.comms) }}</div>
                    <div
                      v-if="exgStatusByIndex[idx]"
                      class="exg-inline-status"
                      :class="{
                        'exg-inline-status--available': exgStatusByIndex[idx].state === 'available',
                        'exg-inline-status--cooldown': exgStatusByIndex[idx].state === 'cooldown',
                        'exg-inline-status--unavailable': exgStatusByIndex[idx].state !== 'available' && exgStatusByIndex[idx].state !== 'cooldown'
                      }"
                    >
                      <template v-if="exgStatusByIndex[idx].state === 'available'">
                        <svg class="exg-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                          <path d="M12 2c5.523 0 10 4.477 10 10s-4.477 10-10 10S2 17.523 2 12 6.477 2 12 2Zm3.22 6.97-4.47 4.47-1.97-1.97a.75.75 0 0 0-1.06 1.06l2.5 2.5a.75.75 0 0 0 1.06 0l5-5a.75.75 0 1 0-1.06-1.06Z" fill="currentColor"/>
                        </svg>
                        <span class="exg-inline-label">{{ t('map_sub_exg_available') }}</span>
                      </template>
                      <template v-else-if="exgStatusByIndex[idx].state === 'cooldown'">
                        <svg class="exg-icon" width="16" height="16" fill="none" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                          <path d="M12 5a8.5 8.5 0 1 1 0 17 8.5 8.5 0 0 1 0-17Zm0 3a.75.75 0 0 0-.743.648l-.007.102v4.5l.007.102a.75.75 0 0 0 1.486 0l.007-.102v-4.5l-.007-.102A.75.75 0 0 0 12 8Zm7.17-2.877.082.061 1.149 1a.75.75 0 0 1-.904 1.193l-.081-.061-1.149-1a.75.75 0 0 1 .903-1.193ZM14.25 2.5a.75.75 0 0 1 .102 1.493L14.25 4h-4.5a.75.75 0 0 1-.102-1.493L9.75 2.5h4.5Z" fill="currentColor"/>
                        </svg>
                        <span class="exg-inline-label">{{ t('map_sub_exg_cooldown') }}</span>
                        <span class="exg-inline-time">{{ exgStatusByIndex[idx].compactTime }}</span>
                      </template>
                      <template v-else>
                        <span class="exg-inline-label">{{ exgStatusByIndex[idx].label }}</span>
                      </template>
                    </div>
                  </div>
                </div>
                <div class="sub-actions">
                  <button class="btn-unsub" @click="removeSubscription(idx)">{{ t('unsubscribe') }}</button>
                </div>
              </div>
            </div>
            <div v-else style="text-align: center; padding: 40px; color: var(--text-secondary);">
              {{ t('no_subs') }}
            </div>

            <div class="sub-test-btn" @click="testNotification">{{ t('test_notify') }}</div>
          </div>
        </div>

        <div v-show="curView === 'stats'" class="animate-enter">
          <div v-if="isLoggedIn" class="stats-dashboard">
            <div class="stats-summary-row">
              <div class="summary-card">
                <div class="summary-label">{{ t('stats_total_label') }}</div>
                <div class="summary-value">{{ totalPlayers }}</div>
              </div>
              <div class="summary-card">
                <div class="summary-label">{{ t('stats_peak_label') }}</div>
                <div class="summary-value">{{ totalPeak48h }}</div>
              </div>
              <div class="summary-card" v-if="topCommunity">
                <div class="summary-label">{{ t('stats_top_label') }}</div>
                <div class="summary-value">{{ topCommunity.name }}</div>
                <div class="summary-sub">{{ topCommunity.count }} {{ t('stats_players_label') }}</div>
              </div>
            </div>

            <div class="stats-charts-row">
              <div class="chart-wrapper">
                <div class="chart-title">{{ t('stats_title') }}</div>
                <div class="chart-subtitle">{{ t('stats_time_note') }}</div>
                <div class="chart-content"><canvas id="statsLineChart"></canvas></div>
              </div>
              <div class="community-list-card">
                <div class="comm-list-header">{{ t('stats_distribution_label') }}</div>
                <div class="pie-container">
                  <canvas id="statsPieChart"></canvas>
                </div>
                <div class="comm-list-body">
                  <div class="comm-stat-row" v-for="item in currentStats" :key="item.id">
                    <div class="comm-stat-info">
                      <div class="comm-color-dot" :style="{background: item.color}"></div>
                      <div class="comm-stat-name">{{ item.name }}</div>
                    </div>
                    <div class="comm-stat-val">{{ item.count }}</div>
                  </div>
                </div>
              </div>
            </div>

            <div class="stats-advanced-toolbar">
              <button class="toolbar-btn" @click="toggleAdvancedStats">
                {{ showAdvancedStats ? 'Hide Advanced Analytics' : 'Show Advanced Analytics' }}
              </button>
            </div>

            <div v-if="showAdvancedStats" class="stats-advanced-panel">
              <div v-if="advancedStatsLoading" class="stats-advanced-state">Loading advanced analytics...</div>
              <div v-else-if="advancedStatsError" class="stats-advanced-state stats-advanced-state--error">{{ advancedStatsError }}</div>
              <template v-else-if="advancedStatsPayload">
                <div class="stats-advanced-grid">
                  <div class="stats-advanced-card">
                    <div class="chart-title">Run Chart in 7 days  (Total PCU/ACU)</div>
                    <div class="stats-advanced-canvas"><canvas id="statsAdvancedWeekChart"></canvas></div>
                  </div>
                  <div class="stats-advanced-card">
                    <div class="chart-title">Run Chart in 30 days  (Total PCU/ACU)</div>
                    <div class="stats-advanced-canvas"><canvas id="statsAdvancedMonthChart"></canvas></div>
                  </div>
                </div>

                <div class="stats-advanced-note">
                  Daily metrics (by community): PCU = daily peak CCU (max); ACU = daily average CCU (arithmetic mean of 10-minute samples). "Samples" is used to detect missing samples and resulting data distortion. WoW stands for "week-over-week"
                </div>
                <div class="stats-advanced-note">
                  For the full data table, please contact (English/中文): <a href="mailto:liwenyu2004@outlook.com">liwenyu2004@outlook.com</a>
                </div>

                <div class="stats-advanced-table-wrap">
                  <div class="comm-list-header">30-Day ZE Community Trend Overview</div>
                  <table class="stats-advanced-table">
                    <thead>
                      <tr>
                        <th>Communities</th>
                        <th>30d AVG PCU</th>
                        <th>30d AVG ACU</th>
                        <th>30d PEAK PCU</th>
                        <th>30d PEAK ACU</th>
                        <th>PCU WoW Growth Rate</th>
                        <th>ACU WoW Growth Rate</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="row in advancedMonthlySummaryRows" :key="row.community_id">
                        <td>{{ row.community_name }}</td>
                        <td>{{ formatStatNumber(row.avg_pcu_30d) }}</td>
                        <td>{{ formatStatNumber(row.avg_acu_30d) }}</td>
                        <td>{{ formatStatNumber(row.pcu_peak_30d) }}</td>
                        <td>{{ formatStatNumber(row.acu_peak_30d) }}</td>
                        <td :class="trendClass(row.pcu_trend_pct)">{{ formatTrend(row.pcu_trend_pct) }}</td>
                        <td :class="trendClass(row.acu_trend_pct)">{{ formatTrend(row.acu_trend_pct) }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <div class="stats-advanced-table-wrap">
                  <div class="comm-list-header">Daily Metrics (Past 7 Days, by Community)</div>
                  <table class="stats-advanced-table">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Communities</th>
                        <th>PCU</th>
                        <th>ACU</th>
                        <th>Samples</th>
                        <th>Expected</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="row in advancedRows7d" :key="`${row.date}-${row.community_id}`">
                        <td>{{ row.date }}</td>
                        <td>{{ row.community_name }}</td>
                        <td>{{ formatStatNumber(row.pcu) }}</td>
                        <td>{{ formatStatNumber(row.acu) }}</td>
                        <td>{{ row.samples }}</td>
                        <td>{{ row.expected_samples }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </template>
            </div>
          </div>
          <div v-else class="login-required">
            <strong>{{ t('login_required_title') }}</strong>
            <div>{{ t('login_required_stats') }}</div>
          </div>
        </div>

        <div v-show="curView === 'map_cooldown'" class="animate-enter mapcd-enter">
          <div class="mapcd-page">
            <div class="mapcd-view">
              <div class="mapcd-toolbar">
                <div class="mapcd-toolbar-row">
                  <div class="mapcd-title-wrap">
                    <h3 class="mapcd-title">
                      {{ mapcdAutoShowAll ? t('mapcd_title_fallback_all') : (isAllMapsMode ? t('mapcd_title_all') : t('mapcd_title_cooldown')) }}
                    </h3>
                    <span v-if="mapCooldownIsBuilding" class="mapcd-preparing">
                      {{ isChineseLang ? '准备中...' : 'Preparing...' }}{{ mapCooldownProgressText }}
                    </span>
                  </div>
                  <div class="mapcd-controls">
                     <button class="mapcd-toggle-btn" type="button" @click="toggleMapCooldownMode">
                      <span class="mapcd-toggle-icon" aria-hidden="true">
                        <!-- 褰撳墠鏄€滄樉绀哄叏閮ㄢ€濊鍥撅細鎸夐挳鏄剧ず鈥滀粎鍐峰嵈鈥?+ 闂归挓 icon -->
                      <svg v-if="isAllMapsMode" width="20" height="20" viewBox="0 0 24 24" fill="none"
                          xmlns="http://www.w3.org/2000/svg">
                          <path d="M12 5a8.5 8.5 0 1 1 0 17 8.5 8.5 0 0 1 0-17Zm0 3a.75.75 0 0 0-.743.648l-.007.102v4.5l.007.102a.75.75 0 0 0 1.486 0l.007-.102v-4.5l-.007-.102A.75.75 0 0 0 12 8Zm7.17-2.877.082.061 1.149 1a.75.75 0 0 1-.904 1.193l-.081-.061-1.149-1a.75.75 0 0 1 .903-1.193ZM14.25 2.5a.75.75 0 0 1 .102 1.493L14.25 4h-4.5a.75.75 0 0 1-.102-1.493L9.75 2.5h4.5Z"
                            fill="currentColor"/>
                      </svg>

                    <!-- 褰撳墠鏄€滀粎鍐峰嵈鈥濊鍥撅細鎸夐挳鏄剧ず鈥滄樉绀哄叏閮ㄢ€?+ 鍒楄〃 icon -->
                      <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none"
                        xmlns="http://www.w3.org/2000/svg">
                        <path d="M3 17h12a1 1 0 0 1 .117 1.993L15 19H3a1 1 0 0 1-.117-1.993L3 17h12H3Zm0-6h18a1 1 0 0 1 .117 1.993L21 13H3a1 1 0 0 1-.117-1.993L3 11h18H3Zm0-6h15a1 1 0 0 1 .117 1.993L18 7H3a1 1 0 0 1-.117-1.993L3 5h15H3Z"
                          fill="currentColor"/>
                      </svg>
                  </span>

                <span class="mapcd-toggle-label">
                  {{ isAllMapsMode ? t('mapcd_btn_only_cooldown','Only Cooldown') : t('mapcd_btn_show_all','Show All') }}
                </span>
                    </button>

                    <div class="mapcd-search">
                       <div class="mapcd-searchIcon" v-html="icons.search_sub"></div>
                       <input
                        ref="mapCooldownSearchInputRef"
                        class="mapcd-searchInput"
                        type="text"
                        v-model="mapCooldownQueryInput"
                        :placeholder="t('mapcd_search_ph')"
                        autocomplete="off"
                        spellcheck="false"
                        @keydown="onMapCooldownSearchKeydown"
                      >
                      <button v-if="mapCooldownQueryInput" class="mapcd-clearBtn" @click="clearMapCooldownSearchAndFocus">
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
                      </button>
                    </div>
                  </div>
                </div>
                <div v-if="mapcdAutoShowAll" class="mapcd-hint">{{ t('mapcd_hint_auto_all') }}</div>
              </div>

              <div class="mapcd-container" :class="{ 'is-fast': mapCooldownIsFastScrolling }">
                <div class="mapcd-table">
                  <div class="mapcd-header">
                    <div class="mapcd-cell mapcd-col-map">{{ t('map') }}</div>
                    <div class="mapcd-cell mapcd-col-ach">{{ t('achievement') }}</div>
                    <div
                      class="mapcd-cell mapcd-col-deadline sortable"
                      :class="{ active: mapcdSortMode === 'availability' }"
                      @click="onMapcdCooldownEndHeaderClick"
                    >
                      <span class="sort-label">{{ t('cooldown_deadline') }}</span>
                      <span class="sort-tri" aria-hidden="true">▲</span>
                    </div>
                    <div class="mapcd-cell mapcd-col-length">{{ t('cooldown_length') }}</div>
                    <div class="mapcd-cell mapcd-col-availability">{{ t('exg_availability') }}</div>
                  </div>
                  <div class="mapcd-body" ref="mapCooldownScrollRef" @scroll="onMapCooldownScroll">
                    <div class="mapcd-top-spacer" :style="{ height: `${mapCooldownTopSpacerPx}px` }"></div>

                    <div
                      class="mapcd-row"
                      :class="{
                        'is-fast': mapCooldownIsFastScrolling,
                        'is-fresh': isMapCooldownRowFresh(row.key),
                        'is-highlight': row.key === mapCooldownHighlightKey
                      }"
                      v-for="row in mapCooldownVisibleRows"
                      :key="row.key"
                      :data-key="row.key"
                    >
                      <div class="mapcd-cell mapcd-col-map">
                        <div class="mapcd-map-key-row">
                          <div class="mapcd-map-key">{{ row.mapLine1 }}</div>
                          <!-- 蹇粴鏃朵笉娓叉煋绗簩琛岋紙浣犲凡鏈?mapCooldownIsFastScrolling 杩欎釜鐘舵€侊級 -->
                          <div v-if="isChineseLang && row.mapLine2 && !mapCooldownIsFastScrolling" class="mapcd-map-cn">
                            {{ row.mapLine2 }}
                          </div>
                        </div>
                      </div>

                      <!-- 蹇粴鏃朵笉濉?achievement锛堥伩鍏嶅ぇ閲忔枃鏈妭鐐硅繘鍑猴級 -->
                      <div class="mapcd-cell mapcd-col-ach" :title="mapCooldownIsFastScrolling ? '' : row.achievement">
                        {{ mapCooldownIsFastScrolling ? '' : (row.achievement || '-') }}
                      </div>

                      <div class="mapcd-cell mapcd-col-deadline">{{ row.deadlineText }}</div>
                      <div class="mapcd-cell mapcd-col-length">{{ row.durationText }}</div>

                      <!-- 涓嶇敤 v-html锛氭敼鎴愬唴鑱?svg锛堣妭鐐规洿鍙帶锛?-->
                      <div class="mapcd-cell mapcd-col-availability">
                        <span class="mapcd-availability" :class="row.availability === 'available' ? 'is-available' : 'is-cooldown'">
                          <span class="mapcd-availability-icon" aria-hidden="true">
                            <svg v-if="row.availability === 'available'" width="14" height="14" viewBox="0 0 16 16" fill="none">
                              <path
                                d="M3.5 8.5l2.5 2.5 6-6"
                                stroke="currentColor"
                                stroke-width="2"
                                stroke-linecap="round"
                                stroke-linejoin="round"
                              />
                            </svg>
                            <svg v-else width="14" height="14" viewBox="0 0 16 16" fill="none">
                              <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
                            </svg>
                          </span>
                        </span>
                      </div>
                    </div>

                    <div class="mapcd-bottom-spacer" :style="{ height: `${mapCooldownBottomSpacerPx}px` }"></div>

                    <div
                      v-if="mapCooldownRows.length === 0 && !mapCooldownIsBuilding && !mapCooldownSearchQueryTrimmed"
                      class="mapcd-empty"
                    >
                      {{ t('no_data') }}
                    </div>

                    <div class="mapcd-edge-fade mapcd-edge-fade--top"></div>
                    <div class="mapcd-edge-fade mapcd-edge-fade--bottom"></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-show="curView === 'feedback'" class="animate-enter">
          <div class="feedback-panel">
            <h3>{{ t('feedback_dev_title') }}</h3>
            <p>{{ t('feedback_dev_desc') }}</p>
          </div>
        </div>
      </div>
      <div class="fixed-logo" v-if="showFixedLogo"><img :src="currentLogoPath" alt="nerv_logo" width="140" height="140" loading="lazy" decoding="async" fetchpriority="low"></div>
    </div>
    <div class="toast" v-if="toastMsg" :class="{show: toastMsg}">{{ toastMsg }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed, isProxy, nextTick, onMounted, onUnmounted, ref, toRaw, watch } from 'vue';
import { formatExgDate, formatExgDateTime, getExgStatusState, normalizeSearchText, normalizeZh, shouldShowExgStatus, stripBracketSegments, validateMapIndexEntry } from './mapSearchCore';
import { formatTemplate, getConnectAddress, getFastJoinUrl, getServerKey, normalizeJoinStrategy } from './composables/useAppUtilities';

const props = defineProps({
  initialConfig: {
    type: Array,
    default: () => [],
  },
  pageContext: {
    type: Object,
    default: () => ({}),
  },
});

type ServerRecord = Record<string, any>;

type CommunityRecord = {
  id: string;
  name: string;
  short_name?: string;
  features: string[];
  servers?: ServerRecord[];
  game?: string;
  normal_threshold?: number;
  join_strategy?: string;
  logo?: string;
  logo_is_svg?: boolean;
  logo_light?: string;
  logo_light_is_svg?: boolean;
  logo_dark?: string;
  logo_dark_is_svg?: boolean;
  [key: string]: any;
};

type AdvancedSummaryRow = {
  community_id: string;
  community_name: string;
  avg_pcu_30d: number;
  avg_acu_30d: number;
  pcu_peak_30d: number;
  acu_peak_30d: number;
  pcu_trend_pct: number | null;
  acu_trend_pct: number | null;
};

type AdvancedDailyRow = {
  date: string;
  community_id: string;
  community_name: string;
  pcu: number;
  acu: number;
  samples: number;
  expected_samples: number;
};

type AdvancedStatsPayload = {
  monthly_summary: AdvancedSummaryRow[];
  community_daily_rows_7d: AdvancedDailyRow[];
  community_daily_rows_30d: AdvancedDailyRow[];
  weekly_chart: Record<string, any>;
  monthly_chart: Record<string, any>;
  [key: string]: any;
};

const ADVANCED_STATS_ENDPOINTS = [
  '/api/stats/advanced?days=30',
  '/api/stats/advanced/?days=30',
  '/api/stats-advanced?days=30',
];

declare global {
  interface Window {
    Chart?: any;
  }

  interface Navigator {
    userLanguage?: string;
  }
}

const ICONS = {
  map: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M8.5 4.358v12.465l-4.32 3.038a.75.75 0 0 1-1.174-.509l-.007-.104V8.615a.75.75 0 0 1 .238-.548l.08-.065L8.5 4.358Zm12.494.29.007.104v10.633a.75.75 0 0 1-.238.548l-.08.065L15.5 19.64V7.174l4.32-3.035a.75.75 0 0 1 1.174.509ZM10 4.359l4 2.812v12.467l-4-2.814V4.359Z" fill="currentColor"/></svg>`,
  server: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M9 2a3 3 0 0 0-3 3v14a3 3 0 0 0 3 3h6a3 3 0 0 0 3-3V5a3 3 0 0 0-3-3H9Zm-.5 4.75A.75.75 0 0 1 9.25 6h5.5a.75.75 0 0 1 0 1.5h-5.5a.75.75 0 0 1-.75-.75Zm0 11a.75.75 0 0 1 .75-.75h5.5a.75.75 0 0 1 0 1.5h-5.5a.75.75 0 0 1-.75-.75Zm0-3a.75.75 0 0 1 .75-.75h5.5a.75.75 0 0 1 0 1.5h-5.5a.75.75 0 0 1-.75-.75Z" fill="currentColor"/></svg>`,
  stats: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M9 5.23a2.25 2.25 0 0 1 2.25-2.25h1.5A2.25 2.25 0 0 1 15 5.23V21H9V5.23ZM7.5 10H5.25A2.25 2.25 0 0 0 3 12.25v8c0 .415.336.75.75.75H7.5V10ZM16.5 21h3.75a.75.75 0 0 0 .75-.75v-11A2.25 2.25 0 0 0 18.75 7H16.5v14Z" fill="currentColor"/></svg>`,
  feedback: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M5 3a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h4l3.2 3.2a.75.75 0 0 0 1.28-.53V17H19a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2H5Zm2.5 5.75a.75.75 0 0 1 .75-.75h7a.75.75 0 0 1 0 1.5h-7a.75.75 0 0 1-.75-.75Zm.75 3.25a.75.75 0 0 0 0 1.5H13a.75.75 0 0 0 0-1.5H8.25Z" fill="currentColor"/></svg>`,
  lang: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M18 2a1 1 0 1 0-2 0v1h-4a1 1 0 0 0-1 1v1.25a1 1 0 1 0 2 0V5h8v.25a1 1 0 1 0 2 0V4a1 1 0 0 0-1-1h-4V2ZM8.563 7.505l.056.117 5.307 13.005a1 1 0 0 1-1.801.86l-.05-.105L10.692 18H4.407l-1.49 3.407a1 1 0 0 1-1.208.555l-.11-.04a1 1 0 0 1-.555-1.208l.04-.11L6.777 7.6c.337-.77 1.395-.795 1.786-.094Zm-.902 3.062L5.282 16h4.595l-2.216-5.432ZM13.499 7a1 1 0 0 1 1-1h5a1 1 0 0 1 .708 1.707L18.414 9.5H22a1 1 0 1 1 0 2h-4v2.984a2.5 2.5 0 0 1-3.219 2.394l-.569-.17a1 1 0 1 1 .575-1.916l.569.17a.5.5 0 0 0 .643-.478V11.5H12a1 1 0 1 1 0-2h4a1 1 0 0 1 .292-.707L17.085 8H14.5a1 1 0 0 1-1-1Z" fill="currentColor"/></svg>`,
  theme: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10Zm0-2V4a8 8 0 1 1 0 16Z" fill="currentColor"/></svg>`,
  grid: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M4 6a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6Zm10-2a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2V6ZM4 16a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-4Zm10-2a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-4Z" fill="currentColor"/></svg>`,
  list: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M3 6a1 1 0 0 1 1-1h16a1 1 0 1 1 0 2H4a1 1 0 0 1-1-1zm0 6a1 1 0 0 1 1-1h16a1 1 0 1 1 0 2H4a1 1 0 0 1-1-1zm1 5a1 1 0 1 0 0 2h16a1 1 0 1 0 0-2H4z" fill="currentColor"/></svg>`,
  edit: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z" fill="currentColor"/></svg>`,
  sort: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M3 18h6v-2H3v2zM3 6v2h18V6H3zm0 7h12v-2H3v2z" fill="currentColor"/></svg>`,
  drag: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M7 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4zm0-6a2 2 0 1 0 0-4 2 2 0 0 0 0 4zm0-6a2 2 0 1 0 0-4 2 2 0 0 0 0 4zm10 12a2 2 0 1 0 0-4 2 2 0 0 0 0 4zm0-6a2 2 0 1 0 0-4 2 2 0 0 0 0 4zm0-6a2 2 0 1 0 0-4 2 2 0 0 0 0 4z" fill="currentColor"/></svg>`,
  bell: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.63-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.64 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2zm-2 1H8v-6c0-2.48 1.51-4.5 4-4.5s4 2.02 4 4.5v6z" fill="currentColor"/></svg>`,
  trash: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" fill="currentColor"/></svg>`,
  search_sub: `<svg width="24" height="24" fill="none" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M10 2.5a7.5 7.5 0 0 1 5.964 12.048l4.743 4.745a1 1 0 0 1-1.32 1.497l-.094-.083-4.745-4.743A7.5 7.5 0 1 1 10 2.5Zm0 2a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11Z" fill="currentColor"/></svg>`,
  check: `<svg width="18" height="18" viewBox="0 0 16 16" fill="none"><path d="M3.5 8.5l2.5 2.5 6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  cross: `<svg width="18" height="18" viewBox="0 0 16 16" fill="none"><path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>`
};
const icons = ICONS;

const LOGO_PATHS = { B: '/static/nerv_logo_ui.webp', W: '/static/nerv_logo_ui.webp' };
const FAVICON_PATHS = { light: '/static/nerv_logo.png', dark: '/static/nerv_logo.png' };
const STEAM_LOGO_PATH = '/static/steam_logo.svg';
const NOTIFICATION_ICON_PATH = '/static/nerv_logo_ui.webp';
const COMMUNITY_LOGO_OVERRIDES: Record<string, string> = {
  '/static/exg_logo.webp': '/static/exg_logo_ui.webp',
  '/static/nide_logo.png': '/static/nide_logo_ui.webp',
  '/static/zed_logo.png': '/static/zed_logo_ui.webp',
};
const VIEW_ROUTES = { servers: '/', map_sub: '/map-sub', map_cooldown: '/map-cooldown', stats: '/stats', feedback: '/feedback' };
const INITIAL_CONFIG = (Array.isArray(props.initialConfig) ? props.initialConfig : []) as CommunityRecord[];

const communities = ref<CommunityRecord[]>(INITIAL_CONFIG);
const joinConfig = ref({ default_strategy: 'rungameid' });
const servers = ref<Record<string, ServerRecord[]>>({});
const serverCache = ref<Record<string, Record<string, ServerRecord & { _lastSeen: number }>>>({});
const pageContext = props.pageContext || {};
const embedMode = Boolean(pageContext.embedMode ?? document.body.dataset.embedMode === 'true');
const urlParams = new URLSearchParams(window.location.search);
const paramLang = urlParams.get('lang');
const paramClient = urlParams.get('client');
const paramNonce = urlParams.get('nonce');
const paramTheme = urlParams.get('theme');
const paramTab = urlParams.get('tab');
const paramDense = urlParams.get('dense');
const initialView = document.body.dataset.initialView || 'servers';
const allowedTabs = new Set(['servers', 'map_sub', 'map_cooldown', 'stats', 'feedback']);
const resolvedView = allowedTabs.has(paramTab) ? paramTab : initialView;
const curView = ref(resolvedView);
const toastMsg = ref('');
let toastTimer = null;
let steamLoginWindow = null;
let steamLoginTimer = null;
const isCollapsed = ref(document.documentElement.classList.contains('sidebar-is-collapsed'));
const showLangMenu = ref(false);
const showSubPopover = ref(false);
const showProfileMenu = ref(false);
const viewMode = ref('list');
const isDark = ref(window.matchMedia('(prefers-color-scheme: dark)').matches);
const isMobile = ref(window.innerWidth <= 768);
const viewportWidth = ref(window.innerWidth);
const isEditMode = ref(false);
const sidebarWasAutoExpandedForReorder = ref(false);
const sortByPlayers = ref(false);
const serverMapQuery = ref('');
const serverMapQueryInput = ref('');
const authState = ref({ loggedIn: false, role: 'guest' });
const isPrime = ref(false);
const steamAuthPending = ref(false);
const steamProfile = ref({ name: null, avatar: null });
const steamId = ref(null);
const showLoginPrompt = ref(false);
const showFixedLogo = ref(false);
const feedbackSubject = ref('');
const feedbackMessage = ref('');
const mainContentRef = ref(null);
const serversScrollTop = ref(0);

const currentStats = ref([]);
const totalPlayers = ref(0);
const totalPeak48h = ref(0);
const topCommunity = ref(null);
const showAdvancedStats = ref(false);
const advancedStatsLoading = ref(false);
const advancedStatsError = ref('');
const advancedStatsPayload = ref<AdvancedStatsPayload | null>(null);

const subSearchQuery = ref('');
const mapIndex = ref({});
const mapSearchIndex = ref([]);
const searchResults = ref([]);
const selectedMap = ref(null);
const newSubComms = ref(['all']);
const subscriptions = ref([]);
const lastNotifiedMaps = ref({});
const hasNotification = typeof Notification !== 'undefined';
const notificationPermission = ref(hasNotification ? Notification.permission : 'denied');
const draggedIndex = ref(null);
const dragOverIndex = ref(null);

const embedConfig = {
  enabled: embedMode,
  client: paramClient,
  nonce: paramNonce,
  theme: paramTheme,
  lang: paramLang,
  tab: paramTab,
  dense: paramDense
};
const sysLang = navigator.language || (navigator as Navigator).userLanguage;

let defaultLang = 'en';

if (paramLang) {
  defaultLang = paramLang;
} else {
  if (sysLang && sysLang.toLowerCase().startsWith('zh')) {
    if (sysLang.includes('HK')) defaultLang = 'zh-HK';
    else if (sysLang.includes('TW')) defaultLang = 'zh-TW';
    else defaultLang = 'zh-CN';
  } else {
    defaultLang = 'en';
  }
}

const defaultChineseLang = defaultLang.startsWith('zh') ? defaultLang : 'zh-CN';
const curLang = ref(defaultLang);

const EMBED_TARGET_ORIGIN = import.meta.env.VITE_EMBED_TARGET_ORIGIN || 'https://example.com';
const steamProfileUrlPrefix = import.meta.env.VITE_STEAM_PROFILE_URL_PREFIX || 'https://example.com/profiles/';
const isTauriClient = embedMode && paramClient === 'tauri';
const hasEmbedNonce = embedMode && Boolean(paramNonce);
const shouldUsePostMessage = isTauriClient && hasEmbedNonce;
const isEmbedDense = embedMode && ['1', 'true', 'yes'].includes(String(paramDense || '').toLowerCase());

if (embedMode && paramTheme) {
  const themeValue = String(paramTheme).toLowerCase();
  if (themeValue === 'dark') isDark.value = true;
  if (themeValue === 'light') isDark.value = false;
}
if (isEmbedDense) {
  document.documentElement.classList.add('embed-dense');
}

const postEmbedMessage = (type, payload = {}) => {
  if (!shouldUsePostMessage) return false;
  if (!window.parent || window.parent === window) return false;
  window.parent.postMessage({ type, v: 1, nonce: paramNonce, payload }, EMBED_TARGET_ORIGIN);
  return true;
};

const sendEmbedReady = () => {
  postEmbedMessage('CS2ZE_READY', {
    features: ['join', 'copy', 'subscribe_map']
  });
};

const ROLE_LABELS = {
  guest: { label: 'Guest' },
  member: { label: 'Member' },
  prime: { label: 'Prime' },
  admin: { label: 'Admin' }
};

const i18nData = ref({});
const t = (key, fallback = '') => {
  const langPack = i18nData.value[curLang.value] || {};
  const fallbackPack = i18nData.value['en'] || {};
  return langPack[key] || fallbackPack[key] || fallback || key;
};
const isLoggedIn = computed(() => authState.value.loggedIn);
const authRoleLabel = computed(() => ROLE_LABELS[authState.value.role]?.label || ROLE_LABELS.guest.label);
const authRoleClass = computed(() => authState.value.role);
const langLabel = computed(() => (curLang.value || '').startsWith('zh') ? '中文' : 'English');
const isChineseLang = computed(() => curLang.value.includes('zh'));
const currentLogoPath = computed(() => isDark.value ? LOGO_PATHS.W : LOGO_PATHS.B);
const steamLogoPath = computed(() => STEAM_LOGO_PATH);
const steamProfileName = computed(() => steamProfile.value.name || 'Steam User');
const steamProfileAvatar = computed(() => steamProfile.value.avatar || steamLogoPath.value);
const communityById = computed<Record<string, CommunityRecord>>(() => {
  const map: Record<string, CommunityRecord> = {};
  communities.value.forEach((comm) => {
    map[comm.id] = comm;
  });
  return map;
});
const normalizedServerMapQuery = computed(() => normalizeSearchText(serverMapQuery.value));
const resolveOptimizedLogo = (url: string | undefined) => {
  const source = String(url || '');
  if (!source) return '';
  return COMMUNITY_LOGO_OVERRIDES[source] || source;
};
const getCommunityLogoMeta = (comm: CommunityRecord | null | undefined) => {
  if (!comm) return { url: '', isSvg: false };
  if (isDark.value && comm.logo_dark) {
    return { url: resolveOptimizedLogo(comm.logo_dark), isSvg: Boolean(comm.logo_dark_is_svg) };
  }
  if (!isDark.value && comm.logo_light) {
    return { url: resolveOptimizedLogo(comm.logo_light), isSvg: Boolean(comm.logo_light_is_svg) };
  }
  return { url: resolveOptimizedLogo(comm.logo || ''), isSvg: Boolean(comm.logo_is_svg) };
};
let searchDebounceTimer = null;
watch(serverMapQueryInput, (next) => {
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer);
  }
  searchDebounceTimer = setTimeout(() => {
    serverMapQuery.value = next;
  }, 200);
});
const getMainScrollContainer = () => mainContentRef.value || document.getElementById('main-content');
const saveServersScroll = () => {
  const container = getMainScrollContainer();
  if (container) {
    serversScrollTop.value = container.scrollTop;
  } else {
    serversScrollTop.value = window.scrollY || window.pageYOffset || 0;
  }
};
const applyServersScrollPosition = () => {
  const container = getMainScrollContainer();
  if (container) {
    const previousBehavior = container.style.scrollBehavior;
    container.style.scrollBehavior = 'auto';
    container.scrollTop = serversScrollTop.value;
    container.style.scrollBehavior = previousBehavior;
  } else {
    window.scrollTo(0, serversScrollTop.value);
  }
};
const restoreServersScroll = () => {
  applyServersScrollPosition();
  void nextTick(() => {
    applyServersScrollPosition();
  });
};
watch(curView, (nextView, prevView) => {
  if (prevView === 'servers' && nextView !== 'servers') {
    saveServersScroll();
  }
  if (nextView === 'servers' && prevView !== 'servers') {
    restoreServersScroll();
  }
  if (nextView === 'stats' && showAdvancedStats.value) {
    loadAdvancedStats(false);
  }
  if (prevView === 'stats' && nextView !== 'stats') {
    cleanupAdvancedCharts();
  }
  if (nextView === 'map_sub') {
    void ensureMapDataForView('map_sub').catch(() => undefined);
  }
  if (nextView === 'map_cooldown') {
    void ensureMapDataForView('map_cooldown').finally(() => {
      mapCooldownNowEpoch.value = Math.floor(Date.now() / 1000);
      if (mapCooldownNeedsRebuild.value) {
        buildCooldownRows({ rebuildAll: true, reason: 'enter-view' });
        mapCooldownNeedsRebuild.value = false;
      } else {
        buildCooldownRows({ rebuildAll: false, reason: 'enter-view' });
      }
      resetMapCooldownScrollState();
      resetMapCooldownFeedState();
      startMapCooldownTimer();
      nextTick(() => {
        if (mapCooldownScrollRef.value) {
          mapCooldownScrollRef.value.scrollTop = 0;
          mapCooldownLatestScrollTop = mapCooldownScrollRef.value.scrollTop || 0;
        }
        setupMapCooldownContainerObserver();
        scheduleMapCooldownPrefixRebuild();
        clampMapCooldownScrollTop({ force: true });
      });
    });
  }
  if (prevView === 'map_cooldown' && nextView !== 'map_cooldown') {
    stopMapCooldownTimer();
    resetMapCooldownScrollState();
    teardownMapCooldownContainerObserver();
  }
});
watch([isLoggedIn, curView], () => {
  scheduleServerRefresh();
  if (isLoggedIn.value && curView.value === 'stats') {
    scheduleStatsRefresh();
  } else if (statsRefreshTimer) {
    clearInterval(statsRefreshTimer);
    statsRefreshTimer = null;
  }
});

const updateFavicon = () => {
  const icon = document.getElementById('favicon') as HTMLLinkElement | null;
  if (!icon) return;
  icon.href = isDark.value ? FAVICON_PATHS.dark : FAVICON_PATHS.light;
};

watch(curLang, () => {
  document.title = t('app_title');
}, { immediate: true });
const handleResize = () => {
  viewportWidth.value = window.innerWidth;
  isMobile.value = window.innerWidth <= 768;
  if (curView.value === 'map_cooldown') {
    mapCooldownLatestScrollTop = mapCooldownScrollRef.value?.scrollTop || mapCooldownLatestScrollTop;
    nextTick(() => {
      scheduleMapCooldownPrefixRebuild();
      clampMapCooldownScrollTop({ force: true });
    });
  }
};

const handleGlobalClick = (e) => {
  if (!showLangMenu.value && !showSubPopover.value && !showProfileMenu.value) return;
  const target = e.target;
  if (!(target instanceof Element)) return;
  const inLang = target.closest('.dropdown-menu') || target.closest('.control-btn') || target.closest('.profile-btn');
  if (!inLang) {
    showLangMenu.value = false;
    showSubPopover.value = false;
    showProfileMenu.value = false;
  }
};
const handleVisibilityChange = () => {
  if (document.hidden) {
    scheduleServerRefresh();
  } else {
    scheduleServerRefresh(true);
  }
  if (isLoggedIn.value && curView.value === 'stats') {
    scheduleStatsRefresh();
  }
};

const clearToastTimer = () => {
  if (toastTimer) {
    clearTimeout(toastTimer);
    toastTimer = null;
  }
};

const showToast = (message, duration = 3000) => {
  toastMsg.value = message;
  clearToastTimer();
  if (message) {
    toastTimer = setTimeout(() => {
      toastMsg.value = '';
      toastTimer = null;
    }, duration);
  }
};

const stopSteamLoginWatcher = () => {
  if (steamLoginTimer) {
    clearInterval(steamLoginTimer);
    steamLoginTimer = null;
  }
  steamLoginWindow = null;
};

const fetchSteamStatus = async (silent = false) => {
  try {
    const res = await fetch('/auth/me', { credentials: 'same-origin' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const isLoggedInBool = Boolean(data && data.logged_in);
    authState.value = {
      loggedIn: isLoggedInBool,
      role: isLoggedInBool ? (data.role || 'member') : 'guest'
    };
    isPrime.value = Boolean(isLoggedInBool && data.prime);

    if (isLoggedInBool) {
      steamProfile.value = data.profile || { name: null, avatar: null };
      steamId.value = data.steam_id;
    } else {
      steamProfile.value = { name: null, avatar: null };
      steamId.value = null;
      isPrime.value = false;
    }

    return data;
  } catch (e) {
    if (!silent) {
      showToast(t('login_required_title'));
    }
    authState.value = { loggedIn: false, role: 'guest' };
    steamProfile.value = { name: null, avatar: null };
    isPrime.value = false;
    return null;
  }
};

const handleSteamMessage = async (event) => {
  const isTrustedOrigin = () => {
    if (event.origin === window.location.origin) return true;
    try {
      return new URL(event.origin).host === window.location.host;
    } catch (e) {
      return false;
    }
  };
  if (!isTrustedOrigin()) return;
  const payload = event.data || {};
  if (payload.type !== 'steam-auth') return;
  stopSteamLoginWatcher();
  steamAuthPending.value = false;
  const status = await fetchSteamStatus(true);
  if (payload.status === 'ok' && status && status.logged_in) {
    showToast(t('login_as'));
    showLoginPrompt.value = false;
    localStorage.setItem('steam_prompt_dismissed', 'true');
  } else {
    showToast(t('steam_prompt_desc'));
  }
};

onMounted(async () => {
  window.addEventListener('resize', handleResize);
  window.addEventListener('click', handleGlobalClick);
  window.addEventListener('message', handleSteamMessage);
  document.addEventListener('visibilitychange', handleVisibilityChange);

  document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
  updateFavicon()

  try {
    const savedCollapse = localStorage.getItem('sidebar_collapsed');
    if (savedCollapse !== null) isCollapsed.value = savedCollapse === 'true';
    else isCollapsed.value = false;
  } catch (e) {
    isCollapsed.value = false;
  }

  try {
    const savedView = localStorage.getItem('view_mode');
    if (savedView) viewMode.value = savedView;
  } catch (e) {}

  await fetchSteamStatus(true);
  if (communities.value.length) {
    applyCommunities(communities.value);
  }

  try {
    const subs = localStorage.getItem('map_subs');
    if (subs) subscriptions.value = JSON.parse(subs);
    if (!Array.isArray(subscriptions.value)) subscriptions.value = [];
  } catch (e) {
    localStorage.removeItem('map_subs');
    subscriptions.value = [];
  }

  await loadLanguage();
  await fetchConfig();
  if (initialView === 'map_sub' || initialView === 'map_cooldown') {
    scheduleMapIndexWarmup();
  } else {
    window.setTimeout(() => {
      scheduleMapIndexWarmup();
    }, 6000);
  }
  if ((initialView === 'map_sub' || initialView === 'stats' || initialView === 'feedback') && !isLoggedIn.value) {
    curView.value = 'servers';
    showToast(t('login_required_title'));
  }
  if (!isMobile.value && !embedMode) {
    const dismissed = localStorage.getItem('steam_prompt_dismissed');
    if (!isLoggedIn.value && dismissed !== 'true') {
      showLoginPrompt.value = true;
    }
  }
  if (initialView === 'stats' && isLoggedIn.value) {
    await loadStats();
  }
  if (initialView === 'map_cooldown' || (initialView === 'map_sub' && isLoggedIn.value)) {
    await ensureMapDataForView(initialView);
  }
  if (embedMode) {
    sendEmbedReady();
  }
  const revealFixedLogo = () => {
    showFixedLogo.value = true;
  };
  const win = window as unknown as { requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => void };
  if (typeof win.requestIdleCallback === 'function') {
    win.requestIdleCallback(revealFixedLogo, { timeout: 1500 });
  } else {
    window.setTimeout(revealFixedLogo, 500);
  }
});

watch(curLang, () => {
  if (subSearchQuery.value) {
    searchMaps();
  }
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  window.removeEventListener('click', handleGlobalClick);
  window.removeEventListener('message', handleSteamMessage);
  document.removeEventListener('visibilitychange', handleVisibilityChange);
  stopSteamLoginWatcher();
  clearToastTimer();
  stopMapCooldownTimer();
  resetMapCooldownScrollState();
  cleanupAdvancedCharts();
  teardownMapCooldownContainerObserver();
  if (mapCooldownSearchTimer) {
    clearTimeout(mapCooldownSearchTimer);
    mapCooldownSearchTimer = null;
  }
  if (mapCooldownHighlightTimer) {
    clearTimeout(mapCooldownHighlightTimer);
    mapCooldownHighlightTimer = null;
  }
  if (statsRefreshTimer) {
    clearInterval(statsRefreshTimer);
    statsRefreshTimer = null;
  }
  if (serverRefreshTimer) {
    clearInterval(serverRefreshTimer);
    serverRefreshTimer = null;
  }
  if (languageRefreshTimer) {
    clearInterval(languageRefreshTimer);
    languageRefreshTimer = null;
  }
});

const toggleLangMenu = () => {
  showSubPopover.value = false;
  showLangMenu.value = !showLangMenu.value;
};
const toggleSubPopover = () => {
  showLangMenu.value = false;
  showSubPopover.value = !showSubPopover.value;
};
const toggleProfileMenu = () => {
  showLangMenu.value = false;
  showSubPopover.value = false;
  showProfileMenu.value = !showProfileMenu.value;
};

const toggleSidebar = () => {
  isCollapsed.value = !isCollapsed.value;
  if (isCollapsed.value) {
    document.documentElement.classList.add('sidebar-is-collapsed');
  } else {
    document.documentElement.classList.remove('sidebar-is-collapsed');
  }
  localStorage.setItem('sidebar_collapsed', String(isCollapsed.value));
};
const toggleTheme = () => {
  isDark.value = !isDark.value;
  document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light');
  updateFavicon();
  if (showAdvancedStats.value && advancedStatsPayload.value) {
    nextTick(() => renderAdvancedCharts());
  }
};
const setLang = (l) => {
  curLang.value = l;
  showLangMenu.value = false;

  const url = new URL(window.location.href);
  if (l === 'zh-CN') {
    url.searchParams.delete('lang');
  } else {
    url.searchParams.set('lang', l);
  }
  window.history.pushState({}, '', url);
};

const closeDropdowns = () => {
  showLangMenu.value = false;
  showSubPopover.value = false;
  showProfileMenu.value = false;
};

const toggleViewMode = () => {
  viewMode.value = viewMode.value === 'grid' ? 'list' : 'grid';
  localStorage.setItem('view_mode', viewMode.value);
};
const toggleEditMode = () => {
  const nextState = !isEditMode.value;
  if (nextState && isCollapsed.value) {
    sidebarWasAutoExpandedForReorder.value = true;
    isCollapsed.value = false;
    document.documentElement.classList.remove('sidebar-is-collapsed');
    localStorage.setItem('sidebar_collapsed', String(isCollapsed.value));
  }
  if (!nextState) {
    if (sidebarWasAutoExpandedForReorder.value) {
      isCollapsed.value = true;
      document.documentElement.classList.add('sidebar-is-collapsed');
      localStorage.setItem('sidebar_collapsed', String(isCollapsed.value));
    }
    sidebarWasAutoExpandedForReorder.value = false;
  }
  isEditMode.value = nextState;
};
const toggleSortByPlayers = () => sortByPlayers.value = !sortByPlayers.value;

const startSteamLogin = () => {
  if (steamAuthPending.value) return;
  steamAuthPending.value = true;
  stopSteamLoginWatcher();
  steamLoginWindow = window.open('/api/steam/login', 'steamAuth', 'width=920,height=720');
  if (steamLoginWindow) {
    steamLoginTimer = setInterval(async () => {
      if (!steamLoginWindow || steamLoginWindow.closed) {
        stopSteamLoginWatcher();
        steamAuthPending.value = false;
        const status = await fetchSteamStatus(true);
        if (status && status.logged_in) {
          showToast(t('login_as'));
          showLoginPrompt.value = false;
          localStorage.setItem('steam_prompt_dismissed', 'true');
        } else {
          showToast(t('steam_prompt_desc'));
        }
      }
    }, 600);
  } else {
    steamAuthPending.value = false;
    showToast(t('steam_prompt_desc'));
  }
  showLoginPrompt.value = false;
  localStorage.setItem('steam_prompt_dismissed', 'true');
};

const logout = async () => {
  steamAuthPending.value = false;
  showProfileMenu.value = false;
  try {
    await fetch('/api/steam/logout', { method: 'POST', credentials: 'same-origin' });
  } catch (e) {}
  await fetchSteamStatus(true);
  showToast(t('guest_mode'));
};

const dismissLoginPrompt = () => {
  showLoginPrompt.value = false;
  localStorage.setItem('steam_prompt_dismissed', 'true');
};

const hasFeature = (feat) => communities.value.some(c => c.features.includes(feat));
const goToView = (view) => {
  if ((view === 'map_sub' || view === 'stats' || view === 'feedback') && !isLoggedIn.value) {
    showToast(t('login_required_title'));
    return;
  }
  const target = VIEW_ROUTES[view] || '/';
  if (window.location.pathname !== target) {
    const url = new URL(window.location.href);
    url.pathname = target;
    window.history.pushState({}, '', url);
  }
  curView.value = view;
};

const goToSubPage = () => {
  goToView('map_sub');
  showSubPopover.value = false;
};

const scrollToComm = (id) => {
  const isMob = window.innerWidth <= 768;
  let el = document.getElementById(isMob ? 'comm-mob-' + id : 'comm-' + id);
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
};

const requestPerm = () => {
  if (!hasNotification) return;
  Notification.requestPermission().then(p => notificationPermission.value = p);
};

const saveCommunityOrder = () => {
  const ids = communities.value.map(c => c.id);
  localStorage.setItem('comm_order', JSON.stringify(ids));
};
const onDragStart = (e, index) => {
  draggedIndex.value = index;
  e.dataTransfer.effectAllowed = 'move';
  e.dataTransfer.dropEffect = 'move';
};
const onDragEnter = (e, index) => {
  if (index !== draggedIndex.value) dragOverIndex.value = index;
};
const onDragLeave = (_e: DragEvent) => {};
const onDrop = (e, index) => {
  if (draggedIndex.value !== null && draggedIndex.value !== index) {
    const item = communities.value[draggedIndex.value];
    communities.value.splice(draggedIndex.value, 1);
    communities.value.splice(index, 0, item);
    saveCommunityOrder();
  }
  draggedIndex.value = null;
  dragOverIndex.value = null;
};

const loadLanguage = async (silent = false) => {
  if (languageRefreshInFlight) return;
  languageRefreshInFlight = true;
  try {
    const headers = {};
    if (languageRefreshEtag) {
      headers['If-None-Match'] = languageRefreshEtag;
    }
    const res = await fetch('/language.json', { headers });
    if (res.status === 304) {
      return;
    }
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const etag = res.headers.get('ETag') || res.headers.get('etag');
    if (etag) languageRefreshEtag = etag;
    const data = await res.json();
    if (data && typeof data === 'object') {
      i18nData.value = data;
      document.title = t('app_title');
    }
  } catch (e) {
    if (!silent) {
      showToast(t('language_load_failed'));
    }
  } finally {
    languageRefreshInFlight = false;
  }
};

type MapSearchRuntimeModule = typeof import('./mapSearchIndexRuntime.js');
const ensureMapSearchRuntime = async (): Promise<MapSearchRuntimeModule> => {
  if (mapSearchRuntimeModule) return mapSearchRuntimeModule;
  if (mapSearchRuntimePromise) return mapSearchRuntimePromise;
  mapSearchRuntimePromise = import('./mapSearchIndexRuntime.js')
    .then((mod) => {
      mapSearchRuntimeModule = mod;
      return mod;
    })
    .finally(() => {
      mapSearchRuntimePromise = null;
    });
  return mapSearchRuntimePromise;
};

const rebuildMapSearchIndex = async () => {
  const runtime = await ensureMapSearchRuntime();
  mapSearchIndex.value = runtime.buildMapSearchIndex(mapIndex.value);
  mapSearchIndexBuilt = true;
};

const loadMapIndex = async () => {
  if (mapIndexLoadPromise) {
    await mapIndexLoadPromise;
    return;
  }
  mapIndexLoadPromise = (async () => {
    try {
      const res = await fetch('/map_index.json');
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const data = await res.json();
      mapIndex.value = data && typeof data === 'object' ? data : {};
      Object.entries(mapIndex.value).forEach(([key, entry]) => {
        validateMapIndexEntry(key, entry);
      });
      mapSearchIndexBuilt = false;
    } catch (e) {
      mapIndex.value = {};
      mapSearchIndex.value = [];
      mapSearchIndexBuilt = false;
      throw e;
    } finally {
      mapIndexLoadPromise = null;
    }
  })();
  await mapIndexLoadPromise;
};

const ensureMapDataForView = async (view: string) => {
  if (view !== 'map_sub' && view !== 'map_cooldown') return;
  await loadMapIndex().catch(() => undefined);
  if (view === 'map_sub') {
    await ensureMapSearchRuntime();
    if (!mapSearchIndexBuilt) {
      await rebuildMapSearchIndex();
    }
    return;
  }
  if (view === 'map_cooldown') {
    mapCooldownNeedsRebuild.value = true;
  }
};

const scheduleMapIndexWarmup = () => {
  const task = () => {
    void loadMapIndex().catch(() => undefined);
  };
  const win = window as unknown as { requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => void };
  if (typeof win.requestIdleCallback === 'function') {
    win.requestIdleCallback(task, { timeout: 2000 });
    return;
  }
  window.setTimeout(task, 500);
};

const normalizeMapKey = (value) => {
  if (!value) return '';
  let mapKey = value.toString().trim().toLowerCase();
  mapKey = mapKey.replace(/\\/g, '/').split('?', 1)[0];
  if (mapKey.endsWith('.bsp')) mapKey = mapKey.slice(0, -4);
  if (mapKey.startsWith('workshop/')) {
    const parts = mapKey.split('/');
    mapKey = parts[parts.length - 1] || mapKey;
  } else {
    mapKey = mapKey.split('/').pop();
  }
  return mapKey;
};

const mapNoTranslationText = '暂无';

const buildMapTranslationEntry = (mapCn, mapTw) => {
  return {
    zh_cn: mapCn || '',
    zh_tw: mapTw || mapCn || ''
  };
};

const getMapTranslationEntry = (mapName, serverEntry = null) => {
  if (!mapName) return buildMapTranslationEntry('', '');
  if (serverEntry && (serverEntry.map_cn || serverEntry.map_tw)) {
    return buildMapTranslationEntry(serverEntry.map_cn, serverEntry.map_tw);
  }
  const entry = getMapIndexEntry(mapName);
  if (entry && entry.map_cn) {
    return buildMapTranslationEntry(entry.map_cn, entry.map_tw || '');
  }
  return buildMapTranslationEntry('', '');
};

const getMapTranslation = (mapName) => {
  const entry = getMapTranslationEntry(mapName);
  if (curLang.value === 'zh-TW') {
    const translated = stripBracketSegments(entry.zh_tw || '');
    return translated || mapNoTranslationText;
  }
  if (curLang.value === 'zh-CN') {
    const translated = stripBracketSegments(entry.zh_cn || '');
    return translated || mapNoTranslationText;
  }
  return '';
};

const getServerMapTranslation = (serverEntry) => {
  if (!serverEntry) return mapNoTranslationText;
  const entry = getMapTranslationEntry(serverEntry.map, serverEntry);
  if (curLang.value === 'zh-TW') {
    const translated = stripBracketSegments(entry.zh_tw || '');
    return translated || mapNoTranslationText;
  }
  if (curLang.value === 'zh-CN') {
    const translated = stripBracketSegments(entry.zh_cn || '');
    return translated || mapNoTranslationText;
  }
  return '';
};

const getMapIndexEntry = (mapName) => {
  if (!mapName) return null;
  if (mapIndex.value[mapName]) return mapIndex.value[mapName];
  const normalizedKey = normalizeMapKey(mapName);
  if (normalizedKey && mapIndex.value[normalizedKey]) return mapIndex.value[normalizedKey];
  return null;
};

const getMapIndexDisplayName = (mapName) => {
  const entry = getMapIndexEntry(mapName);
  if (!entry || !entry.map_cn) return '';
  const cleaned = stripBracketSegments(entry.map_cn);
  if (curLang.value === 'zh-TW') {
    const mapTw = stripBracketSegments(entry.map_tw || '');
    return mapTw || cleaned;
  }
  if (curLang.value === 'zh-CN') return cleaned;
  return '';
};

const formatExgCompactTime = (datetimeString) => {
  if (!datetimeString) return '';
  const normalized = datetimeString.replace(' - ', ' ').trim();
  const [datePart, timePart = ''] = normalized.split(' ');
  const dateSegments = datePart.split('/');
  if (dateSegments.length < 3) return datetimeString;
  const month = dateSegments[1];
  const day = dateSegments[2];
  const time = timePart.slice(0, 5);
  if (!month || !day || !time) return datetimeString;
  return `${month}/${day} ${time}`;
};

const getExgCooldownProgress = (deadline, durationSec) => {
  if (!deadline || typeof durationSec !== 'number' || durationSec <= 0) return null;
  const nowEpoch = Math.floor(Date.now() / 1000);
  const remaining = Math.max(0, deadline - nowEpoch);
  const progress = 1 - Math.min(1, remaining / durationSec);
  return Math.max(0, Math.min(1, progress));
};

const mapCooldownScrollRef = ref(null);
const coolingOnly = ref(true);
const isAllMapsMode = computed(() => !coolingOnly.value);
const mapCooldownRowsCooling = ref([]);
const mapCooldownRowsAll = ref([]);
const mapCooldownQueryInput = ref('');
const mapCooldownSearchInputRef = ref(null);
const mapCooldownSearchQuery = ref('');
const mapCooldownHighlightKey = ref('');
const mapCooldownNowEpoch = ref(Math.floor(Date.now() / 1000));
const mapCooldownNeedsRebuild = ref(true);
const mapCooldownIsFastScrolling = ref(false);
const mapcdSortMode = ref<'default' | 'availability'>('default');
const mapCooldownPendingRebuild = ref(false);
const mapCooldownIsBuilding = ref(false);
const mapCooldownBuildProgress = ref({ done: 0, total: 0 });
const mapCooldownEstimatedRowHeight = 68;
const mapCooldownMaxRendered = 160;
const mapCooldownFastSpeedThresholdHigh = 2.5;
const mapCooldownFastSpeedThresholdLow = 1.2;
const mapCooldownScrollIdleMs = 180;
const mapCooldownDebug = false;
const mapCooldownWinStart = ref(0);
const mapCooldownWinEnd = ref(0);
const mapCooldownTopSpacerPx = ref(0);
const mapCooldownBottomSpacerPx = ref(0);
const mapCooldownVisibleRows = ref([]);
const mapCooldownTotalHeight = ref(0);
const mapCooldownFreshKeys = ref(new Set());
let mapCooldownTimer = null;
let mapCooldownScrollRafId = 0;
let mapCooldownScrollPending = false;
let mapCooldownLatestScrollTop = 0;
let mapCooldownLastScrollTop = 0;
let mapCooldownLastTimestamp = 0;
let mapCooldownLastChangeTs = 0;
let mapCooldownLastSpeed = 0;
let mapCooldownIsApplyingScrollAdjust = false;
let mapCooldownFreshTimer = null;
let mapCooldownIdleTimer = null;
let mapCooldownPrefixRafId = 0;
let mapCooldownPrefixSums = [0];
let mapCooldownWorker = null;
let mapCooldownWorkerHasIndex = false
let mapCooldownPlainIndexCache: any = null
let mapCooldownLastSentIndexRef: any = null
let mapCooldownBuildId = 0;
let mapCooldownPendingModes = new Set();
let mapCooldownSearchTimer = null;
let mapCooldownHighlightTimer = null;
let mapCooldownContainerResizeObserver = null;
let mapCooldownLastNonZeroViewportHeight = mapCooldownEstimatedRowHeight;
let mapIndexLoadPromise: Promise<void> | null = null;
let mapSearchRuntimeModule: MapSearchRuntimeModule | null = null;
let mapSearchRuntimePromise: Promise<MapSearchRuntimeModule> | null = null;
let mapSearchIndexBuilt = false;
let mapSearchRequestId = 0;

const mapCooldownLocale = computed(() => {
  const lang = curLang.value || 'en-US';
  return lang === 'en' ? 'en-US' : lang;
});
const mapCooldownTimeZone = ref(Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC');
const mapCooldownProgressText = computed(() => {
  const { done, total } = mapCooldownBuildProgress.value || {};
  if (!total) return '';
  const pct = Math.min(100, Math.round((done / total) * 100));
  return ` ${pct}%`;
});

const mapcdQueryTrimmed = computed(() => mapCooldownQueryInput.value.trim());
const mapCooldownSearchQueryTrimmed = computed(() => mapCooldownSearchQuery.value.trim());
const mapCooldownSearchQueryNorm = computed(() => normalizeZh(mapCooldownSearchQuery.value));
const mapCooldownBaseRows = computed(() => (coolingOnly.value ? mapCooldownRowsCooling.value : mapCooldownRowsAll.value));
const mapCooldownFilteredRows = computed(() => {
  const baseRows = mapCooldownBaseRows.value;
  const queryNorm = mapCooldownSearchQueryNorm.value;
  if (!queryNorm) return baseRows;
  return baseRows.filter((row) => (row.searchTextNorm || '').includes(queryNorm));
});
const mapcdAllMatches = computed(() => {
  const baseRows = mapCooldownRowsAll.value;
  const queryNorm = mapCooldownSearchQueryNorm.value;
  if (!queryNorm) return baseRows;
  return baseRows.filter((row) => (row.searchTextNorm || '').includes(queryNorm));
});
const mapcdAutoShowAll = computed(() =>
  coolingOnly.value &&
  mapcdQueryTrimmed.value.length > 0 &&
  mapCooldownFilteredRows.value.length === 0 &&
  mapcdAllMatches.value.length > 0
);
const mapcdDisplayedRows = computed(() => {
  const baseRows = mapcdAutoShowAll.value ? mapcdAllMatches.value : mapCooldownFilteredRows.value;
  const nameValue = (row) => (row.mapLine1 || '').toLowerCase();
  const compareName = (a, b) => nameValue(a).localeCompare(nameValue(b));
  if (mapcdSortMode.value === 'availability') {
    return baseRows.slice().sort((a, b) => {
      const aCooldownEpoch = a.deadlineEpochSec;
      const bCooldownEpoch = b.deadlineEpochSec;
      const aCooling = a.availability === 'cooling' || (typeof aCooldownEpoch === 'number' && aCooldownEpoch > 0);
      const bCooling = b.availability === 'cooling' || (typeof bCooldownEpoch === 'number' && bCooldownEpoch > 0);
      if (aCooling !== bCooling) return aCooling ? 1 : -1;
      if (!aCooling) return compareName(a, b);
      if (aCooldownEpoch == null && bCooldownEpoch == null) return compareName(a, b);
      if (aCooldownEpoch == null) return 1;
      if (bCooldownEpoch == null) return -1;
      const diff = aCooldownEpoch - bCooldownEpoch;
      if (diff !== 0) return diff;
      return compareName(a, b);
    });
  }
  return baseRows.slice().sort(compareName);
});
const onMapcdCooldownEndHeaderClick = () => {
  mapcdSortMode.value = mapcdSortMode.value === 'default' ? 'availability' : 'default';
};
const mapCooldownRows = computed(() => mapcdDisplayedRows.value);
const mapCooldownKeysAll = computed(() => mapCooldownRows.value.map((row) => row.key));
const updateMapCooldownVisibleRows = () => {
  const total = mapCooldownRows.value.length;
  const rowHeight = getMapCooldownRowHeight();
  const totalHeight = total * rowHeight;
  mapCooldownTotalHeight.value = totalHeight;
  if (total === 0) {
    mapCooldownWinStart.value = 0;
    mapCooldownWinEnd.value = 0;
    mapCooldownVisibleRows.value = [];
    mapCooldownTopSpacerPx.value = 0;
    mapCooldownBottomSpacerPx.value = 0;
    return;
  }
  let start = Math.max(0, Math.min(mapCooldownWinStart.value, total - 1));
  let end = Math.max(start + 1, Math.min(mapCooldownWinEnd.value, total));
  if (end <= start) {
    start = Math.min(Math.max(start, 0), total - 1);
    end = Math.min(start + 1, total);
  }
  mapCooldownWinStart.value = start;
  mapCooldownWinEnd.value = end;
  const nextVisibleRows = mapCooldownRows.value.slice(start, end);
  if (mapCooldownDebug && total > 0 && nextVisibleRows.length === 0) {
    console.log('[mapcd] visible rows empty with non-zero total', { total, start, end });
  }
  mapCooldownVisibleRows.value = nextVisibleRows;
  mapCooldownTopSpacerPx.value = start * rowHeight;
  mapCooldownBottomSpacerPx.value = Math.max(0, totalHeight - end * rowHeight);
};

const clearMapCooldownSearch = () => {
  mapCooldownQueryInput.value = '';
  mapCooldownSearchQuery.value = '';
  mapCooldownHighlightKey.value = '';
};

const focusMapCooldownSearchInput = () => {
  nextTick(() => {
    if (mapCooldownSearchInputRef.value) {
      mapCooldownSearchInputRef.value.focus();
    }
  });
};

const clearMapCooldownSearchAndFocus = () => {
  clearMapCooldownSearch();
  focusMapCooldownSearchInput();
};

const setMapCooldownHighlight = (key) => {
  mapCooldownHighlightKey.value = key;
  if (mapCooldownHighlightTimer) {
    clearTimeout(mapCooldownHighlightTimer);
  }
  mapCooldownHighlightTimer = setTimeout(() => {
    mapCooldownHighlightKey.value = '';
    mapCooldownHighlightTimer = null;
  }, 320);
};

const jumpToMapCooldownRow = (row) => {
  if (!row) return;
  const idx = mapcdDisplayedRows.value.findIndex((item) => item.key === row.key);
  if (idx < 0) return;
  const scrollEl = mapCooldownScrollRef.value;
  if (scrollEl) {
    const scrollTop = idx * mapCooldownEstimatedRowHeight;
    scrollEl.scrollTo({ top: scrollTop, behavior: 'auto' });
    mapCooldownLatestScrollTop = scrollTop;
    scheduleMapCooldownRaf();
  }
  setMapCooldownHighlight(row.key);
};

const jumpToBestMapCooldownMatch = () => {
  if (!mapCooldownSearchQueryTrimmed.value) return;
  const rows = mapcdDisplayedRows.value;
  if (!rows.length) return;
  jumpToMapCooldownRow(rows[0]);
};

const onMapCooldownSearchKeydown = (event) => {
  const { key } = event;
  if (key === 'Escape') {
    clearMapCooldownSearch();
    return;
  }
  if (key === 'Enter') {
    event.preventDefault();
    jumpToBestMapCooldownMatch();
  }
};

const getMapCooldownRowHeight = () => mapCooldownEstimatedRowHeight;

const rebuildMapCooldownPrefixSums = () => {
  const total = mapCooldownRows.value.length;
  const rowHeight = getMapCooldownRowHeight();
  const nextPrefix = new Array(total + 1);
  nextPrefix[0] = 0;
  for (let i = 0; i < total; i += 1) {
    nextPrefix[i + 1] = nextPrefix[i] + rowHeight;
  }
  mapCooldownPrefixSums = nextPrefix;
  mapCooldownTotalHeight.value = total * rowHeight;
};

const captureMapCooldownAnchor = () => {
  const scrollEl = mapCooldownScrollRef.value;
  if (!scrollEl) return null;
  const keys = mapCooldownKeysAll.value;
  if (!keys.length) return null;
  const startIndex = Math.min(Math.max(0, mapCooldownWinStart.value), keys.length - 1);
  const anchorKey = keys[startIndex];
  if (!anchorKey) return null;
  const anchorTop = startIndex * getMapCooldownRowHeight();
  return {
    key: anchorKey,
    startIndex,
    offset: scrollEl.scrollTop - anchorTop
  };
};

const applyMapCooldownAnchor = (anchor) => {
  if (!anchor) return;
  const scrollEl = mapCooldownScrollRef.value;
  if (!scrollEl) return;
  const keys = mapCooldownKeysAll.value;
  let anchorIndex = anchor.startIndex;
  if (keys[anchorIndex] !== anchor.key) {
    anchorIndex = keys.indexOf(anchor.key);
  }
  if (anchorIndex < 0) return;
  const anchorTop = anchorIndex * getMapCooldownRowHeight();
  const desired = anchorTop + anchor.offset;
  const maxScrollTop = Math.max(0, mapCooldownTotalHeight.value - scrollEl.clientHeight);
  mapCooldownIsApplyingScrollAdjust = true;
  scrollEl.scrollTop = Math.min(Math.max(0, desired), maxScrollTop);
  mapCooldownLatestScrollTop = scrollEl.scrollTop;
  mapCooldownIsApplyingScrollAdjust = false;
};

const scheduleMapCooldownPrefixRebuild = () => {
  if (mapCooldownPrefixRafId) return;
  const anchor = captureMapCooldownAnchor();
  mapCooldownPrefixRafId = window.requestAnimationFrame(() => {
    mapCooldownPrefixRafId = 0;
    rebuildMapCooldownPrefixSums();
    const scrollEl = mapCooldownScrollRef.value;
    if (scrollEl) {
      const maxScrollTop = Math.max(0, mapCooldownTotalHeight.value - scrollEl.clientHeight);
      if (scrollEl.scrollTop > maxScrollTop) {
        mapCooldownIsApplyingScrollAdjust = true;
        scrollEl.scrollTop = maxScrollTop;
        mapCooldownIsApplyingScrollAdjust = false;
      }
      mapCooldownLatestScrollTop = scrollEl.scrollTop;
    }
    applyMapCooldownAnchor(anchor);
    const scrollTop = mapCooldownScrollRef.value?.scrollTop ?? mapCooldownLatestScrollTop;
    updateMapCooldownWindow(scrollTop, { force: true });
  });
};

const getMapCooldownViewportHeight = (scrollEl) => {
  const rawHeight = scrollEl?.clientHeight ?? 0;
  if (rawHeight > 0) {
    mapCooldownLastNonZeroViewportHeight = rawHeight;
    return rawHeight;
  }
  if (mapCooldownDebug && mapCooldownLastNonZeroViewportHeight > 0) {
    console.log('[mapcd] viewport height is 0, reusing last value');
  }
  return Math.max(1, mapCooldownLastNonZeroViewportHeight || 1);
};

const clampMapCooldownScrollTop = ({ force = false } = {}) => {
  const scrollEl = mapCooldownScrollRef.value;
  const totalRows = mapCooldownRows.value.length;
  const rowHeight = getMapCooldownRowHeight();
  const viewportHeight = getMapCooldownViewportHeight(scrollEl);
  const totalHeight = totalRows * rowHeight;
  const maxScrollTop = Math.max(0, totalHeight - viewportHeight);
  if (scrollEl && scrollEl.scrollTop > maxScrollTop) {
    if (mapCooldownDebug) {
      console.log('[mapcd] scrollTop clamped', { from: scrollEl.scrollTop, to: maxScrollTop });
    }
    mapCooldownIsApplyingScrollAdjust = true;
    scrollEl.scrollTop = maxScrollTop;
    mapCooldownIsApplyingScrollAdjust = false;
  }
  const scrollTop = scrollEl ? scrollEl.scrollTop : mapCooldownLatestScrollTop;
  mapCooldownLatestScrollTop = scrollTop;
  updateMapCooldownWindow(scrollTop, { force });
};

const updateMapCooldownWindow = (scrollTop, { force = false } = {}) => {
  const total = mapCooldownRows.value.length;
  const rowHeight = getMapCooldownRowHeight() || 1;
  const scrollEl = mapCooldownScrollRef.value;
  const viewportHeight = getMapCooldownViewportHeight(scrollEl);
  const totalHeight = total * rowHeight;
  mapCooldownTotalHeight.value = totalHeight;
  const maxScrollTop = Math.max(0, totalHeight - viewportHeight);
  const scrollTopClamped = Math.min(Math.max(scrollTop, 0), maxScrollTop);
  if (mapCooldownDebug && scrollTop !== scrollTopClamped) {
    console.log('[mapcd] scrollTop clamped in window', { from: scrollTop, to: scrollTopClamped });
  }
  if (total === 0) {
    mapCooldownWinStart.value = 0;
    mapCooldownWinEnd.value = 0;
    updateMapCooldownVisibleRows();
    return;
  }
  // 璁＄畻鍩烘湰琛屾暟
  const baseRows = Math.max(1, Math.ceil(viewportHeight / rowHeight))

  // 鏄惁澶勪簬蹇€熸粴鍔ㄧ姸鎬?
  const isFast = mapCooldownIsFastScrolling.value

  // 涓嶅悓婊氬姩鐘舵€佷笅鐨?overscan 鍜屾渶澶ф覆鏌撴暟閲?
  const overscanRows = isFast
    ? Math.min(24, Math.max(8, Math.ceil(baseRows * 0.5)))
    : Math.min(120, Math.max(10, Math.ceil(baseRows * 1.2)))

  const maxRendered = isFast ? 80 : mapCooldownMaxRendered

  // 鏈€缁堟覆鏌撶殑琛屾暟
  const renderCount = Math.min(
    maxRendered,
    Math.max(baseRows, baseRows + overscanRows * 2)
  )

  // 浠ヨ鍙ｄ腑鐐逛负閿氱偣璁＄畻 start/end
  const anchorIndex = Math.floor((scrollTopClamped + viewportHeight / 2) / rowHeight)
  const maxStart = Math.max(0, total - renderCount)

  let startIndex = Math.min(
    Math.max(anchorIndex - Math.floor(renderCount / 2), 0),
    maxStart
  )
  let endIndex = Math.min(total, startIndex + renderCount)

  if (total > 0 && endIndex <= startIndex) {
    startIndex = Math.min(Math.max(startIndex, 0), total - 1);
    endIndex = Math.min(total, startIndex + renderCount);
  }
  if (!force && startIndex === mapCooldownWinStart.value && endIndex === mapCooldownWinEnd.value) {
    return;
  }
  mapCooldownWinStart.value = startIndex;
  mapCooldownWinEnd.value = endIndex;
  updateMapCooldownVisibleRows();
};

const scheduleMapCooldownRaf = () => {
  mapCooldownScrollPending = true;
  if (mapCooldownScrollRafId) return;
  mapCooldownScrollRafId = window.requestAnimationFrame((timestamp) => {
    mapCooldownScrollRafId = 0;
    if (!mapCooldownScrollPending) return;
    mapCooldownScrollPending = false;
    const now = timestamp || performance.now();
    const scrollEl = mapCooldownScrollRef.value;
    const scrollTop = scrollEl ? scrollEl.scrollTop : mapCooldownLatestScrollTop;
    mapCooldownLatestScrollTop = scrollTop;
    if (!mapCooldownLastChangeTs) {
      mapCooldownLastChangeTs = now;
    }
    const dtMs = Math.max(1, now - (mapCooldownLastTimestamp || now));
    const delta = Math.abs(scrollTop - mapCooldownLastScrollTop);
    const speed = delta / dtMs;
    mapCooldownLastSpeed = speed;
    if (delta > 0) {
      mapCooldownLastChangeTs = now;
      if (mapCooldownIdleTimer) {
        clearTimeout(mapCooldownIdleTimer);
      }
      mapCooldownIdleTimer = setTimeout(() => {
        mapCooldownIdleTimer = null;
        if (
          mapCooldownIsFastScrolling.value &&
          !mapCooldownScrollPending &&
          mapCooldownLastSpeed < mapCooldownFastSpeedThresholdLow
        ) {
          mapCooldownIsFastScrolling.value = false;
          if (mapCooldownPendingRebuild.value) {
            buildCooldownRows({ rebuildAll: false, reason: 'scroll-idle' });
            mapCooldownPendingRebuild.value = false;
            scheduleMapCooldownPrefixRebuild();
          }
        }
      }, mapCooldownScrollIdleMs);
    }
    if (!mapCooldownIsFastScrolling.value && speed > mapCooldownFastSpeedThresholdHigh) {
      mapCooldownIsFastScrolling.value = true;
    }
    mapCooldownLastScrollTop = scrollTop;
    mapCooldownLastTimestamp = now;
    updateMapCooldownWindow(scrollTop);
  });
};

const resetMapCooldownScrollState = () => {
  mapCooldownLatestScrollTop = 0;
  mapCooldownLastScrollTop = 0;
  mapCooldownLastTimestamp = 0;
  mapCooldownLastChangeTs = 0;
  mapCooldownLastSpeed = 0;
  mapCooldownIsFastScrolling.value = false;
  mapCooldownPendingRebuild.value = false;
  if (mapCooldownScrollRafId) {
    cancelAnimationFrame(mapCooldownScrollRafId);
    mapCooldownScrollRafId = 0;
  }
  mapCooldownScrollPending = false;
  mapCooldownIsApplyingScrollAdjust = false;
  mapCooldownFreshKeys.value = new Set();
  if (mapCooldownFreshTimer) {
    clearTimeout(mapCooldownFreshTimer);
    mapCooldownFreshTimer = null;
  }
  if (mapCooldownIdleTimer) {
    clearTimeout(mapCooldownIdleTimer);
    mapCooldownIdleTimer = null;
  }
  if (mapCooldownPrefixRafId) {
    cancelAnimationFrame(mapCooldownPrefixRafId);
    mapCooldownPrefixRafId = 0;
  }
};

const onMapCooldownScroll = (event) => {
  const target = event?.target;
  mapCooldownLatestScrollTop = target?.scrollTop ?? mapCooldownScrollRef.value?.scrollTop ?? 0;
  if (mapCooldownIsApplyingScrollAdjust) return;
  scheduleMapCooldownRaf();
};

const resetMapCooldownFeedState = () => {
  mapCooldownWinStart.value = 0;
  mapCooldownWinEnd.value = Math.min(mapCooldownMaxRendered, mapCooldownRows.value.length);
  updateMapCooldownVisibleRows();
};

const markMapCooldownFreshRows = (keys) => {
  if (!keys.length) return;
  const nextKeys = new Set(mapCooldownFreshKeys.value);
  keys.forEach((key) => nextKeys.add(key));
  mapCooldownFreshKeys.value = nextKeys;
  if (mapCooldownFreshTimer) {
    clearTimeout(mapCooldownFreshTimer);
  }
  const freshUntilTs = performance.now() + 160;
  mapCooldownFreshTimer = setTimeout(() => {
    const clearedKeys = new Set(mapCooldownFreshKeys.value);
    keys.forEach((key) => clearedKeys.delete(key));
    mapCooldownFreshKeys.value = clearedKeys;
    mapCooldownFreshTimer = null;
  }, Math.max(0, freshUntilTs - performance.now()));
};

const isMapCooldownRowFresh = (key) => mapCooldownFreshKeys.value.has(key);

const setupMapCooldownContainerObserver = () => {
  if (mapCooldownContainerResizeObserver) return;
  const scrollEl = mapCooldownScrollRef.value;
  if (!scrollEl) return;
  mapCooldownContainerResizeObserver = new ResizeObserver(() => {
    const viewportHeight = scrollEl.clientHeight || 0;
    if (viewportHeight === 0 && mapCooldownDebug) {
      console.log('[mapcd] container resize to 0 height');
    }
    clampMapCooldownScrollTop({ force: true });
  });
  mapCooldownContainerResizeObserver.observe(scrollEl);
};

const teardownMapCooldownContainerObserver = () => {
  if (!mapCooldownContainerResizeObserver) return;
  mapCooldownContainerResizeObserver.disconnect();
  mapCooldownContainerResizeObserver = null;
};

const pushMapIndexToWorker = () => {
  ensureMapCooldownWorker()
  if (!mapCooldownWorker) return
  if (!mapIndex.value) return

  const mapIndexValue = mapIndex.value
  const mapIndexIsProxy = isProxy(mapIndexValue)
  const raw = mapIndexIsProxy ? toRaw(mapIndexValue) : mapIndexValue

  // 鏂板锛氬悓涓€涓璞″紩鐢ㄥ氨涓嶉噸澶?stringify + SETINDEX
  if (mapCooldownWorkerHasIndex && raw === mapCooldownLastSentIndexRef) return

  mapCooldownPlainIndexCache = JSON.parse(JSON.stringify(raw))
  mapCooldownWorker.postMessage({
    type: 'SETINDEX',
    payload: { mapIndex: mapCooldownPlainIndexCache }
  })

  mapCooldownWorkerHasIndex = true
  mapCooldownLastSentIndexRef = raw
}


const ensureMapCooldownWorker = () => {
  if (mapCooldownWorker) return;
  mapCooldownWorker = new Worker(new URL('./workers/mapCooldown.worker.ts', import.meta.url), { type: 'module' });
  console.log('[mapcd] worker creating');
  mapCooldownWorker.onmessage = (event) => {
    console.log('[mapcd] worker message', event?.data?.type, event?.data);
    const { data } = event || {};
    if (!data) return;
    const payload = data.payload || {};
    if (payload.buildId !== undefined && payload.buildId !== mapCooldownBuildId) return;
    if (data.type === 'PROGRESS') {
      mapCooldownBuildProgress.value = {
        done: payload.done || 0,
        total: payload.total || 0
      };
      return;
    }
    if (data.type === 'RESULT') {
      if (payload.mode === 'showAll') {
        mapCooldownRowsAll.value = payload.rows || [];
      } else if (payload.mode === 'coolingOnly') {
        mapCooldownRowsCooling.value = payload.rows || [];
      }
      if (mapCooldownPendingModes.has(payload.mode)) {
        mapCooldownPendingModes.delete(payload.mode);
      }
      if (mapCooldownPendingModes.size === 0) {
        mapCooldownIsBuilding.value = false;
        mapCooldownNeedsRebuild.value = false;
      }
      scheduleMapCooldownPrefixRebuild();
      nextTick(() => {
        clampMapCooldownScrollTop({ force: true });
      });
      return;
    }
    if (data.type === 'ERROR') {
      console.error('[mapcd worker]', payload.message, payload.stack);
      mapCooldownIsBuilding.value = false;
      mapCooldownPendingModes.clear();
    }
  };
  mapCooldownWorker.onerror = (event) => console.error('[mapcd] worker error', event);
  mapCooldownWorker.onmessageerror = (event) => console.error('[mapcd] worker messageerror', event);
};

const requestMapCooldownBuild = ({ reason = 'update' } = {}) => {
  ensureMapCooldownWorker()
  if (!mapCooldownWorker) return

  mapCooldownTimeZone.value =
    Intl.DateTimeFormat().resolvedOptions().timeZone || mapCooldownTimeZone.value

  // 鏂板锛氬鏋?worker 杩樻病鎷垮埌 index锛屽氨鍏堝彂涓€娆?SETINDEX
  if (!mapCooldownWorkerHasIndex) {
    pushMapIndexToWorker()
  }

  mapCooldownBuildId += 1
  mapCooldownPendingModes = new Set(['showAll', 'coolingOnly'])
  mapCooldownIsBuilding.value = true
  mapCooldownBuildProgress.value = { done: 0, total: 0 }

  const mode = 'showAll'

  // 浣犵殑 debug log 鍙互淇濈暀锛堜絾娉ㄦ剰鍒啀 Object.keys(null)锛?
  const mapIndexValue = mapIndex.value || {}
  console.log('[mapcd] posting BUILD', {
    mode,
    locale: mapCooldownLocale.value,
    timeZone: mapCooldownTimeZone.value,
    nowEpochSec: mapCooldownNowEpoch.value,
    mapIndexKeys: Object.keys(mapIndexValue).length
  })

  // 鍒犻櫎锛歮apIndexIsProxy / plainMapIndex stringify
  // const mapIndexIsProxy = isProxy(mapIndexValue)
  // const plainMapIndex = JSON.parse(JSON.stringify(mapIndexIsProxy ? toRaw(mapIndexValue) : mapIndexValue))

  mapCooldownWorker.postMessage({
    type: 'BUILD',
    payload: {
      buildId: mapCooldownBuildId,
      nowEpochSec: mapCooldownNowEpoch.value,
      locale: mapCooldownLocale.value,
      timeZone: mapCooldownTimeZone.value,
      rowHeight: mapCooldownEstimatedRowHeight,
      mode,
      prefixes: ['ze_', 'bhop_', 'kz_', 'mg_', 'surf_'],
      availabilityLabels: {
        available: t('available'),
        unavailable: t('unavailable')
      },
      reason
    }
  })
};


const buildCooldownRows = ({ rebuildAll = false, reason = 'update' } = {}) => {
  if (!rebuildAll && mapCooldownNeedsRebuild.value) return;
  requestMapCooldownBuild({ reason });
};

const startMapCooldownTimer = () => {
  if (mapCooldownTimer) return;
  mapCooldownTimer = setInterval(() => {
    mapCooldownNowEpoch.value = Math.floor(Date.now() / 1000);
    if (mapCooldownIsFastScrolling.value) {
      mapCooldownPendingRebuild.value = true;
      return;
    }
    buildCooldownRows({ rebuildAll: false, reason: 'timer' });
  }, 5000);
};

const stopMapCooldownTimer = () => {
  if (mapCooldownTimer) {
    clearInterval(mapCooldownTimer);
    mapCooldownTimer = null;
  }
};

const toggleMapCooldownMode = () => {
  coolingOnly.value = !coolingOnly.value;
};

watch(mapCooldownQueryInput, (value) => {
  if (mapCooldownSearchTimer) {
    clearTimeout(mapCooldownSearchTimer);
  }
  mapCooldownSearchTimer = setTimeout(() => {
    mapCooldownSearchQuery.value = value;
    nextTick(() => {
      jumpToBestMapCooldownMatch();
    });
    mapCooldownSearchTimer = null;
  }, 100);
});

watch(mapCooldownSearchQueryTrimmed, (value) => {
  if (!value) {
    mapCooldownHighlightKey.value = '';
  }
});

watch([mapIndex, curLang], () => {
  mapCooldownNeedsRebuild.value = true;
  if (curView.value === 'map_cooldown') {
    mapCooldownNowEpoch.value = Math.floor(Date.now() / 1000);
    buildCooldownRows({ rebuildAll: true, reason: 'index-update' });
    mapCooldownNeedsRebuild.value = false;
    scheduleMapCooldownPrefixRebuild();
  }
});

watch(coolingOnly, () => {
  resetMapCooldownScrollState();
  resetMapCooldownFeedState();
  nextTick(() => {
    setupMapCooldownContainerObserver();
    scheduleMapCooldownPrefixRebuild();
    clampMapCooldownScrollTop({ force: true });
  });
});

watch(mapCooldownRows, () => {
  scheduleMapCooldownPrefixRebuild();
  nextTick(() => {
    clampMapCooldownScrollTop({ force: true });
  });
  if (mapCooldownHighlightKey.value) {
    const stillExists = mapCooldownRows.value.some((row) => row.key === mapCooldownHighlightKey.value);
    if (!stillExists) {
      mapCooldownHighlightKey.value = '';
    }
  }
}, { immediate: true });

const hasMapIndexExgFields = (entry) => (
  entry
  && typeof entry === 'object'
  && ['deadline', 'cooldown_end_epoch', 'duration_raw', 'duration_sec']
    .some((field) => Object.prototype.hasOwnProperty.call(entry, field))
);

const getExgStatus = (sub) => {
  if (!sub) return null;
  const mapKey = normalizeMapKey(sub.map || '');
  const comms = sub.comms || [];
  const commsNorm = Array.isArray(comms)
    ? comms
      .map((value) => {
        if (typeof value === 'string') return value;
        if (value && typeof value === 'object') {
          return value.id ?? value.community_id ?? value.value ?? value.name ?? null;
        }
        return value !== null && value !== undefined ? String(value) : null;
      })
      .filter(Boolean)
    : [];
  const shouldShow = shouldShowExgStatus({
    mapKey,
    comms: commsNorm,
    viewportWidth: viewportWidth.value
  });
  if (!shouldShow) return null;
  const entry = getMapIndexEntry(mapKey);
  if (!entry || !hasMapIndexExgFields(entry)) return null;
  const deadline = typeof entry.cooldown_end_epoch === 'number'
    ? entry.cooldown_end_epoch
    : (typeof entry.deadline === 'number' ? entry.deadline : null);
  const durationRaw = Object.prototype.hasOwnProperty.call(entry, 'duration_raw') ? entry.duration_raw ?? null : null;
  const durationSec = typeof entry.duration_sec === 'number' ? entry.duration_sec : null;
  if (
    (deadline === null || deadline === undefined)
    && (durationRaw === null || durationRaw === undefined)
    && (durationSec === null || durationSec === undefined)
  ) {
    return null;
  }
  const state = getExgStatusState(deadline, durationSec, undefined, durationRaw);
  if (state === 'cooldown' && deadline !== null && deadline !== undefined) {
    const date = formatExgDate(deadline);
    const datetime = formatExgDateTime(deadline);
    const compactTime = formatExgCompactTime(datetime);
    const progress = getExgCooldownProgress(deadline, durationSec);
    return {
      state,
      date,
      datetime,
      compactTime,
      progress
    };
  }
  if (state === 'available') {
    return { state, label: t('map.exg.available') };
  }
  if (state === 'not_available') {
    return { state, label: t('map.exg.not_available') };
  }
  return null;
};
const exgStatusByIndex = computed(() => subscriptions.value.map(sub => getExgStatus(sub)));

const searchMaps = async () => {
  if (!subSearchQuery.value) {
    searchResults.value = [];
    return;
  }
  const query = subSearchQuery.value.trim();
  if (!query) {
    searchResults.value = [];
    return;
  }
  const requestId = ++mapSearchRequestId;
  await ensureMapDataForView('map_sub');
  if (requestId !== mapSearchRequestId) return;
  const runtime = await ensureMapSearchRuntime();
  const matches = [];
  mapSearchIndex.value.forEach((entry) => {
    const score = runtime.scoreSearchEntry(entry, query);
    if (score > 0) {
      const displayName = isChineseLang.value ? (curLang.value === 'zh-TW' ? entry.mapTw : entry.mapCn) : '';
      matches.push({ key: entry.key, val: displayName, score });
    }
  });
  matches.sort((a, b) => (b.score - a.score) || a.key.localeCompare(b.key));
  searchResults.value = matches.slice(0, 20);
};

const selectMapToSub = (m) => {
  selectedMap.value = m.key;
  searchResults.value = [];
};

const toggleSubComm = (id) => {
  if (id === 'all') {
    if (newSubComms.value.includes('all')) newSubComms.value = [];
    else newSubComms.value = ['all'];
  } else {
    if (newSubComms.value.includes('all')) newSubComms.value = [];
    if (newSubComms.value.includes(id)) newSubComms.value = newSubComms.value.filter(c => c !== id);
    else newSubComms.value.push(id);
  }
};

const addSubscription = () => {
  if (!selectedMap.value || newSubComms.value.length === 0) return;
  const nextMap = selectedMap.value;
  const nextComms = [...newSubComms.value];
  const existingIdx = subscriptions.value.findIndex(s => s.map === selectedMap.value);
  if (existingIdx !== -1) {
    subscriptions.value[existingIdx].comms = [...nextComms];
  } else {
    subscriptions.value.push({ map: nextMap, comms: [...nextComms] });
  }
  localStorage.setItem('map_subs', JSON.stringify(subscriptions.value));
  selectedMap.value = null;
  newSubComms.value = ['all'];
  subSearchQuery.value = '';
  searchResults.value = [];
  showToast(t('subscribed'), 2000);
  if (embedMode) {
    postEmbedMessage('CS2ZE_SUBSCRIBE_MAP', {
      map: nextMap
    });
  }
};

const removeSubscription = (idx) => {
  subscriptions.value.splice(idx, 1);
  localStorage.setItem('map_subs', JSON.stringify(subscriptions.value));
};
const removeSubscriptionByMap = (mapName) => {
  const idx = subscriptions.value.findIndex((sub) => sub.map === mapName);
  if (idx >= 0) {
    removeSubscription(idx);
  }
};

const isSubscribed = (mapName) => subscriptions.value.some(s => s.map === mapName);
const toggleSubscription = (mapName) => {
  if (isSubscribed(mapName)) {
    subscriptions.value = subscriptions.value.filter(s => s.map !== mapName);
  } else {
    subscriptions.value.push({ map: mapName, comms: ['all'] });
  }
  localStorage.setItem('map_subs', JSON.stringify(subscriptions.value));
};

const formatSubComms = (comms) => {
  if (comms.includes('all')) return t('all_comm');
  return comms.map(cid => {
    const c = communities.value.find(cm => cm.id === cid);
    return c ? (c.short_name || c.name) : cid;
  }).join(', ');
};

const testNotification = () => {
  if (!hasNotification) return;
  if (Notification.permission === "granted") {
    const cName = communities.value.length > 0 ? communities.value[0].name : "Test Community";
    new Notification(t('sub_notify'), {
      body: `[${cName}] Changed map to: ze_test_map\nTest Server`,
      icon: NOTIFICATION_ICON_PATH
    });
  } else {
    requestPerm();
  }
};

const decorateServer = (srv, comm) => {
  const base = { ...srv };
  if (!base.server_key) base.server_key = getServerKey(base);
  if (!base.community_name) base.community_name = comm ? (comm.name || '') : '';
  if (!base.game) base.game = (comm && comm.game) ? comm.game : 'cs2';
  base.normal_threshold = Number(base.normal_threshold || (comm && comm.normal_threshold) || 62);
  return base;
};

const checkSubscriptions = (srvData, commId) => {
  if (!srvData.map || srvData.map === '-') return;
  const fullId = `${commId}_${getServerKey(srvData)}`;
  const normalizedMap = normalizeMapKey(srvData.map);

  const matchedSub = subscriptions.value.find(sub => {
    const mapMatch = normalizedMap && normalizedMap === normalizeMapKey(sub.map);
    const commMatch = sub.comms.includes('all') || sub.comms.includes(commId);
    return mapMatch && commMatch;
  });

  if (matchedSub) {
    if (lastNotifiedMaps.value[fullId] === undefined) {
      lastNotifiedMaps.value[fullId] = normalizedMap;
      return;
    }
    if (lastNotifiedMaps.value[fullId] !== normalizedMap) {
      if (hasNotification && Notification.permission === "granted") {
        const c = communities.value.find(x => x.id === commId);
        const cName = c ? (c.short_name || c.name) : commId;
        const n = new Notification(t('sub_notify'), {
          body: `[${cName}] Changed map to: ${srvData.map}\n${srvData.name}`,
          icon: NOTIFICATION_ICON_PATH
        });
        n.onclick = () => { window.focus(); copyCmd(srvData); };
      }
      lastNotifiedMaps.value[fullId] = normalizedMap;
    }
  } else {
    if (lastNotifiedMaps.value[fullId]) delete lastNotifiedMaps.value[fullId];
  }
};

const serverStaleMs = 15000;
const refreshIntervalMs = 10000;
const loggedInRefreshIntervalMs = 10000;
const hiddenRefreshIntervalMs = 20000;
const statsRefreshIntervalMs = 15000;
const hiddenStatsRefreshIntervalMs = 30000;
const languageRefreshIntervalMs = 120000;
let serverRefreshTimer = null;
let statsRefreshTimer = null;
let languageRefreshTimer = null;
let serverRefreshEtag = null;
let languageRefreshEtag = null;
let serverRefreshInFlight = false;
let languageRefreshInFlight = false;
let serverRefreshInitialized = false;

const parseConfigPayload = (payload: any): { communities: CommunityRecord[]; join: Record<string, any> } => {
  if (Array.isArray(payload)) {
    return { communities: payload, join: {} };
  }
  if (payload && typeof payload === 'object') {
    return {
      communities: Array.isArray(payload.communities) ? payload.communities : [],
      join: payload.join && typeof payload.join === 'object' ? payload.join : {}
    };
  }
  return { communities: [], join: {} };
};

const applyCommunities = (data: CommunityRecord[]) => {
  communities.value = Array.isArray(data) ? data : [];
  let needsServerRefresh = false;
  communities.value.forEach(c => {
    if (c.servers && c.servers.length > 0) {
      servers.value[c.id] = c.servers.map(srv => decorateServer(srv, c));
    } else if (!servers.value[c.id]) {
      servers.value[c.id] = [];
      needsServerRefresh = true;
    }

    if (!serverCache.value[c.id]) serverCache.value[c.id] = {};

    if (!c.servers || c.servers.length === 0) {
      needsServerRefresh = true;
    }
  });
  if (needsServerRefresh) {
    refreshAllServers();
  }
};

const fetchConfig = async () => {
  try {
    const res = await fetch('/config.json');
    const data = await res.json();
    const parsed = parseConfigPayload(data);
    const defaultStrategy = normalizeJoinStrategy(parsed.join?.default_strategy) || 'rungameid';
    joinConfig.value = { ...parsed.join, default_strategy: defaultStrategy };

    try {
      const savedIds = JSON.parse(localStorage.getItem('comm_order') || '[]');
      if (savedIds.length > 0) {
        parsed.communities.sort((a, b) => {
          const idxA = savedIds.indexOf(a.id);
          const idxB = savedIds.indexOf(b.id);
          if (idxA === -1 && idxB === -1) return 0;
          if (idxA === -1) return 1;
          if (idxB === -1) return -1;
          return idxA - idxB;
        });
      }
    } catch (e) {
      localStorage.removeItem('comm_order');
    }

    applyCommunities(parsed.communities);
  } catch (e) {
    console.error("Config fetch failed", e);
  }
};

const refreshAllServers = async () => {
  if (serverRefreshInFlight) return;
  serverRefreshInFlight = true;
  try {
    const headers = {};
    if (serverRefreshEtag) {
      headers['If-None-Match'] = serverRefreshEtag;
    }
    const res = await fetch(`/servers.json`, { headers });
    if (res.status === 304) {
      return;
    }
    if (!res.ok) {
      return;
    }
    const etag = res.headers.get('ETag') || res.headers.get('etag');
    if (etag) serverRefreshEtag = etag;
    let payload = await res.json();
    const now = Date.now();
    if (Array.isArray(payload)) {
      payload = payload.reduce((acc, item) => {
        if (!item || !item.cid) return acc;
        if (!acc[item.cid]) acc[item.cid] = [];
        acc[item.cid].push(item);
        return acc;
      }, {});
    }
    communities.value.forEach(comm => {
      const cid = comm.id;
      const cache = serverCache.value[cid] || {};
      const data = Array.isArray(payload[cid]) ? payload[cid] : [];
      data.forEach(s => {
        const decorated = decorateServer(s, comm);
        cache[getServerKey(decorated)] = { ...decorated, _lastSeen: now };
        checkSubscriptions(decorated, cid);
      });
      Object.keys(cache).forEach((key) => {
        if (now - cache[key]._lastSeen > serverStaleMs) {
          delete cache[key];
        }
      });
      serverCache.value[cid] = cache;
      servers.value[cid] = Object.values(cache);
    });
  } catch (e) {
  } finally {
    serverRefreshInFlight = false;
  }
};

const getServerRefreshInterval = () => {
  const baseInterval = isLoggedIn.value ? loggedInRefreshIntervalMs : refreshIntervalMs;
  if (document.visibilityState !== 'visible') {
    return Math.max(baseInterval, hiddenRefreshIntervalMs);
  }
  return baseInterval;
};

const getStatsRefreshInterval = () => {
  if (document.visibilityState !== 'visible') {
    return Math.max(statsRefreshIntervalMs, hiddenStatsRefreshIntervalMs);
  }
  return statsRefreshIntervalMs;
};

const scheduleServerRefresh = (immediate = false) => {
  if (serverRefreshTimer) clearInterval(serverRefreshTimer);
  serverRefreshTimer = setInterval(() => refreshAllServers(), getServerRefreshInterval());
  if (immediate) refreshAllServers();
};

const startServerRefresh = () => {
  if (serverRefreshInitialized) return;
  serverRefreshInitialized = true;
  scheduleServerRefresh(true);
};

type ServerListCacheEntry = {
  sourceRef: ServerRecord[] | undefined;
  commRef: CommunityRecord | undefined;
  query: string;
  sortByPlayers: boolean;
  mapIndexRef: Record<string, any>;
  result: ServerRecord[];
};
const serverListCache = new Map<string, ServerListCacheEntry>();
const scheduleStatsRefresh = () => {
  if (statsRefreshTimer) clearInterval(statsRefreshTimer);
  if (!isLoggedIn.value || curView.value !== 'stats') {
    return;
  }
  loadStats();
  statsRefreshTimer = setInterval(() => {
    if (curView.value === 'stats' && isLoggedIn.value) {
      loadStats();
    }
  }, getStatsRefreshInterval());
};

startServerRefresh();
if (languageRefreshTimer) clearInterval(languageRefreshTimer);
languageRefreshTimer = setInterval(() => {
  loadLanguage(true);
}, languageRefreshIntervalMs);

const getServers = (cid) => {
  const sourceList = servers.value[cid];
  const comm = communityById.value[cid];
  const query = normalizedServerMapQuery.value;
  const previous = serverListCache.get(cid);
  if (
    previous &&
    previous.sourceRef === sourceList &&
    previous.commRef === comm &&
    previous.query === query &&
    previous.sortByPlayers === sortByPlayers.value &&
    previous.mapIndexRef === mapIndex.value
  ) {
    return previous.result;
  }

  let list = sourceList ? [...sourceList].map(s => decorateServer(s, comm)) : [];
  if (query) {
    list = list.filter((serverEntry) => {
      const mapName = serverEntry.map || '';
      const entry = getMapTranslationEntry(mapName, serverEntry);
      const candidates = [
        mapName,
        normalizeMapKey(mapName),
        entry.zh_cn || '',
        entry.zh_tw || ''
      ];
      return candidates.some((item) => normalizeSearchText(item).includes(query));
    });
  }
  if (sortByPlayers.value) {
    list.sort((a, b) => {
      if (a.online && !b.online) return -1;
      if (!a.online && b.online) return 1;
      return b.players - a.players;
    });
  }
  serverListCache.set(cid, {
    sourceRef: sourceList,
    commRef: comm,
    query,
    sortByPlayers: sortByPlayers.value,
    mapIndexRef: mapIndex.value,
    result: list
  });
  return list;
};
const filteredCommunities = computed<CommunityRecord[]>(() => {
  const query = normalizedServerMapQuery.value;
  if (!query) return communities.value;
  return communities.value.filter((comm) => getServers(comm.id).length > 0);
});
const serverSearchNotice = computed(() => {
  const query = serverMapQuery.value.trim();
  if (!query) return '';
  let count = 0;
  filteredCommunities.value.forEach((comm) => {
    count += getServers(comm.id).length;
  });
  if (count === 0) {
    return formatTemplate(t('server_search_empty'), { map: query });
  }
  return '';
});
const advancedMonthlySummaryRows = computed<AdvancedSummaryRow[]>(() => {
  return (advancedStatsPayload.value && Array.isArray(advancedStatsPayload.value.monthly_summary))
    ? advancedStatsPayload.value.monthly_summary
    : [];
});
const advancedRows7d = computed<AdvancedDailyRow[]>(() => {
  return (advancedStatsPayload.value && Array.isArray(advancedStatsPayload.value.community_daily_rows_7d))
    ? advancedStatsPayload.value.community_daily_rows_7d
    : [];
});

const formatStatNumber = (value, digits = 1) => {
  const num = Number(value);
  if (!Number.isFinite(num)) return '0.0';
  return num.toFixed(digits);
};
const formatTrend = (value) => {
  const num = Number(value);
  if (!Number.isFinite(num)) return '-';
  return `${num > 0 ? '+' : ''}${num.toFixed(2)}%`;
};
const trendClass = (value) => {
  const num = Number(value);
  if (!Number.isFinite(num) || num === 0) return '';
  return num > 0 ? 'trend-up' : 'trend-down';
};

let lineChartInst = null;
let pieChartInst = null;
let advancedWeekChartInst = null;
let advancedMonthChartInst = null;
let chartLoader: Promise<void> | null = null;

const loadChartJs = () => {
  if (window.Chart) return Promise.resolve<void>(undefined);
  if (chartLoader) return chartLoader;
  chartLoader = new Promise<void>((resolve, reject) => {
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/chart.js';
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('Chart.js load failed'));
    document.head.appendChild(script);
  });
  return chartLoader;
};

const cleanupAdvancedCharts = () => {
  if (advancedWeekChartInst) {
    advancedWeekChartInst.destroy();
    advancedWeekChartInst = null;
  }
  if (advancedMonthChartInst) {
    advancedMonthChartInst.destroy();
    advancedMonthChartInst = null;
  }
};

const renderAdvancedCharts = () => {
  const payload = advancedStatsPayload.value;
  if (!payload) return;
  const chartApi = window.Chart;
  if (!chartApi) return;

  const weekCtx = document.getElementById('statsAdvancedWeekChart');
  const monthCtx = document.getElementById('statsAdvancedMonthChart');
  if (!weekCtx || !monthCtx) return;

  const textColor = isDark.value ? '#d0d0d0' : '#1b1b1b';
  const gridColor = isDark.value ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)';
  chartApi.defaults.color = textColor;
  chartApi.defaults.borderColor = gridColor;

  if (advancedWeekChartInst) {
    advancedWeekChartInst.destroy();
    advancedWeekChartInst = null;
  }
  advancedWeekChartInst = new chartApi(weekCtx, {
    type: 'line',
    data: payload.weekly_chart,
    options: {
      maintainAspectRatio: false,
      scales: {
        x: { ticks: { color: textColor }, grid: { display: false } },
        y: { ticks: { color: textColor }, grid: { color: gridColor } }
      }
    }
  });

  if (advancedMonthChartInst) {
    advancedMonthChartInst.destroy();
    advancedMonthChartInst = null;
  }
  advancedMonthChartInst = new chartApi(monthCtx, {
    type: 'line',
    data: payload.monthly_chart,
    options: {
      maintainAspectRatio: false,
      scales: {
        x: { ticks: { color: textColor }, grid: { display: false } },
        y: { ticks: { color: textColor }, grid: { color: gridColor } }
      }
    }
  });
};

const loadAdvancedStats = async (force = false) => {
  const scheduleAdvancedChartRender = () => {
    nextTick(() => {
      if (!showAdvancedStats.value || advancedStatsLoading.value || !advancedStatsPayload.value) return;
      renderAdvancedCharts();
    });
  };

  if (!isLoggedIn.value || curView.value !== 'stats') return;
  if (advancedStatsLoading.value) return;
  if (advancedStatsPayload.value && !force) {
    scheduleAdvancedChartRender();
    return;
  }
  advancedStatsLoading.value = true;
  advancedStatsError.value = '';
  try {
    await loadChartJs();
    let lastRes: Response | null = null;
    let data: AdvancedStatsPayload | null = null;
    for (const endpoint of ADVANCED_STATS_ENDPOINTS) {
      const res = await fetch(endpoint, { credentials: 'same-origin' });
      lastRes = res;
      if (res.ok) {
        data = (await res.json()) as AdvancedStatsPayload;
        break;
      }
      if (res.status !== 404) {
        break;
      }
    }
    if (!data) {
      throw new Error(`HTTP ${lastRes ? lastRes.status : 0}`);
    }
    advancedStatsPayload.value = data;
  } catch (e) {
    const message = e instanceof Error ? e.message : '';
    if (message.includes('HTTP 401')) {
      advancedStatsError.value = 'Login required to load advanced analytics';
    } else if (message.includes('HTTP 404')) {
      advancedStatsError.value = 'Advanced analytics API is unavailable (404)';
    } else {
      advancedStatsError.value = 'Failed to load advanced analytics';
    }
  } finally {
    advancedStatsLoading.value = false;
    scheduleAdvancedChartRender();
  }
};

const toggleAdvancedStats = () => {
  showAdvancedStats.value = !showAdvancedStats.value;
  if (showAdvancedStats.value) {
    loadAdvancedStats(false);
  } else {
    cleanupAdvancedCharts();
  }
};

const loadStats = async () => {
  if (!isLoggedIn.value || curView.value !== 'stats') return;

  try { await loadChartJs(); } catch (e) { return; }

  let data = null;
  try {
    const res = await fetch('/api/stats');
    if (!res.ok) throw new Error();
    data = await res.json();
  } catch (e) {
    return;
  }

  currentStats.value = data.current_stats;
  totalPlayers.value = data.current_stats.reduce((acc, c) => acc + c.count, 0);
  totalPeak48h.value = data.total_peak_48h || 0;

  let top = null;
  data.current_stats.forEach(c => {
    if (!top || c.count > top.count) top = c;
  });
  topCommunity.value = top;

  curView.value = 'stats';

  if (data.line_chart && Array.isArray(data.line_chart.labels)) {
    data.line_chart.labels = data.line_chart.labels.map((ts) => {
      if (typeof ts !== 'number') return ts;
      const date = new Date(ts * 1000);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    });
  }

  setTimeout(() => {
    const lineCtx = document.getElementById('statsLineChart');
    const pieCtx = document.getElementById('statsPieChart');
    const chartApi = window.Chart;
    if (!chartApi) return;

    const textColor = isDark.value ? '#d0d0d0' : '#1b1b1b';
    const gridColor = isDark.value ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)';
    chartApi.defaults.color = textColor;
    chartApi.defaults.borderColor = gridColor;

    if (lineCtx) {
      if (lineChartInst) {
        lineChartInst.data.labels = data.line_chart.labels;
        lineChartInst.data.datasets = data.line_chart.datasets;
        lineChartInst.options.scales.x.ticks = { color: textColor };
        lineChartInst.options.scales.y = { grid: { color: gridColor }, ticks: { color: textColor } };
        lineChartInst.update('none');
      } else {
        lineChartInst = new chartApi(lineCtx, {
          type: 'line',
          data: data.line_chart,
          options: { maintainAspectRatio: false, scales: { x: { grid: { display: false } } } }
        });
      }
    }

    if (pieCtx) {
      if (pieChartInst) {
        pieChartInst.data.labels = data.pie_chart.labels;
        if (pieChartInst.data.datasets.length > 0 && data.pie_chart.datasets.length > 0) {
          pieChartInst.data.datasets[0].data = data.pie_chart.datasets[0].data;
          pieChartInst.data.datasets[0].backgroundColor = data.pie_chart.datasets[0].backgroundColor;
        } else {
          pieChartInst.data.datasets = data.pie_chart.datasets;
        }
        pieChartInst.update();
      } else {
        pieChartInst = new chartApi(pieCtx, {
          type: 'doughnut',
          data: data.pie_chart,
          options: {
            maintainAspectRatio: false,
            cutout: '70%',
            plugins: { legend: { display: false } }
          }
        });
      }
    }
  }, 0);
};

const getJoinPayload = (srv) => {
  const host = srv.connect_ip || srv.ip || '';
  return {
    ip: host,
    port: srv.port || null,
    name: srv.name || ''
  };
};

const bestEffortCopy = (text) => {
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).catch(() => {
      const textArea = document.createElement("textarea");
      textArea.value = text;
      textArea.style.top = "0";
      textArea.style.left = "0";
      textArea.style.position = "fixed";
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      try {
        document.execCommand('copy');
      } catch (err) {
      }
      document.body.removeChild(textArea);
    });
  } else {
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.top = "0";
    textArea.style.left = "0";
    textArea.style.position = "fixed";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
      document.execCommand('copy');
    } catch (err) {
    }
    document.body.removeChild(textArea);
  }
};

const joinServer = (srv, comm) => {
  const target = decorateServer(srv, comm);
  const address = getConnectAddress(target);
  const strategy = normalizeJoinStrategy(target.join_strategy)
    || normalizeJoinStrategy(comm && comm.join_strategy)
    || normalizeJoinStrategy(joinConfig.value.default_strategy)
    || 'rungameid';
  if (strategy === 'steam_connect') {
    const connectUrl = `steam://connect/${address}`;
    bestEffortCopy(address);
    try {
      window.location.href = connectUrl;
    } catch (err) {
      showToast(`Server address copied: ${address}`);
    }
    return;
  }
  if (strategy === 'clipboard_only') {
    copyText(address, `Server address copied: ${address}`);
    return;
  }
  if (strategy === 'server_browser') {
    bestEffortCopy(address);
    try {
      window.location.href = 'steam://open/servers';
    } catch (err) {
      showToast(`Server address copied: ${address}`);
    }
    return;
  }
  if (embedMode) {
    const sent = postEmbedMessage('CS2ZE_JOIN', getJoinPayload(target));
    if (sent) return;
    copyText(`connect ${address}`, t('copy_console_done'));
    return;
  }
  window.location.href = getFastJoinUrl(target);
};

const fallbackCopy = (text, toastMessage) => {
  const textArea = document.createElement("textarea");
  textArea.value = text;
  textArea.style.top = "0";
  textArea.style.left = "0";
  textArea.style.position = "fixed";
  document.body.appendChild(textArea);
  textArea.focus();
  textArea.select();
  try {
    const successful = document.execCommand('copy');
    if (successful) {
      showToast(toastMessage || (t('copied') + text));
    } else {
      showToast(t('copy_failed'));
    }
  } catch (err) {
    showToast(t('copy_failed'));
  }
  document.body.removeChild(textArea);
};

const copyText = (text, toastMessage) => {
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(() => {
      showToast(toastMessage || (t('copied') + text));
    }).catch(() => fallbackCopy(text, toastMessage));
  } else {
    fallbackCopy(text, toastMessage);
  }
};

const copyCmd = async (srv) => {
  const address = getConnectAddress(srv);
  if (embedMode) {
    const sent = postEmbedMessage('CS2ZE_COPY', {
      text: `connect ${address}`,
      kind: 'connect'
    });
    if (sent) return;
    copyText(`connect ${address}`, t('copy_console_done'));
    return;
  }
  if (!isLoggedIn.value) {
    showToast(t('login_required_copy'));
    return;
  }
  copyText(`connect ${address}`, t('copy_console_done'));
};

const submitFeedback = () => {
  if (!feedbackSubject.value.trim() && !feedbackMessage.value.trim()) {
    showToast(t('feedback_required'));
    return;
  }
  feedbackSubject.value = '';
  feedbackMessage.value = '';
  showToast(t('feedback_sent'));
};
</script>

<style scoped>
/* 1. 鍏ㄥ眬甯冨眬閿佸畾 - 闃叉鍙屾粴鍔ㄦ潯 */
:global(html), :global(body) {
  height: 100%;
  margin: 0;
  overflow: hidden !important;
}

:global(#app) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.content-wrapper {
  height: 100% !important;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 涓诲唴瀹瑰尯涓嶈嚜宸辨粴鍔紝鑰屾槸浣滀负涓€涓?Flex 瀹瑰櫒锛岃瀛愯鍥捐嚜宸卞喅瀹氬浣曟粴鍔?*/
#main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  overflow-x: hidden;
  position: relative;
}

/* 鎵€鏈夎鍥惧寘瑁瑰眰涔熷繀椤讳紶閫掗珮搴?*/
#main-content > .animate-enter {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  min-height: 100%;
  overflow: visible;
}

#main-content.is-mapcd-view {
  overflow: hidden;
}

#main-content > .animate-enter.mapcd-enter {
  flex: 1;
  height: 100%;
  overflow: hidden;
}

.stats-dashboard {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.stats-advanced-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.stats-advanced-panel {
  border: 1px solid var(--border-color, rgba(127, 127, 127, 0.2));
  border-radius: 10px;
  padding: 12px;
  background: var(--card-bg, rgba(127, 127, 127, 0.06));
}

.stats-advanced-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 12px;
}

.stats-advanced-card {
  border: 1px solid var(--border-color, rgba(127, 127, 127, 0.2));
  border-radius: 10px;
  padding: 10px;
  background: var(--card-bg, rgba(127, 127, 127, 0.04));
}

.stats-advanced-canvas {
  position: relative;
  height: 220px;
}

.stats-advanced-canvas canvas {
  width: 100% !important;
  height: 220px !important;
}

.stats-advanced-state {
  padding: 12px;
  color: var(--text-secondary);
}

.stats-advanced-state--error {
  color: #d64545;
}

.stats-advanced-note {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 10px;
}

.stats-advanced-note a {
  color: #8fb8ff;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.stats-advanced-note a:hover {
  color: #b3d0ff;
}

[data-theme="light"] .stats-advanced-note a {
  color: #0b57d0;
}

[data-theme="light"] .stats-advanced-note a:hover {
  color: #174ea6;
}

.stats-advanced-table-wrap {
  margin-top: 12px;
  overflow-x: auto;
}

.stats-advanced-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.stats-advanced-table th,
.stats-advanced-table td {
  border-bottom: 1px solid var(--border-color, rgba(127, 127, 127, 0.2));
  padding: 8px 6px;
  text-align: left;
  white-space: nowrap;
}

.trend-up {
  color: #1d9d63;
}

.trend-down {
  color: #d64545;
}

/* =======================================================
   Windows 11 Fluent Design - Map Cooldown Page
   ======================================================= */

.mapcd-page {
  flex: 1;
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 0;
  margin: 0;
  overflow: hidden;
}

/* 1. 榛樿瀹氫箟涓?鏆楄壊妯″紡 (Dark Mode Base) */
.mapcd-view {
  --w11-bg: rgba(32, 32, 32, 0.75);
  --w11-border: rgba(255, 255, 255, 0.08);
  --w11-text: #ffffff;
  --w11-text-sub: rgba(255, 255, 255, 0.6);
  --w11-hover: rgba(255, 255, 255, 0.05);
  --w11-header-bg: rgba(0, 0, 0, 0.2);
  --w11-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  --w11-accent: var(--accent, #60cdff);

  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

/* 2. 浜壊妯″紡瑕嗗啓 (Light Mode Overrides) */
/* 鍖呭惈涓ょ鎯呭喌锛欻TML鏍囩涓婃湁 data-theme="light" 鎴栬€?绯荤粺鍋忓ソ鏄?light 涓旀病鏈夋墜鍔ㄦ寚瀹?dark */
:global(html[data-theme="light"]) .mapcd-container,
/* 浜壊涓婚瑕嗗啓锛氳窡闅?data-theme */
[data-theme="light"] .mapcd-view {
  --w11-bg: #ffffff;
  --w11-border: #e5e5e5;
  --w11-text: #000000;
  --w11-text-sub: #5f6368;
  --w11-hover: #f9f9f9;
  --w11-header-bg: #ffffff;
  --w11-shadow: 0 4px 16px rgba(0, 0, 0, 0.04), 0 1px 3px rgba(0,0,0,0.02);
  --w11-accent: var(--accent, #005a9e);
}

/* 宸ュ叿鏍忓尯鍩?(Fixed Header) */
.mapcd-toolbar {
  flex-shrink: 0;
  padding: 20px 16px 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mapcd-toolbar-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}

.mapcd-title-wrap {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.mapcd-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary); /* 浣跨敤鍏ㄥ眬瀛椾綋鑹蹭互閫傚簲澶栭儴涓婚 */
}

.mapcd-preparing {
  font-size: 13px;
  color: var(--text-secondary);
  opacity: 0.8;
}

.mapcd-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* Win11 椋庢牸鎸夐挳 */
.mapcd-toggle-btn {
  height: 36px;
  padding: 0 16px;
  border-radius: 6px;
  border: 1px solid var(--w11-border);
  background: var(--w11-hover);
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex: 0 0 auto;      /* 涓嶅厑璁歌鎸ゅ帇鍙樼獎 */
  white-space: nowrap; /* 绂佹涓枃閫愬瓧鎹㈣ */
  min-width: fit-content;
}

.mapcd-toggle-icon {
  width: 20px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 20px;
}
.mapcd-toggle-icon svg {
  display: block;
}

/* 鍏抽敭锛氬浘鏍囬鑹茶窡闅忔寜閽枃瀛楅鑹诧紝娣辨祬鑹查兘鑷姩閫傞厤 */
.mapcd-toggle-btn {
  color: var(--w11-text);
}
.mapcd-toggle-btn:hover {
  color: var(--w11-text);
  background: var(--w11-hover);
}

/* Win11 椋庢牸鎼滅储妗?*/
.mapcd-search {
  display: flex;
  align-items: center;
  height: 36px;
  width: 240px;
  background: var(--w11-hover);
  border: 1px solid var(--w11-border);
  border-radius: 6px; /* 灏忓渾瑙?*/
  padding: 0 8px;
  transition: all 0.2s ease;
}
.mapcd-search:focus-within {
  background: var(--w11-bg);
  border-color: var(--w11-accent);
  box-shadow: 0 0 0 2px rgba(96, 205, 255, 0.2); 
}
.mapcd-searchIcon {
  width: 16px; height: 16px;
  color: var(--text-secondary);
  align-items: center;     /* 鍏抽敭 */
  justify-content: center; /* 鍏抽敭 */
  margin-right: 8px;
  display: flex;
}
.mapcd-searchInput {
  flex: 1;
  border: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
}
.mapcd-clearBtn {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 4px;
  display: flex;
}
.mapcd-clearBtn:hover { color: var(--text-primary); }

.mapcd-hint {
  font-size: 12px;
  color: var(--w11-text-sub);
  background: rgba(255, 165, 0, 0.1);
  border: 1px solid rgba(255, 165, 0, 0.2);
  padding: 8px 12px;
  border-radius: 4px;
}

/* 涓诲鍣細鍗曠嫭鐨勫ぇ鍦嗚鍗＄墖 */
.mapcd-container {
  flex: 1; /* 鍗犳嵁鍓╀綑楂樺害 */
  display: flex;
  flex-direction: column;
  min-height: 0; /* 蹇呴』璁剧疆浠ュ厑璁?flex 瀛愰」婊氬姩 */
  
  background: var(--w11-bg);
  border: 1px solid var(--w11-border);
  border-radius: 8px; /* Win11 鍗＄墖鍦嗚 */
  box-shadow: var(--w11-shadow);
  
  margin: 0 16px 20px 16px; /* 娴姩杈硅窛 */
  overflow: hidden;
  
  /* 鏆楄壊妯″紡寮€鍚ā绯?*/
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

.mapcd-container.is-fast {
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
}


/* 浜壊妯″紡寮哄埗鍏抽棴妯＄硦锛岀‘淇濈函鍑€ */
/* 浜壊涓婚寮哄埗鍏抽棴妯＄硦锛岀‘淇濈函鍑€ */
[data-theme="light"] .mapcd-container {
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
}

.mapcd-table {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* 琛ㄥご锛氬浐瀹氬湪瀹瑰櫒椤堕儴 */
.mapcd-header {
  display: grid;
  grid-template-columns: minmax(200px, 2fr) 1fr 1.3fr minmax(110px, 0.7fr) minmax(150px, 0.9fr);
  align-items: center;
  height: 48px;
  padding: 0 16px;
  background: var(--w11-header-bg);
  border-bottom: 1px solid var(--w11-border);
  font-size: 12px;
  font-weight: 600;
  color: var(--w11-text-sub);
  user-select: none;
}

.mapcd-header .sortable {
  cursor: pointer;
  display: flex;
  align-items: center;
}
.mapcd-header .sortable:hover { color: var(--w11-text); }
.sort-tri { margin-left: 4px; font-size: 10px; opacity: 0.5; }

/* 鍒楄〃涓讳綋锛氬敮涓€鍙粴鍔ㄧ殑鍖哄煙 */
.mapcd-body {
  flex: 1;
  overflow-y: auto !important; /* 寮哄埗寮€鍚瀭鐩存粴鍔?*/
  padding-bottom: 20px;
  scrollbar-width: none;      /* Firefox */
  -ms-overflow-style: none;   /* legacy Edge */
}

:deep(.mapcd-body::-webkit-scrollbar) {
  width: 0;
  height: 0;
}


/* 琛屾牱寮?*/
.mapcd-row {
  display: grid;
  grid-template-columns: minmax(200px, 2fr) 1fr 1.3fr minmax(110px, 0.7fr) minmax(150px, 0.9fr);
  align-items: center;
  height: 48px; /* 楂樺瘑搴?*/
  padding: 0 16px;
  border-bottom: 1px solid rgba(128,128,128, 0.08); /* 鏋佺粏鍒嗗壊绾?*/
  color: var(--w11-text);
  font-size: 13px;
  transition: background 0.1s ease;
}

.mapcd-container.is-fast .mapcd-row {
  transition: none;
}

.mapcd-row .mapcd-col-length,
.mapcd-row .mapcd-col-availability {
  height: 100%;
}

.mapcd-row:hover {
  background: var(--w11-hover);
}

/* 鍒楀榻?*/
.mapcd-cell {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  padding-right: 8px;
}

.mapcd-col-map { display: flex; flex-direction: column; justify-content: center; }
.mapcd-col-deadline { display: flex; align-items: center; }
.mapcd-col-length, .mapcd-col-availability { display: flex; justify-content: center; align-items: center; text-align: center; padding-left: 14px; padding-right: 0;}

.mapcd-map-key { font-weight: 600; }
.mapcd-map-cn { font-size: 11px; color: var(--w11-text-sub); line-height: 1.2; margin-top: 2px; }

/* 鐘舵€佸浘鏍囷細鍦嗚姝ｆ柟褰?(Win11 椋庢牸) */
.mapcd-availability {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 4px; /* 灏忓渾瑙?*/
  line-height: 0;
}

.mapcd-availability.is-available {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
}
.mapcd-availability.is-cooldown {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.mapcd-availability-icon svg {
  width: 14px; height: 14px;
  display: block;
  margin: auto;
}

.mapcd-availability-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  line-height: 0;
}

.mapcd-empty {
  padding: 40px;
  text-align: center;
  color: var(--w11-text-sub);
}

/* 绉诲姩绔€傞厤 */
@media (max-width: 768px) {
  .mapcd-view { padding: 0; max-width: 100%; height: 100vh; }
  .mapcd-container { margin: 0; border-radius: 0; border: none; }
  .mapcd-toolbar { padding: 10px; }
  .mapcd-header, .mapcd-row {
    padding: 0 10px;
    grid-template-columns: 1fr 0.5fr 72px; /* 绠€鍖栧垪 */
    font-size: 12px;
  }
  .mapcd-col-ach, .mapcd-col-length { display: none !important; }
}

.map-sub-view .sub-tags {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.map-sub-view .exg-inline-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  line-height: 30px;
  font-weight: 600;
  padding: 0;
  background: none;
  border: none;
  cursor: default;
  pointer-events: none;
}

.map-sub-view .exg-inline-time {
  opacity: 0.9;
  font-weight: 600;
}

.map-sub-view .exg-icon {
  width: 16px;
  height: 16px;
  flex: 0 0 auto;
}

[data-theme="dark"] .map-sub-view .exg-inline-status--cooldown {
  color: rgba(74, 163, 255, 0.85);
}

[data-theme="dark"] .map-sub-view .exg-inline-status--available {
  color: rgba(55, 208, 125, 0.85);
}

[data-theme="light"] .map-sub-view .exg-inline-status--cooldown {
  color: rgba(0, 90, 158, 0.8);
}

[data-theme="light"] .map-sub-view .exg-inline-status--available {
  color: rgba(0, 120, 70, 0.8);
}

.map-sub-view .exg-inline-status--unavailable {
  color: var(--status-offline);
}

.sub-container {
  width: 100%;
  max-width: 980px;
  margin: 0 auto;
  padding: 0 16px;
}
</style>
