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
      <div class="sidebar-logo"><img :src="currentLogoPath" alt="Logo" decoding="async"></div>

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
            <div class="header-logo"><img :src="currentLogoPath" alt="Logo"></div>
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
                    <a v-if="steamId" :href="'https://steamcommunity.com/profiles/' + steamId" target="_blank" class="profile-link">
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
          <img v-if="getCommunityLogoMeta(comm).url" :src="getCommunityLogoMeta(comm).url"  :class="{ 'logo-svg': getCommunityLogoMeta(comm).isSvg, 'logo-invert': getCommunityLogoMeta(comm).isSvg && isDark }"loading="lazy" decoding="async">>
          <span>{{ comm.name }}</span>
        </div>
      </div>

      <div class="server-search-bar" v-show="curView === 'servers'">
        <input class="server-search-input" type="text" v-model="serverMapQueryInput" :placeholder="t('server_search_ph')">
      </div>

      <div id="main-content" ref="mainContentRef">
        <div v-show="curView === 'servers'" class="animate-enter">
          <div v-if="serverSearchNotice" class="server-search-hint">
            {{ serverSearchNotice }}
          </div>
          <div v-for="comm in filteredCommunities" :key="comm.id" :id="'comm-' + comm.id" style="margin-bottom: 40px;">
            <h3 class="desktop-header" v-if="!isMobile" style="border-left: 4px solid var(--accent); padding-left: 10px; margin: 0 0 16px 0;">{{ comm.name }}</h3>
            <div class="community-title-bar" v-if="isMobile" :id="'comm-mob-' + comm.id">
              <img v-if="getCommunityLogoMeta(comm).url" :src="getCommunityLogoMeta(comm).url" :class="{ 'logo-svg': getCommunityLogoMeta(comm).isSvg, 'logo-invert': getCommunityLogoMeta(comm).isSvg && isDark }">
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

        <div v-show="curView === 'map_sub' && isLoggedIn" class="animate-enter">
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
                  <div class="sub-comms">{{ formatSubComms(sub.comms) }}</div>
                </div>
                <div class="sub-actions">
                  <div v-if="exgStatusByIndex[idx]" class="exg-status-stack">
                    <div
                      v-if="exgStatusByIndex[idx].state === 'available'"
                      class="exg-pill exg-pill--available"
                    >
                      {{ exgStatusByIndex[idx].label }}
                    </div>
                    <div
                      v-else-if="exgStatusByIndex[idx].state === 'cooldown'"
                      class="exg-pill exg-pill--cooldown"
                      @mouseenter="showExgTooltip($event, exgStatusByIndex[idx].tooltipText)"
                      @mouseleave="hideExgTooltip"
                    >
                      <div class="exg-pill-line1">{{ exgStatusByIndex[idx].prefix }}</div>
                      <div class="exg-pill-line2">{{ exgStatusByIndex[idx].datetimeDisplay }}</div>
                    </div>
                    <div v-else class="exg-pill exg-pill--unavailable">
                      {{ exgStatusByIndex[idx].label }}
                    </div>
                  </div>
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

        <Teleport to="body">
          <div
            v-if="exgTooltip.visible"
            ref="exgTooltipRef"
            class="exg-tooltip"
            :style="{ top: `${exgTooltip.top}px`, left: `${exgTooltip.left}px` }"
          >
            {{ exgTooltip.text }}
          </div>
        </Teleport>

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
          </div>
          <div v-else class="login-required">
            <strong>{{ t('login_required_title') }}</strong>
            <div>{{ t('login_required_stats') }}</div>
          </div>
        </div>

          <div v-show="curView === 'map_cooldown'" class="animate-enter">
          <div class="mapcd-page">
            <div class="mapcd-content">
              <div class="sub-search-area mapcd-search-area">
                <input
                  ref="mapCooldownSearchInputRef"
                  class="sub-search-box"
                  type="text"
                  v-model="mapCooldownQueryInput"
                  :placeholder="t('mapcd_search_ph')"
                  autocomplete="off"
                  spellcheck="false"
                  @keydown="onMapCooldownSearchKeydown"
                >
              </div>

              <div class="mapcd-divider"></div>

              <div class="mapcd-title-slot">
                <div class="mapcd-title-row">
                  <h3 style="margin-bottom:16px; opacity:0.8">{{ mapCooldownTitle }}</h3>
                  <div v-if="mapCooldownIsBuilding" class="mapcd-preparing">
                    {{ isChineseLang ? '准备中…' : 'Preparing…' }}{{ mapCooldownProgressText }}
                  </div>
                </div>
              </div>

              <div class="mapcd-container">
                <div class="mapcd-table">
                  <div class="mapcd-header">
                    <div class="mapcd-cell mapcd-col-map">{{ t('map') }}</div>
                    <div class="mapcd-cell mapcd-col-ach">{{ t('achievement') }}</div>
                    <div class="mapcd-cell mapcd-col-deadline">{{ t('cooldown_deadline') }}</div>
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
                      :ref="(el) => registerMapCooldownRowEl(el, row.key)"
                    >
                      <div class="mapcd-cell mapcd-col-map">
                        <div class="mapcd-map-key-row">
                          <div class="mapcd-map-key">{{ row.mapLine1 }}</div>
                        </div>
                        <div v-if="isChineseLang && row.mapLine2" class="mapcd-map-cn">{{ row.mapLine2 }}</div>
                      </div>
                      <div class="mapcd-cell mapcd-col-ach">{{ row.achievement || '-' }}</div>
                      <div class="mapcd-cell mapcd-col-deadline">{{ row.deadlineText }}</div>
                      <div class="mapcd-cell mapcd-col-length">{{ row.durationText }}</div>
                      <div class="mapcd-cell mapcd-col-availability">
                        <span
                          class="mapcd-availability"
                          :class="row.availability === 'available' ? 'is-available' : 'is-cooldown'"
                          :title="mapCooldownIsFastScrolling ? '' : row.availabilityTitle"
                        >
                          <span v-if="row.availability === 'available'" class="mapcd-availability-icon" v-html="icons.check"></span>
                          <span v-else class="mapcd-availability-icon" v-html="icons.cross"></span>
                        </span>
                      </div>
                    </div>
                    <div class="mapcd-bottom-spacer" :style="{ height: `${mapCooldownBottomSpacerPx}px` }"></div>
                    <div v-if="mapCooldownRows.length === 0 && !mapCooldownIsBuilding && !mapCooldownSearchQueryTrimmed" class="mapcd-empty">
                      {{ t('no_data') }}
                    </div>
                    <div class="mapcd-edge-fade mapcd-edge-fade--top"></div>
                    <div class="mapcd-edge-fade mapcd-edge-fade--bottom"></div>
                  </div>
                </div>
              </div>
              <div class="mapcd-actions-row">
                <button class="mapcd-toggle-btn" type="button" @click="toggleMapCooldownMode">
                  {{ mapcdToggleBtnLabel }}
                </button>
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
      <div class="fixed-logo"><img :src="currentLogoPath" alt="nerv_logo"></div>
    </div>
    <div class="toast" v-if="toastMsg" :class="{show: toastMsg}">{{ toastMsg }}</div>
  </div>
</template>

<script setup>
import { computed, isProxy, nextTick, onMounted, onUnmounted, ref, toRaw, watch } from 'vue';
import { buildMapSearchIndex, createOpenCCConverter, formatExgDate, formatExgDateTime, getExgStatusState, normalizeSearchText, normalizeZh, scoreSearchEntry, shouldShowExgStatus, stripBracketSegments, validateMapIndexEntry } from './mapSearchUtils';

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
  check: `<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3.5 8.5l2.5 2.5 6-6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  cross: `<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>`
};
const icons = ICONS;

const LOGO_PATHS = { B: '/static/nerv_logo.png', W: '/static/nerv_logo.png' };
const FAVICON_PATHS = { light: '/static/nerv_logo.png', dark: '/static/nerv_logo.png' };
const STEAM_LOGO_PATH = '/static/steam_logo.svg';
const VIEW_ROUTES = { servers: '/', map_sub: '/map-sub', map_cooldown: '/map-cooldown', stats: '/stats', feedback: '/feedback' };
const INITIAL_CONFIG = props.initialConfig || [];

const communities = ref(Array.isArray(INITIAL_CONFIG) ? INITIAL_CONFIG : []);
const servers = ref(window.__INITIAL_SERVERS__ || {});
const serverCache = ref({});
if (window.__INITIAL_SERVERS__) {
  Object.keys(window.__INITIAL_SERVERS__).forEach(cid => {
    const sList = window.__INITIAL_SERVERS__[cid];
    const cacheMap = {};
    const now = Date.now();
    sList.forEach(s => {
      const key = `${s.ip}:${s.port}`;
      cacheMap[key] = { ...s, _lastSeen: now };
    });
    serverCache.value[cid] = cacheMap;
  });
}
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
const feedbackSubject = ref('');
const feedbackMessage = ref('');
const mainContentRef = ref(null);
const serversScrollTop = ref(0);

const currentStats = ref([]);
const totalPlayers = ref(0);
const totalPeak48h = ref(0);
const topCommunity = ref(null);

const subSearchQuery = ref('');
const mapTranslations = ref({});
const mapIndex = ref({});
const mapSearchIndex = ref([]);
const mapIndexConverter = createOpenCCConverter();
const searchResults = ref([]);
const selectedMap = ref(null);
const newSubComms = ref(['all']);
const subscriptions = ref([]);
const lastNotifiedMaps = ref({});
const hasNotification = typeof Notification !== 'undefined';
const notificationPermission = ref(hasNotification ? Notification.permission : 'denied');
const exgTooltip = ref({
  visible: false,
  text: '',
  top: 0,
  left: 0
});
const exgTooltipRef = ref(null);

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
const sysLang = navigator.language || navigator.userLanguage;

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

const EMBED_TARGET_ORIGIN = 'https://www.cs2ze.org';
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
const formatTemplate = (template, vars = {}) => template.replace(/\{(\w+)\}/g, (_, key) => vars[key] ?? '');
const langLabel = computed(() => (curLang.value || '').startsWith('zh') ? '中文' : 'English');
const isChineseLang = computed(() => curLang.value.includes('zh'));
const currentLogoPath = computed(() => isDark.value ? LOGO_PATHS.W : LOGO_PATHS.B);
const steamLogoPath = computed(() => STEAM_LOGO_PATH);
const steamProfileName = computed(() => steamProfile.value.name || 'Steam User');
const steamProfileAvatar = computed(() => steamProfile.value.avatar || steamLogoPath.value);
const getCommunityLogoMeta = (comm) => {
  if (!comm) return { url: '', isSvg: false };
  if (isDark.value && comm.logo_dark) {
    return { url: comm.logo_dark, isSvg: Boolean(comm.logo_dark_is_svg) };
  }
  if (!isDark.value && comm.logo_light) {
    return { url: comm.logo_light, isSvg: Boolean(comm.logo_light_is_svg) };
  }
  return { url: comm.logo || '', isSvg: Boolean(comm.logo_is_svg) };
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
const restoreServersScroll = async () => {
  await nextTick();
  const container = getMainScrollContainer();
  if (container) {
    container.scrollTop = serversScrollTop.value;
  } else {
    window.scrollTo(0, serversScrollTop.value);
  }
};
watch(curView, (nextView, prevView) => {
  if (prevView === 'servers' && nextView !== 'servers') {
    saveServersScroll();
  }
  if (nextView === 'servers' && prevView !== 'servers') {
    restoreServersScroll();
  }
  if (nextView === 'map_cooldown') {
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
      setupMapCooldownResizeObserver();
      setupMapCooldownContainerObserver();
      scheduleMapCooldownPrefixRebuild();
      clampMapCooldownScrollTop({ force: true });
    });
  }
  if (prevView === 'map_cooldown' && nextView !== 'map_cooldown') {
    stopMapCooldownTimer();
    resetMapCooldownScrollState();
    teardownMapCooldownResizeObserver();
    teardownMapCooldownContainerObserver();
  }
});
watch([isLoggedIn, curView], () => {
  scheduleServerRefresh();
  scheduleStatsRefresh();
});

const updateFavicon = () => {
  const icon = document.getElementById('favicon');
  if (!icon) return;
  icon.href = isDark.value ? FAVICON_PATHS.dark : FAVICON_PATHS.light;
};

watch(curLang, () => document.title = t('app_title'), { immediate: true });
const handleResize = () => {
  viewportWidth.value = window.innerWidth;
  isMobile.value = window.innerWidth <= 768;
  if (isMobile.value) {
    exgTooltip.value = { ...exgTooltip.value, visible: false };
  }
  if (curView.value === 'map_cooldown') {
    mapCooldownLatestScrollTop = mapCooldownScrollRef.value?.scrollTop || mapCooldownLatestScrollTop;
    nextTick(() => {
      scheduleMapCooldownPrefixRebuild();
      clampMapCooldownScrollTop({ force: true });
    });
  }
};

const showExgTooltip = (event, datetime) => {
  if (!datetime || viewportWidth.value < 768) return;
  const target = event?.currentTarget;
  if (!target || typeof target.getBoundingClientRect !== 'function') return;
  const rect = target.getBoundingClientRect();
  exgTooltip.value = {
    visible: true,
    text: datetime,
    top: 0,
    left: 0
  };
  nextTick(() => {
    requestAnimationFrame(() => {
      const tooltipEl = exgTooltipRef.value;
      if (!tooltipEl) return;
      const tooltipRect = tooltipEl.getBoundingClientRect();
      const padding = 8;
      const tooltipOffset = 8;
      const centeredLeft = rect.left + rect.width / 2 - tooltipRect.width / 2;
      const left = Math.min(
        Math.max(padding, centeredLeft),
        window.innerWidth - tooltipRect.width - padding
      );
      const top = Math.max(padding, rect.top - tooltipRect.height - tooltipOffset);
      exgTooltip.value = {
        ...exgTooltip.value,
        top,
        left
      };
    });
  });
};

const hideExgTooltip = () => {
  exgTooltip.value = { ...exgTooltip.value, visible: false };
};

const handleGlobalClick = (e) => {
  const target = e.target;
  const inLang = target.closest('.dropdown-menu') || target.closest('.control-btn') || target.closest('.profile-btn');
  if (!inLang) {
    showLangMenu.value = false;
    showSubPopover.value = false;
    showProfileMenu.value = false;
  }
};
const handleVisibilityChange = () => {
  scheduleServerRefresh();
  scheduleStatsRefresh();
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

  if (isDark.value) document.documentElement.setAttribute('data-theme', 'dark');
  updateFavicon();

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

  if (hasNotification) {
    try {
      if (Notification.permission !== "granted") Notification.requestPermission();
    } catch (e) {}
  }

  await loadLanguage();
  await loadTranslations();
  await loadMapIndex();
  await fetchConfig();
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
  if (embedMode) {
    sendEmbedReady();
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
  teardownMapCooldownResizeObserver();
  teardownMapCooldownContainerObserver();
  if (mapCooldownSearchTimer) {
    clearTimeout(mapCooldownSearchTimer);
    mapCooldownSearchTimer = null;
  }
  if (mapCooldownHighlightTimer) {
    clearTimeout(mapCooldownHighlightTimer);
    mapCooldownHighlightTimer = null;
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
  localStorage.setItem('sidebar_collapsed', isCollapsed.value);
};
const toggleTheme = () => {
  isDark.value = !isDark.value;
  document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light');
  updateFavicon();
};
const setLang = (l) => {
  curLang.value = l;
  showLangMenu.value = false;

  const url = new URL(window.location);
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
    localStorage.setItem('sidebar_collapsed', isCollapsed.value);
  }
  if (!nextState) {
    if (sidebarWasAutoExpandedForReorder.value) {
      isCollapsed.value = true;
      document.documentElement.classList.add('sidebar-is-collapsed');
      localStorage.setItem('sidebar_collapsed', isCollapsed.value);
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
const onDragLeave = (e) => {};
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
  try {
    const res = await fetch('/language.json');
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const data = await res.json();
    if (data && typeof data === 'object') {
      i18nData.value = data;
      document.title = t('app_title');
    }
  } catch (e) {
    if (!silent) {
      showToast(t('language_load_failed'));
    }
  }
};

const loadTranslations = async () => {
  try {
    const res = await fetch('/map_translations.json');
    const data = await res.json();
    const normalized = {};
    for (const [key, value] of Object.entries(data)) {
      if (typeof value === 'string') {
        normalized[key] = { zh_cn: value, zh_tw: value };
      } else {
        normalized[key] = {
          zh_cn: (value && (value.zh_cn || value.cn)) || '',
          zh_tw: (value && (value.zh_tw || value.tw)) || ''
        };
      }
    }
    mapTranslations.value = normalized;
  } catch (e) {}
};

const loadMapIndex = async () => {
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
    mapSearchIndex.value = buildMapSearchIndex(mapIndex.value, mapIndexConverter);
  } catch (e) {
    mapIndex.value = {};
    mapSearchIndex.value = [];
  }
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

const getMapTranslationEntry = (mapName, serverEntry) => {
  if (!mapName) return { zh_cn: '', zh_tw: '' };
  if (mapTranslations.value[mapName]) return mapTranslations.value[mapName];
  const normalizedKey = normalizeMapKey(mapName);
  if (normalizedKey && mapTranslations.value[normalizedKey]) return mapTranslations.value[normalizedKey];
  if (serverEntry) {
    return {
      zh_cn: serverEntry.map_cn || '',
      zh_tw: serverEntry.map_tw || ''
    };
  }
  return { zh_cn: '', zh_tw: '' };
};

const getMapTranslation = (mapName) => {
  const entry = getMapTranslationEntry(mapName);
  if (curLang.value === 'zh-TW') return stripBracketSegments(entry.zh_tw || entry.zh_cn || '');
  if (curLang.value === 'zh-CN') return stripBracketSegments(entry.zh_cn || '');
  return '';
};

const getServerMapTranslation = (serverEntry) => {
  if (!serverEntry) return '';
  const entry = getMapTranslationEntry(serverEntry.map, serverEntry);
  if (curLang.value === 'zh-TW') return stripBracketSegments(entry.zh_tw || entry.zh_cn || '');
  if (curLang.value === 'zh-CN') return stripBracketSegments(entry.zh_cn || '');
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
    return mapIndexConverter ? mapIndexConverter(cleaned) : cleaned;
  }
  if (curLang.value === 'zh-CN') return cleaned;
  return '';
};

const ensureCooldownPrefix = (text) => {
  if (!text) return text;
  if (text.endsWith(':') || text.endsWith('：')) return text;
  return `${text}${isChineseLang.value ? '：' : ':'}`;
};

const mapCooldownScrollRef = ref(null);
const coolingOnly = ref(true);
const mapCooldownTitle = computed(() => (coolingOnly.value ? t('mapcd_title_cooldown') : t('mapcd_title_all')));
const mapcdToggleBtnLabel = computed(() => (
  coolingOnly.value
    ? t('mapcd_btn_show_all', 'Show all')
    : t('mapcd_btn_only_cooldown', 'Show cooldown only')
));
const mapCooldownRowsCooling = ref([]);
const mapCooldownRowsAll = ref([]);
const mapCooldownQueryInput = ref('');
const mapCooldownSearchInputRef = ref(null);
const mapCooldownSearchQuery = ref('');
const mapCooldownHighlightKey = ref('');
const mapCooldownNowEpoch = ref(Math.floor(Date.now() / 1000));
const mapCooldownNeedsRebuild = ref(true);
const mapCooldownIsFastScrolling = ref(false);
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
let mapCooldownResizeObserver = null;
let mapCooldownIdleTimer = null;
let mapCooldownPrefixRafId = 0;
let mapCooldownPrefixSums = [0];
let mapCooldownWorker = null;
let mapCooldownBuildId = 0;
let mapCooldownPendingModes = new Set();
let mapCooldownSearchTimer = null;
let mapCooldownHighlightTimer = null;
let mapCooldownContainerResizeObserver = null;
let mapCooldownLastNonZeroViewportHeight = mapCooldownEstimatedRowHeight;
const mapCooldownHeightByKey = new Map();
const mapCooldownRowElByKey = new Map();

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

const mapCooldownSearchQueryTrimmed = computed(() => mapCooldownSearchQuery.value.trim());
const mapCooldownSearchQueryNorm = computed(() => normalizeZh(mapCooldownSearchQuery.value));
const mapCooldownBaseRows = computed(() => (coolingOnly.value ? mapCooldownRowsCooling.value : mapCooldownRowsAll.value));
const mapCooldownFilteredRows = computed(() => {
  const baseRows = mapCooldownBaseRows.value;
  const queryNorm = mapCooldownSearchQueryNorm.value;
  if (!queryNorm) return baseRows;
  return baseRows.filter((row) => (row.searchTextNorm || '').includes(queryNorm));
});
const mapCooldownRows = computed(() => mapCooldownFilteredRows.value);
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
  const idx = mapCooldownFilteredRows.value.findIndex((item) => item.key === row.key);
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
  const rows = mapCooldownFilteredRows.value;
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
  const baseRows = Math.max(1, Math.ceil(viewportHeight / rowHeight));
  const overscanRows = Math.min(120, Math.max(30, Math.ceil(baseRows * 1.2)));
  const renderCount = Math.min(mapCooldownMaxRendered, Math.max(baseRows, baseRows + overscanRows * 2));
  const anchorIndex = Math.floor((scrollTopClamped + viewportHeight / 2) / rowHeight);
  const maxStart = Math.max(0, total - renderCount);
  let startIndex = Math.min(Math.max(anchorIndex - Math.floor(renderCount / 2), 0), maxStart);
  let endIndex = Math.min(total, startIndex + renderCount);
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

const registerMapCooldownRowEl = (el, key) => {
  if (!key) return;
  if (el) {
    mapCooldownRowElByKey.set(key, el);
    if (mapCooldownResizeObserver) {
      mapCooldownResizeObserver.observe(el);
    }
  } else {
    const existing = mapCooldownRowElByKey.get(key);
    if (existing && mapCooldownResizeObserver) {
      mapCooldownResizeObserver.unobserve(existing);
    }
    mapCooldownRowElByKey.delete(key);
  }
};

const setupMapCooldownResizeObserver = () => {
  if (mapCooldownResizeObserver) return;
  mapCooldownResizeObserver = new ResizeObserver((entries) => {
    let changed = false;
    entries.forEach((entry) => {
      const key = entry.target?.dataset?.key;
      if (!key) return;
      const nextHeight = Math.ceil(entry.contentRect.height);
      const prevHeight = mapCooldownHeightByKey.get(key);
      if (prevHeight !== nextHeight) {
        mapCooldownHeightByKey.set(key, nextHeight);
        changed = true;
      }
    });
    if (changed) {
      scheduleMapCooldownPrefixRebuild();
    }
  });
  mapCooldownRowElByKey.forEach((el) => {
    mapCooldownResizeObserver.observe(el);
  });
};

const teardownMapCooldownResizeObserver = () => {
  if (!mapCooldownResizeObserver) return;
  mapCooldownResizeObserver.disconnect();
  mapCooldownResizeObserver = null;
  mapCooldownRowElByKey.clear();
};

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
  ensureMapCooldownWorker();
  if (!mapCooldownWorker) return;
  mapCooldownTimeZone.value = Intl.DateTimeFormat().resolvedOptions().timeZone || mapCooldownTimeZone.value;
  mapCooldownBuildId += 1;
  mapCooldownPendingModes = new Set(['showAll', 'coolingOnly']);
  mapCooldownIsBuilding.value = true;
  mapCooldownBuildProgress.value = { done: 0, total: 0 };
  const mode = 'showAll';
  const mapIndexValue = mapIndex.value || {};
  const mapIndexIsProxy = isProxy(mapIndexValue);
  console.log('[mapcd] posting BUILD', {
    mode,
    locale: mapCooldownLocale.value,
    timeZone: mapCooldownTimeZone.value,
    nowEpochSec: mapCooldownNowEpoch.value,
    mapIndexKeys: Object.keys(mapIndexValue).length
  });
  console.log('[mapcd] mapIndex isProxy', mapIndexIsProxy);
  const plainMapIndex = JSON.parse(JSON.stringify(mapIndexIsProxy ? toRaw(mapIndexValue) : mapIndexValue));
  mapCooldownWorker.postMessage({
    type: 'BUILD',
    payload: {
      buildId: mapCooldownBuildId,
      mapIndex: plainMapIndex,
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
  });
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
    mapCooldownHeightByKey.clear();
    scheduleMapCooldownPrefixRebuild();
  }
});

watch(coolingOnly, () => {
  resetMapCooldownScrollState();
  resetMapCooldownFeedState();
  mapCooldownHeightByKey.clear();
  nextTick(() => {
    setupMapCooldownResizeObserver();
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
  && ['cooldown_end_epoch', 'duration_raw', 'duration_sec']
    .some((field) => Object.prototype.hasOwnProperty.call(entry, field))
);

const getExgStatus = (sub) => {
  if (!sub) return null;
  const mapKey = normalizeMapKey(sub.map || '');
  const comms = sub.comms || [];
  const shouldShow = shouldShowExgStatus({
    mapKey,
    comms,
    viewportWidth: viewportWidth.value
  });
  if (!shouldShow) return null;
  const entry = getMapIndexEntry(mapKey);
  if (!entry || !hasMapIndexExgFields(entry)) return null;
  const deadline = typeof entry.cooldown_end_epoch === 'number' ? entry.cooldown_end_epoch : null;
  const durationRaw = Object.prototype.hasOwnProperty.call(entry, 'duration_raw') ? entry.duration_raw ?? null : null;
  const durationSec = typeof entry.duration_sec === 'number' ? entry.duration_sec : null;
  if ((deadline === null || deadline === undefined) && (durationRaw === null || durationRaw === undefined)) {
    return null;
  }
  const state = getExgStatusState(deadline, durationSec, undefined, durationRaw);
  if (state === 'cooldown' && deadline !== null && deadline !== undefined) {
    const date = formatExgDate(deadline);
    const datetime = formatExgDateTime(deadline);
    const datetimeDisplay = datetime.replace(' - ', ' ');
    const cooldownText = formatTemplate(t('map.exg.cooldown_until'), { date });
    const prefix = ensureCooldownPrefix(cooldownText.replace(date, '').trim());
    const tooltipText = formatTemplate(t('map.exg.cooldown_tooltip'), { datetime: datetimeDisplay });
    return {
      state,
      prefix,
      date,
      datetime,
      datetimeDisplay,
      tooltipText
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

const searchMaps = () => {
  if (!subSearchQuery.value) {
    searchResults.value = [];
    return;
  }
  const query = subSearchQuery.value.trim();
  if (!query) {
    searchResults.value = [];
    return;
  }
  const matches = [];
  mapSearchIndex.value.forEach((entry) => {
    const score = scoreSearchEntry(entry, query);
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
      icon: "/static/nerv_logo.png"
    });
  } else {
    requestPerm();
  }
};

const getServerKey = (srv) => `${srv.ip}:${srv.port}`;
function normalizeIpPort(ip, port) {
  const ipStr = String(ip ?? '').trim();
  const portStr = String(port ?? '').trim();
  if (!ipStr || !portStr) return '';
  return `${ipStr}:${portStr}`;
}

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
          icon: '/static/nerv_logo.png'
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
const languageRefreshIntervalMs = 15000;
let serverRefreshTimer = null;
let statsRefreshTimer = null;
let serverRefreshEtag = null;
let serverRefreshInFlight = false;
let serverRefreshInitialized = false;

const applyCommunities = (data) => {
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

    try {
      const savedIds = JSON.parse(localStorage.getItem('comm_order') || '[]');
      if (savedIds.length > 0) {
        data.sort((a, b) => {
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

    applyCommunities(data);
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
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      scheduleServerRefresh();
    } else {
      scheduleServerRefresh(true);
    }
  });
};

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
scheduleStatsRefresh();
setInterval(() => {
  loadLanguage(true);
}, languageRefreshIntervalMs);

const getServers = (cid) => {
  const comm = communities.value.find(c => c.id === cid);
  let list = servers.value[cid] ? [...servers.value[cid]].map(s => decorateServer(s, comm)) : [];
  const query = normalizeSearchText(serverMapQuery.value);
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
  return list;
};
const filteredCommunities = computed(() => {
  const query = normalizeSearchText(serverMapQuery.value);
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

let lineChartInst = null;
let pieChartInst = null;
let chartLoader = null;

const loadChartJs = () => {
  if (window.Chart) return Promise.resolve();
  if (chartLoader) return chartLoader;
  chartLoader = new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/chart.js';
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('Chart.js load failed'));
    document.head.appendChild(script);
  });
  return chartLoader;
};

const loadStats = async () => {
  if (!isLoggedIn.value) return;

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

    const textColor = isDark.value ? '#d0d0d0' : '#1b1b1b';
    const gridColor = isDark.value ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)';
    Chart.defaults.color = textColor;
    Chart.defaults.borderColor = gridColor;

    if (lineCtx) {
      if (lineChartInst) {
        lineChartInst.data.labels = data.line_chart.labels;
        lineChartInst.data.datasets = data.line_chart.datasets;
        lineChartInst.options.scales.x.ticks = { color: textColor };
        lineChartInst.options.scales.y = { grid: { color: gridColor }, ticks: { color: textColor } };
        lineChartInst.update('none');
      } else {
        lineChartInst = new Chart(lineCtx, {
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
        pieChartInst = new Chart(pieCtx, {
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

const getConnectAddress = (srv) => {
  const host = srv.connect_ip || srv.ip;
  if (host && srv.port) {
    return `${host}:${srv.port}`;
  }
  return srv.display_ip || (srv.ip + ':' + srv.port);
};
const getJoinPayload = (srv) => {
  const host = srv.connect_ip || srv.ip || '';
  return {
    ip: host,
    port: srv.port || null,
    name: srv.name || ''
  };
};
const getConnectUrl = (srv, game) => {
  const address = getConnectAddress(srv);
  const appid = String(game || 'cs2').toLowerCase() === 'css' ? 240 : 730;
  return `steam://rungameid/${appid}//+connect%20${address}`;
};
const getFastJoinUrl = (srv) => {
  const address = getConnectAddress(srv);
  const appid = String(srv.game || 'cs2').toLowerCase() === 'css' ? 240 : 730;
  return `steam://rungameid/${appid}//+connect%20${address}`;
};

const joinServer = (srv, comm) => {
  const target = decorateServer(srv, comm);
  const address = getConnectAddress(target);
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
.exg-status-stack {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  text-align: center;
}

.exg-pill {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  min-height: 38px;
  padding: 6px 12px;
  border: none;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  text-align: center;
  transition: background 0.2s ease;
}

.exg-pill--available {
  color: var(--status-online);
  background: rgba(32, 201, 151, 0.12);
}

.exg-pill--available:hover {
  background: rgba(32, 201, 151, 0.18);
}

.exg-pill--cooldown {
  color: var(--status-offline);
  background: rgba(255, 92, 92, 0.12);
  cursor: help;
}

.exg-pill--cooldown:hover {
  background: rgba(255, 92, 92, 0.18);
}

.exg-pill--unavailable {
  color: var(--status-offline);
  background: rgba(255, 92, 92, 0.08);
}

.exg-pill-line1 {
  font-size: 11px;
  opacity: 0.75;
}

.exg-pill-line2 {
  font-size: 12px;
  font-weight: 600;
}

.exg-tooltip {
  position: fixed;
  z-index: 999;
  padding: 6px 10px;
  border-radius: 6px;
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  box-shadow: var(--shadow);
  color: var(--text-primary);
  font-size: 12px;
  white-space: nowrap;
  pointer-events: none;
}

.sub-container {
  width: 100%;
  max-width: 980px;
  margin: 0 auto;
  padding: 0 16px;
}

.mapcd-page {
  --mapcd-surface-bg: var(--card-bg);
  --mapcd-surface-border: var(--card-border);
  --mapcd-surface-radius: 14px;
  --mapcd-card-max: 980px;
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 0 0 16px;
}

.mapcd-content {
  width: 100%;
  max-width: var(--mapcd-card-max);
  margin: 0 auto;
  padding: 0 16px;
  display: flex;
  flex-direction: column;
  gap: 0;
}

.mapcd-search-area {
  margin-top: 58px;
  margin-bottom: 45px;
}

.mapcd-divider {
  height: 1px;
  background: var(--card-border);
  margin: 0;
}

.mapcd-title-slot {
  position: relative;
  height: 110px;
}

.mapcd-title-row {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.mapcd-search-row {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 48px;
  margin-top: 12px;
}

.mapcd-search {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 44px;
  width: 100%;
  padding: 0 12px;
  border-radius: 12px;
  background: color-mix(in srgb, var(--mapcd-surface-bg) 86%, #ffffff 14%);
  border: 1px solid color-mix(in srgb, var(--mapcd-surface-border) 65%, transparent 35%);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.04) inset;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
}

.mapcd-search:focus-within {
  border-color: color-mix(in srgb, var(--mapcd-surface-border) 30%, rgba(96, 165, 250, 0.5));
  box-shadow: 0 0 0 2px rgba(96, 165, 250, 0.25), 0 1px 0 rgba(255, 255, 255, 0.04) inset;
  background: color-mix(in srgb, var(--mapcd-surface-bg) 82%, #ffffff 18%);
}

.mapcd-searchIcon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  color: var(--text-secondary);
  opacity: 0.7;
  pointer-events: none;
}

.mapcd-searchIcon svg {
  width: 16px;
  height: 16px;
  display: block;
}

.mapcd-searchInput {
  flex: 1;
  height: 100%;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--text-primary);
  font-size: 14px;
}

.mapcd-searchInput::placeholder {
  color: var(--text-secondary);
  opacity: 0.8;
}

.mapcd-clearBtn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  border: 0;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.mapcd-clearBtn:hover {
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-primary);
}

.mapcd-clearBtn:active {
  background: rgba(255, 255, 255, 0.1);
}

.mapcd-clearBtn svg {
  display: block;
}

.mapcd-search-empty {
  font-size: 12px;
  color: var(--text-secondary);
  padding-left: 4px;
}

.mapcd-search-wrap {
  width: 100%;
  max-width: var(--mapcd-card-max);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.mapcd-container {
  padding: 0;
  background: var(--mapcd-surface-bg);
  border: 1px solid color-mix(in srgb, var(--mapcd-surface-border) 60%, transparent 40%);
  border-radius: var(--mapcd-surface-radius);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.mapcd-card-header {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  min-height: 48px;
  padding: 10px 16px;
  background: color-mix(in srgb, var(--mapcd-surface-bg) 94%, #ffffff 6%);
  border-bottom: 1px solid color-mix(in srgb, var(--mapcd-surface-border) 55%, transparent 45%);
}

.mapcd-card-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.mapcd-actions-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.mapcd-toggle-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 34px;
  padding: 0 14px;
  border-radius: 9px;
  border: 1px solid color-mix(in srgb, var(--mapcd-surface-border) 70%, transparent 30%);
  background: rgba(128, 128, 128, 0.06);
  color: var(--text-primary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}

.mapcd-toggle-btn:hover {
  background: rgba(128, 128, 128, 0.14);
}

.mapcd-toggle-btn:active {
  background: rgba(128, 128, 128, 0.2);
}

.mapcd-preparing {
  font-size: 12px;
  color: var(--text-secondary);
  opacity: 0.8;
}

.mapcd-table {
  margin: 0;
  border-radius: 0 0 calc(var(--mapcd-surface-radius) - 2px) calc(var(--mapcd-surface-radius) - 2px);
  background: transparent;
  border: none;
  box-shadow: none;
  overflow: hidden;
}

.mapcd-body {
  position: relative;
  height: 70vh;
  overflow-y: auto;
  scrollbar-gutter: stable;
  contain: layout paint;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.mapcd-body::-webkit-scrollbar {
  display: none;
  width: 0;
  height: 0;
}

@supports not (scrollbar-gutter: stable) {
  .mapcd-body {
    overflow-y: scroll;
  }
}

.mapcd-edge-fade {
  position: sticky;
  left: 0;
  right: 0;
  height: 16px;
  pointer-events: none;
  z-index: 3;
}

.mapcd-edge-fade--top {
  top: 0;
  background: linear-gradient(to bottom, var(--mapcd-surface-bg), rgba(0, 0, 0, 0));
}

.mapcd-edge-fade--bottom {
  bottom: 0;
  background: linear-gradient(to top, var(--mapcd-surface-bg), rgba(0, 0, 0, 0));
}

.mapcd-top-spacer {
  width: 100%;
}

.mapcd-bottom-spacer {
  width: 100%;
}

.mapcd-header,
.mapcd-row {
  display: grid;
  grid-template-columns: 1.6fr 1.2fr 1.2fr 0.9fr 0.5fr;
  gap: 12px;
  align-items: center;
  padding: 12px 16px;
}

.mapcd-header {
  position: sticky;
  top: 0;
  z-index: 2;
  background: color-mix(in srgb, var(--mapcd-surface-bg) 96%, #ffffff 4%);
  border-bottom: 1px solid color-mix(in srgb, var(--mapcd-surface-border) 50%, transparent 50%);
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.mapcd-row {
  border-bottom: 1px solid color-mix(in srgb, var(--mapcd-surface-border) 35%, transparent 65%);
  font-size: 13px;
  color: var(--text-primary);
  transition: background 0.2s ease, opacity 160ms ease-out;
  min-height: 56px;
  height: auto;
  opacity: 1;
}

.mapcd-row:hover {
  background: rgba(128, 128, 128, 0.05);
}

.mapcd-row.is-highlight {
  background: rgba(120, 160, 255, 0.18);
  box-shadow: inset 0 0 0 1px rgba(120, 160, 255, 0.32);
}

.mapcd-row:last-of-type {
  border-bottom: none;
}

.mapcd-cell {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  height: 100%;
  gap: 2px;
  min-width: 0;
}

.mapcd-col-map,
.mapcd-col-ach {
  align-items: flex-start;
  justify-content: center;
}

.mapcd-col-ach,
.mapcd-col-length {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mapcd-row .mapcd-col-deadline,
.mapcd-row .mapcd-col-length,
.mapcd-row .mapcd-col-availability {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.mapcd-header .mapcd-col-deadline,
.mapcd-row .mapcd-col-deadline {
  flex-direction: row;
  align-items: center;
  justify-content: flex-start;
  text-align: left;
}

.mapcd-row .mapcd-col-deadline {
  justify-content: flex-start;
}

.mapcd-header .mapcd-col-length,
.mapcd-header .mapcd-col-availability,
.mapcd-row .mapcd-col-length,
.mapcd-row .mapcd-col-availability {
  flex-direction: row;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.mapcd-col-availability {
  align-items: center;
}

.mapcd-map-key {
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mapcd-map-key-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.mapcd-map-cn {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: normal;
  line-height: 1.2;
  word-break: break-word;
  min-height: 14px;
}

.mapcd-row.is-fast .mapcd-cell {
  justify-content: center;
}

.mapcd-row.is-fresh {
  opacity: 0.85;
}

.mapcd-row.is-fast {
  grid-template-columns: 1fr;
}

.mapcd-row.is-fast .mapcd-col-ach,
.mapcd-row.is-fast .mapcd-col-deadline,
.mapcd-row.is-fast .mapcd-col-length,
.mapcd-row.is-fast .mapcd-col-availability,
.mapcd-row.is-fast .mapcd-map-cn {
  display: none;
}

.mapcd-availability {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: rgba(128, 128, 128, 0.08);
  line-height: 0;
}

.mapcd-availability-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
}

.mapcd-availability-icon svg {
  display: block;
  margin: auto;
  width: 14px;
  height: 14px;
}

.mapcd-availability.is-available {
  color: var(--status-online);
  background: rgba(32, 201, 151, 0.16);
}

.mapcd-availability.is-cooldown {
  color: var(--status-offline);
  background: rgba(255, 92, 92, 0.16);
}

.mapcd-empty {
  padding: 24px;
  text-align: center;
  color: var(--text-secondary);
}

@media (prefers-reduced-motion: reduce) {
  .mapcd-row {
    transition: none;
  }
}
</style>
