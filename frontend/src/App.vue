<template>
  <div
    :class="{ 'app-blurred': showLoginPrompt, 'is-mobile-layout': isMobile }"
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

    <div id="sidebar" v-if="!embedMode && !isMobile" :class="{ collapsed: isCollapsed }" @click.stop>
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

    <div 
      class="mobile-bottom-nav" 
      :class="{ 'nav-hidden': !isNavVisible }" 
      v-if="isMobile && !embedMode"
    >
      <div class="mob-nav-item" :class="{active: curView === 'servers'}" @click="goToView('servers')">
        <div class="mob-icon" v-html="icons.server"></div>
        <span class="mob-label">{{ t('servers') }}</span>
      </div>
      
      <div class="mob-nav-item" v-if="hasFeature('map_cd')" :class="{active: curView === 'map_cooldown'}" @click="goToView('map_cooldown')">
        <div class="mob-icon" v-html="icons.map"></div>
        <span class="mob-label">{{ t('mapcd') }}</span>
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
          
          <div class="header-toolbar" v-if="curView === 'servers' && !isMobile">
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
            <button class="control-btn mobile-only" v-if="isMobile && isLoggedIn" @click.stop="toggleProfileMenu">
               <div class="icon-svg" v-html="icons.bell"></div>
            </button>

            <div class="desktop-only-icon" v-if="isLoggedIn && !isMobile" style="position: relative;">
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

        <div v-show="curView === 'map_sub' && isLoggedIn" class="animate-enter map-sub-view">
          <div class="sub-container">
            <div class="perm-warning" v-if="notificationPermission !== 'granted'" @click="requestPerm">
              {{ t('notify_warn') }}
            </div>
            <div class="keep-alive-hint" v-if="notificationPermission === 'granted'">
              {{ t('keep_open_hint') }}
            </div>

            <div class="sub-search-area mapcd-search-area">
              <input
                type="text"
                class="sub-search-box"
                v-model="subSearchQuery"
                :placeholder="t('map_sub_search_prompt')"
                autocomplete="off"
                spellcheck="false"
                @input="onMapSubSearchInput"
              >

              <div v-if="mapSubSearchTruncated" class="sub-search-hint">
                {{ t('map_sub_search_full_too_many') }}
              </div>
            </div>

            <div style="border-top:1px solid var(--card-border); margin: 30px 0;"></div>

            <h3 style="margin-bottom:16px; opacity:0.8">{{ t('map_sub_subscribed_section') }}</h3>
            <div class="sub-card-surface">
              <div class="sub-table" v-if="mapSubSubscribedRows.length > 0">
                <div class="sub-row" v-for="row in mapSubSubscribedRows" :key="row.key">
                  <div class="sub-col-info">
                    <div class="sub-map-key-row">
                      <div class="sub-map-key">{{ row.key }}</div>
                    </div>
                    <div class="sub-map-val" v-if="row.displayName">{{ row.displayName }}</div>
                    <div class="sub-tags">
                      <div class="sub-comms" v-if="row.commsLabel">{{ row.commsLabel }}</div>
                      <div
                        v-if="row.status"
                        class="exg-inline-status"
                        :class="row.status.className"
                      >
                        <template v-if="row.status.type === 'available'">
                          <svg class="exg-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                            <path d="M12 2c5.523 0 10 4.477 10 10s-4.477 10-10 10S2 17.523 2 12 6.477 2 12 2Zm3.22 6.97-4.47 4.47-1.97-1.97a.75.75 0 0 0-1.06 1.06l2.5 2.5a.75.75 0 0 0 1.06 0l5-5a.75.75 0 1 0-1.06-1.06Z" fill="currentColor"/>
                          </svg>
                        </template>
                        <template v-else-if="row.status.type === 'cooldown'">
                          <svg class="exg-icon" width="16" height="16" fill="none" viewBox="0 0 24 24" aria-hidden="true">
                            <path d="M12 5a8.5 8.5 0 1 1 0 17 8.5 8.5 0 0 1 0-17Zm0 3a.75.75 0 0 0-.743.648l-.007.102v4.5l.007.102a.75.75 0 0 0 1.486 0l.007-.102v-4.5l-.007-.102A.75.75 0 0 0 12 8Zm7.17-2.877.082.061 1.149 1a.75.75 0 0 1-.904 1.193l-.081-.061-1.149-1a.75.75 0 0 1 .903-1.193ZM14.25 2.5a.75.75 0 0 1 .102 1.493L14.25 4h-4.5a.75.75 0 0 1-.102-1.493L9.75 2.5h4.5Z" fill="currentColor"/>
                          </svg>
                        </template>
                        <template v-else>
                          <svg class="exg-icon" width="16" height="16" fill="none" viewBox="0 0 24 24" aria-hidden="true">
                            <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
                          </svg>
                        </template>
                        <span class="exg-inline-label">{{ row.status.label }}</span>
                        <span v-if="row.status.time" class="exg-inline-time">{{ row.status.time }}</span>
                      </div>
                    </div>
                  </div>
                  <div class="sub-actions">
                    <button class="sub-action-btn sub-action-btn--unsubscribe" @click="handleMapSubUnsubscribe(row)">
                      {{ t('map_sub_unsubscribe') }}
                    </button>
                  </div>
                </div>
              </div>
              <div v-else style="text-align: center; padding: 40px; color: var(--text-secondary);">
                {{ t('no_subs') }}
              </div>
            </div>

            <div v-if="mapSubUnsubscribedRows.length > 0" ref="mapSubUnsubscribedRef" class="sub-unsubscribed-shell">
              <div class="sub-unsubscribed-card sub-card-surface">
                <div class="sub-card-header">
                  <h3 class="sub-card-title">{{ t('map_sub_unsubscribed_section') }}</h3>
                  <button
                    class="sub-bulk-entry"
                    type="button"
                    @click="toggleMapSubMultiSelect"
                  >
                    <span class="sub-bulk-entry-icon" aria-hidden="true">
                      <svg width="24" height="24" fill="none" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path d="M21.707 3.293a1 1 0 0 0-1.414 0L19 4.586l-.293-.293a1 1 0 1 0-1.414 1.414l1 1a1 1 0 0 0 1.414 0l2-2a1 1 0 0 0 0-1.414ZM14.004 17H3l-.117.007A1 1 0 0 0 3 19h11.004l.117-.007A1 1 0 0 0 14.003 17Zm0-6H3l-.117.007A1 1 0 0 0 3 13h11.004l.117-.007A1 1 0 0 0 14.003 11Zm0-6H3l-.117.007A1 1 0 0 0 3 7h11.004l.117-.007A1 1 0 0 0 14.003 5Zm7.703 11.293a1 1 0 0 0-1.414 0L19 17.586l-.293-.293a1 1 0 0 0-1.414 1.414l1 1a1 1 0 0 0 1.414 0l2-2a1 1 0 0 0 0-1.414Zm-1.414-6.5a1 1 0 1 1 1.414 1.414l-2 2a1 1 0 0 1-1.414 0l-1-1a1 1 0 0 1 1.414-1.414l.293.293 1.293-1.293Z" fill="currentColor"/>
                      </svg>
                    </span>
                    {{ mapSubMultiSelectMode ? t('map_sub_cancel') : t('map_sub_bulk_mode') }}
                  </button>
                </div>
                <div class="sub-table">
                  <div
                    class="sub-row"
                    :class="{ 'is-selectable': mapSubMultiSelectMode }"
                    v-for="row in mapSubUnsubscribedRows"
                    :key="row.key"
                    @click="onMapSubRowClick($event, row)"
                  >
                    <div class="sub-col-info">
                      <div class="sub-map-key-row">
                        <div class="sub-map-key">{{ row.key }}</div>
                      </div>
                      <div class="sub-map-val" v-if="row.displayName">{{ row.displayName }}</div>
                    </div>
                    <div class="sub-actions">
                      <label v-if="mapSubMultiSelectMode" class="fd-check" @click.stop>
                        <input
                          class="fd-check__input"
                          type="checkbox"
                          :checked="isSelected(row.key)"
                          @change="toggleSelected(row.key)"
                          :aria-label="`选择 ${row.key}`"
                        />
                        <span class="fd-check__box" aria-hidden="true">
                          <svg
                            v-if="isSelected(row.key)"
                            class="fd-check__icon"
                            width="24"
                            height="24"
                            fill="none"
                            viewBox="0 0 24 24"
                            xmlns="http://www.w3.org/2000/svg"
                            aria-hidden="true"
                          >
                            <path d="M5 13.2 9 17l10-10" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>
                          </svg>
                        </span>
                      </label>
                      <button
                        v-else
                        class="sub-action-btn sub-action-btn--subscribe"
                        @click.stop="handleMapSubSubscribe($event, row)"
                      >
                        {{ t('map_sub_subscribe') }}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
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
          </div>
          <div v-else class="login-required">
            <strong>{{ t('login_required_title') }}</strong>
            <div>{{ t('login_required_stats') }}</div>
          </div>
        </div>

        <div v-show="curView === 'map_cooldown'" class="animate-enter">
          <div class="mapcd-page">
            <div class="mapcd-view">
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

              <div class="mapcd-header-slot">
                <div class="mapcd-header-row">
                  <h3 class="mapcd-title">
                    {{ mapcdAutoShowAll ? t('mapcd_title_fallback_all') : (isAllMapsMode ? t('mapcd_title_all') : t('mapcd_title_cooldown')) }}
                    <span v-if="mapCooldownIsBuilding" class="mapcd-preparing">
                      {{ isChineseLang ? '准备中…' : 'Preparing…' }}{{ mapCooldownProgressText }}
                    </span>
                  </h3>
                  <button class="mapcd-toggle-btn" type="button" @click="toggleMapCooldownMode">
                    {{ isAllMapsMode ? t('mapcd_btn_only_cooldown','Show cooldown only') : t('mapcd_btn_show_all','Show all') }}
                  </button>
                </div>
              </div>

              <div v-if="mapcdAutoShowAll" class="mapcd-hint">{{ t('mapcd_auto_all_hint') }}</div>
              <div v-if="mapcdSortMode === 'availability'" class="mapcd-hint mapcd-sort-hint">{{ t('mapcd_sort_hint') }}</div>

              <div class="mapcd-container">
                <div class="mapcd-table">
                  <div class="mapcd-header">
                    <div class="mapcd-cell mapcd-col-map">{{ t('map') }}</div>
                    <div class="mapcd-cell mapcd-col-ach">{{ t('achievement') }}</div>
                    <div
                      class="mapcd-cell mapcd-col-deadline sortable"
                      :class="{ active: mapcdSortMode === 'availability' }"
                      @click="onMapcdCooldownEndHeaderClick"
                    >
                      <span class="sort-label">{{ t('mapcd_col_cooldown_end') }}</span>
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
                        'is-highlight': row.key === mapCooldownHighlightKey,
                        'is-mobile-card': isMobile /* Hook for card layout */
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
                          :class="getMapCooldownAvailability(row) === 'available' ? 'is-available' : 'is-cooldown'"
                        >
                          <span v-if="getMapCooldownAvailability(row) === 'available'" class="mapcd-availability-icon" v-html="icons.check"></span>
                          <span v-else class="mapcd-availability-icon" v-html="icons.cross"></span>
                        </span>
                      </div>
                    </div>
                    <div class="mapcd-bottom-spacer" :style="{ height: `${mapCooldownBottomSpacerPx}px` }"></div>
                    <div v-if="mapCooldownRows.length === 0 && !mapCooldownIsBuilding" class="mapcd-empty">
                      {{ mapCooldownSearchQueryTrimmed ? t('mapcd_no_results') : t('no_data') }}
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
      <div class="fixed-logo" v-if="!isMobile"><img :src="currentLogoPath" alt="nerv_logo"></div>
    </div>
    <div class="toast" v-if="toastMsg" :class="{show: toastMsg}">{{ toastMsg }}</div>

    <div
      v-if="mapSubPopoverOpen"
      class="sub-popover-backdrop"
      @click="closeMapSubPopover"
    >
      <div
        class="sub-popover-panel"
        @click.stop
      >
        <div class="sub-popover-header">
          <div class="sub-popover-title">{{ mapSubPopoverTitle }}</div>
          <div
            class="sub-popover-hint"
            :class="{ 'is-hidden': mapSubPopoverSelectedCount !== 0 }"
          >
            {{ t('map_sub_choose_communities_required_hint') }}
          </div>
        </div>
        <div class="sub-popover-list">
          <button
            v-for="comm in mapSubPopoverCommunities"
            :key="comm.id"
            type="button"
            class="sub-popover-chip"
            :class="{ 'is-selected': mapSubPopoverSelected.has(comm.id) }"
            @click="toggleMapSubPopoverCommunity(comm.id)"
          >
            <span class="sub-popover-chip-text">{{ comm.name }}</span>
            <span v-if="mapSubPopoverSelected.has(comm.id)" class="sub-popover-chip-icon" v-html="icons.check"></span>
          </button>
        </div>
        <div class="sub-popover-footer">
          <span class="sub-popover-count">
            {{ formatTemplate(t('map_sub_selected_count'), { count: mapSubPopoverSelectedCount }) }}
          </span>
        </div>
        <div class="sub-popover-actions">
          <button class="sub-popover-btn sub-popover-btn--cancel" @click="closeMapSubPopover">
            {{ t('map_sub_cancel') }}
          </button>
          <button
            class="sub-popover-btn sub-popover-btn--confirm"
            :disabled="mapSubPopoverSelectedCount === 0"
            @click="confirmMapSubPopover"
          >
            {{ t('map_sub_confirm') }}
          </button>
        </div>
      </div>
    </div>

    <div
      v-if="mapSubMultiSelectMode && mapSubUnsubscribedRows.length > 0"
      ref="bulkToolbarRef"
      class="sub-bulk-toolbar"
      :style="bulkToolbarStyle"
    >
      <div class="sub-bulk-toolbar-title">
        {{ formatTemplate(t('map_sub_selected_count'), { count: mapSubSelectedCount }) }}
      </div>
      <button
        class="sub-bulk-tool-btn sub-bulk-tool-btn--primary"
        :disabled="mapSubSelectedCount === 0"
        @click.stop="openBulkSubscribePopover($event)"
      >
        <span class="sub-bulk-tool-icon" v-html="icons.check"></span>
        {{ t('map_sub_bulk_subscribe') }}
      </button>
      <button class="sub-bulk-tool-btn" @click="cancelMapSubMultiSelect">
        <span class="sub-bulk-tool-icon" v-html="icons.cross"></span>
        {{ t('map_sub_cancel') }}
      </button>
      <button class="sub-bulk-tool-btn" @click="selectAllMapSub">
        <span class="sub-bulk-tool-icon" v-html="icons.list"></span>
        {{ t('map_sub_select_all') }}
      </button>
      <button class="sub-bulk-tool-btn" @click="clearMapSubSelection">
        <span class="sub-bulk-tool-icon" v-html="icons.trash"></span>
        {{ t('map_sub_clear_all') }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, isProxy, nextTick, onBeforeUnmount, onMounted, onUnmounted, ref, toRaw, watch } from 'vue';
import { buildMapSearchIndex, createOpenCCConverter, formatExgCompactTime, formatExgDateTime, getExgStatusState, normalizeSearchText, scoreSearchEntry, stripBracketSegments, validateMapIndexEntry, shouldShowExgStatus } from './mapSearchUtils';
import { collectSortedMapMatches, normalizeMapSearchQuery } from './utils/map_search_core';

// [ADDED] Mobile Profile Click Handler
const handleMobileProfileClick = () => {
    if(!isLoggedIn.value) {
        startSteamLogin();
    } else {
        goToView('map_sub');
    }
};

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
  grid: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M4 6a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6Zm10-2a2 2 0 0 1 2-2h4a2 2 0 0 1 2-2v4a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2V6ZM4 16a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-4Zm10-2a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-4Z" fill="currentColor"/></svg>`,
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
const joinConfig = ref({ default_strategy: 'rungameid' });
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
const subscriptions = ref([]);
const subscribedMapKeys = ref(new Set());
const mapSearchIndexByKey = ref(new Map());
const mapSubMultiSelectMode = ref(false);
const mapSubSelectedKeys = ref(new Set());
const mapSubResults = ref([]);
const mapSubSearchTruncated = ref(false);
const hiddenAfterUnsub = ref(new Set<string>());
const mapSubPopoverOpen = ref(false);
const mapSubPopoverMode = ref<'single' | 'bulk'>('single');
const mapSubPopoverRow = ref(null);
const mapSubPopoverSelected = ref(new Set());
const lastNotifiedMaps = ref({});
const mapSubUnsubscribedRef = ref<HTMLElement | null>(null);
const bulkToolbarRef = ref<HTMLElement | null>(null);
const bulkToolbarStyle = ref<Record<string, string>>({});
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
document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light');
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

// [NEW] Mobile Nav Scroll Logic Vars
const isNavVisible = ref(true);
const lastScrollTop = ref(0);

watch(curView, (nextView, prevView) => {
  if (prevView === 'servers' && nextView !== 'servers') {
    saveServersScroll();
  }
  if (nextView === 'servers' && prevView !== 'servers') {
    restoreServersScroll();
  }
  if (prevView === 'map_sub' && nextView !== 'map_sub') {
    hiddenAfterUnsub.value = new Set();
    mapSubPopoverOpen.value = false;
    mapSubPopoverSelected.value = new Set();
    // [修改点 2] 切换视图时取消批量选择模式
    mapSubMultiSelectMode.value = false;
  }
  if (nextView === 'map_cooldown') {
    mapCooldownNowEpoch.value = Math.floor(Date.now() / 1000);
    resetMapCooldownScrollState();
    resetMapCooldownFeedState();
    buildCooldownRows({ rebuildAll: true, reason: 'enter-view' });
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
  
  // Reset Nav State
  isNavVisible.value = true;
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

// [UPDATED] Responsive Resize Logic
const handleResize = () => {
  const width = window.innerWidth;
  viewportWidth.value = width;
  isMobile.value = width <= 768;
  
  // Auto collapse for small laptops
  if (width > 768 && width <= 1366) {
     if(!isCollapsed.value && !localStorage.getItem('sidebar_collapsed_manual')) {
         isCollapsed.value = true;
         document.documentElement.classList.add('sidebar-is-collapsed');
     }
  }

  updateBulkToolbarPosition();
  if (curView.value === 'map_cooldown') {
    mapCooldownLatestScrollTop = mapCooldownScrollRef.value?.scrollTop || mapCooldownLatestScrollTop;
    nextTick(() => {
      scheduleMapCooldownPrefixRebuild();
      clampMapCooldownScrollTop({ force: true });
    });
  }
};

// [修改] 滚动处理逻辑：回归元素滚动 (更稳定)
const handleContentScroll = () => {
  if (!isMobile.value) return;
  
  // 获取滚动容器
  const scrollEl = mainContentRef.value;
  if (!scrollEl) return;

  // 直接读取容器的 scrollTop
  const currentScroll = scrollEl.scrollTop;
  
  // 防止 iOS 橡皮筋效果产生负数干扰
  if (currentScroll < 0) return;

  const delta = currentScroll - lastScrollTop.value;
  
  // 防抖阈值
  if (Math.abs(delta) < 10) return;

  // 向下滚动隐藏，向上滚动显示
  if (delta > 0 && currentScroll > 60) {
    isNavVisible.value = false;
  } else {
    isNavVisible.value = true;
  }
  
  lastScrollTop.value = currentScroll;
};

// [ADDED] Global Click Handler to close dropdowns
const handleGlobalClick = () => {
  closeDropdowns();
};

const handleGlobalKeydown = (e) => {
  if (e.key === 'Escape') {
    closeDropdowns();
  }
};

const handleVisibilityChange = () => {
  if (!document.hidden) {
    refreshAllServers();
    if (curView.value === 'map_cooldown') {
      mapCooldownNowEpoch.value = Math.floor(Date.now() / 1000);
      buildCooldownRows({ rebuildAll: true, reason: 'visibility-visible' });
    }
  }
};

let clearToastTimer = () => {
  if (toastTimer) clearTimeout(toastTimer);
};
const showToast = (msg, duration = 3000) => {
  toastMsg.value = msg;
  clearToastTimer();
  toastTimer = setTimeout(() => {
    toastMsg.value = '';
  }, duration);
};

const startSteamLogin = () => {
  if (steamAuthPending.value) return;
  steamAuthPending.value = true;
  const width = 800;
  const height = 600;
  const left = (window.screen.width - width) / 2;
  const top = (window.screen.height - height) / 2;
  steamLoginWindow = window.open(
    '/api/steam/login',
    'SteamLogin',
    `width=${width},height=${height},top=${top},left=${left},scrollbars=yes,resizable=yes`
  );
  if (steamLoginTimer) clearInterval(steamLoginTimer);
  steamLoginTimer = setInterval(() => {
    if (steamLoginWindow && steamLoginWindow.closed) {
      stopSteamLoginWatcher();
      steamAuthPending.value = false;
      fetchSteamStatus(true);
    }
  }, 1000);
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

const updateBulkToolbarPosition = () => {
  if (!mapSubMultiSelectMode.value) return;
  
  const shellEl = mapSubUnsubscribedRef.value;
  const toolbarEl = bulkToolbarRef.value;
  
  if (!shellEl || !toolbarEl) return;
  
  const shellRect = shellEl.getBoundingClientRect();
  const toolbarRect = toolbarEl.getBoundingClientRect();
  const viewportWidthValue = window.innerWidth;
  
  const headerHeight = 85; // Height of the fixed header + buffer
  
  // 1. Vertical Positioning (Sticky behavior)
  // Align with the top of the shell, but stick to header bottom
  // However, since the toolbar is fixed, we just need to know if we should show it
  // Actually, let's keep it fixed at the bottom for mobile, or float for desktop.
  // Implementation: Fixed positioning relative to viewport is easiest.
  // The CSS already handles the fixed position at bottom.
  // We just need to adjust 'left' and 'width' to match the shell container on desktop.
  
  if (viewportWidthValue > 768) {
    // Desktop: Align with the shell container
    bulkToolbarStyle.value = {
      left: `${shellRect.left}px`,
      width: `${shellRect.width}px`,
      bottom: '24px', // Float slightly above bottom
      borderRadius: '16px'
    };
  } else {
    // Mobile: Full width at bottom, above nav bar
    bulkToolbarStyle.value = {
      left: '0',
      width: '100%',
      bottom: isNavVisible.value ? '60px' : '0', // Adjust based on nav visibility
      borderRadius: '0'
    };
  }
};

// [Scroll Lock Helpers]
let bodyOverflowSnapshot = '';
let isBodyScrollLocked = false;
const lockBodyScroll = () => {
  if (isBodyScrollLocked) return;
  const scrollContainer = getMainScrollContainer();
  if (scrollContainer) {
    bodyOverflowSnapshot = scrollContainer.style.overflow;
    scrollContainer.style.overflow = 'hidden';
  } else {
    bodyOverflowSnapshot = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
  }
  isBodyScrollLocked = true;
};
const unlockBodyScroll = () => {
  if (!isBodyScrollLocked) return;
  const scrollContainer = getMainScrollContainer();
  if (scrollContainer) {
    scrollContainer.style.overflow = bodyOverflowSnapshot || '';
  } else {
    document.body.style.overflow = bodyOverflowSnapshot || '';
  }
  isBodyScrollLocked = false;
};

onMounted(async () => {
  window.addEventListener('resize', handleResize);
  
  // [修改] 统一监听滚动容器 (桌面和移动端都使用同一个容器滚动)
  // 注意：不要再监听 window.addEventListener('scroll', handleContentScroll) 了
  const scroller = getMainScrollContainer();
  if (scroller) {
    // 桌面端工具栏定位
    scroller.addEventListener('scroll', updateBulkToolbarPosition, { passive: true });
    // 移动端导航栏显隐 (关键：监听 scroller)
    scroller.addEventListener('scroll', handleContentScroll, { passive: true });
  }

  window.addEventListener('click', handleGlobalClick);
  window.addEventListener('keydown', handleGlobalKeydown);
  window.addEventListener('message', handleSteamMessage);
  document.addEventListener('visibilitychange', handleVisibilityChange);
  document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light');
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
  subscribedMapKeys.value = new Set(subscriptions.value.map((sub) => normalizeMapKey(sub.map)));
  if (hasNotification) {
    try {
      if (Notification.permission !== "granted") Notification.requestPermission();
    } catch (e) {}
  }
  await loadLanguage();
  await loadTranslations();
  await loadMapIndex();
  await fetchConfig();
  startServerRefresh();
  nextTick(() => {
    handleResize();
    const dismissed = localStorage.getItem('steam_prompt_dismissed');
    if (!isLoggedIn.value && dismissed !== 'true') {
      showLoginPrompt.value = true;
    }
    if (initialView === 'stats' && isLoggedIn.value) {
       loadStats(); // No await
    }
    if (embedMode) {
      sendEmbedReady();
    }
  });

  watch(curLang, () => {
    if (subSearchQuery.value) {
       refreshMapSubResults();
    }
  });
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
  mapSubPopoverOpen.value = false;
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
      sidebarWasAutoExpandedForReorder.value = false;
    }
  }
  isEditMode.value = nextState;
};

const toggleSortByPlayers = () => {
  sortByPlayers.value = !sortByPlayers.value;
};

const logout = async () => {
  authState.value = { loggedIn: false, role: 'guest' };
  steamProfile.value = { name: null, avatar: null };
  isPrime.value = false;
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

const onMapSubSearchInput = () => {
  refreshMapSubResults();
};

// Scroll to top of scroll container when changing tabs, IF it's not a back action
// Actually Vue router handles scroll usually, but we use manual view state
// We already have watch(curView) logic above.

const scrollToTop = () => {
  if (mainContentRef.value) {
    mainContentRef.value.scrollTop = 0;
  }
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
    const data = await res.json();
    i18nData.value = data;
  } catch (e) {
    if (!silent) console.error("Lang load failed", e);
  }
};

const loadTranslations = async () => {
  try {
    const res = await fetch('/map_translations.json');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const normalized = {};
    if (data && typeof data === 'object') {
      for (const [k, v] of Object.entries(data)) {
        const cleaned = normalizeMapKey(k);
        if (cleaned) {
          normalized[cleaned] = { zh_cn: v.zh_cn || '', zh_tw: v.zh_tw || '' };
        }
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

    // Validate entries to ensure structure
    Object.entries(mapIndex.value).forEach(([key, entry]) => {
      validateMapIndexEntry(key, entry);
    });
    
    // Build search index
    mapSearchIndex.value = buildMapSearchIndex(mapIndex.value, mapIndexConverter);
    
    // Also build a quick lookup by key for exact matches
    const nextMap = new Map();
    mapSearchIndex.value.forEach((entry) => {
      if (entry && entry.key) nextMap.set(entry.key, entry);
    });
    mapSearchIndexByKey.value = nextMap;
  } catch (e) {
    mapIndex.value = {};
    mapSearchIndex.value = [];
  }
};

// [修改] 只保留 buildMapSearchIndexByKey 的副作用部分（如果需要），实际上上面已经合并了
watch(mapSearchIndex, (newIndex) => {
   const nextMap = new Map();
   newIndex.forEach((entry) => {
      if (entry && entry.key) nextMap.set(entry.key, entry);
   });
   mapSearchIndexByKey.value = nextMap;
}, { immediate: true });


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

const toTraditional = (value) => {
  if (!value) return '';
  return mapIndexConverter ? mapIndexConverter(value) : value;
};

const buildMapTranslationEntry = (mapCn, mapTw) => {
  return { zh_cn: mapCn || '', zh_tw: mapTw || (mapCn ? toTraditional(mapCn) : '') };
};

const getMapTranslationEntry = (mapName, serverEntry) => {
  if (!mapName) return buildMapTranslationEntry('', '');
  
  // 1. Check server-provided override
  if (serverEntry && (serverEntry.map_cn || serverEntry.map_tw)) {
     return buildMapTranslationEntry(serverEntry.map_cn, serverEntry.map_tw);
  }
  
  // 2. Check loaded map_translations.json (legacy)
  // const norm = normalizeMapKey(mapName);
  // if (mapTranslations.value[norm]) {
  //   return mapTranslations.value[norm];
  // }
  
  // 3. Check map_index (new source of truth)
  const entry = getMapIndexEntry(mapName);
  if (entry && entry.map_cn) {
     return buildMapTranslationEntry(entry.map_cn, '');
  }
  
  return buildMapTranslationEntry('', '');
};

const getMapTranslation = (mapName) => {
  const entry = getMapTranslationEntry(mapName);
  if (curLang.value === 'zh-TW' || curLang.value === 'zh-HK') {
    return entry.zh_tw || entry.zh_cn || '';
  }
  return entry.zh_cn || '';
};

const getServerMapTranslation = (srv) => {
  if (!srv || !srv.map) return '';
  return getMapTranslation(srv.map);
};

const getMapIndexDisplayName = (mapName) => {
    return getMapTranslation(mapName);
};

// [NEW] Map Search & Utils
const buildFallbackSearchEntry = (key) => ({ key, normalized: { key, aliases: [], mapCn: '', mapTw: '', achievement: '' } });

const getMapIndexEntry = (mapKey) => {
  const norm = normalizeMapKey(mapKey);
  return mapIndex.value[norm] || null;
};

const getSearchEntryByKey = (mapKey) => {
    if (!mapKey) return buildFallbackSearchEntry('');
    return mapSearchIndexByKey.value.get(mapKey) || buildFallbackSearchEntry(mapKey);
};

const getSearchMatch = (entry, query, { requireExact = false, allowSubstring = true, allowAlias = true, allowPinyin = true } = {}) => {
  if (!entry || !query) return null;
  const normalizedQuery = normalizeSearchText(query);
  if (!normalizedQuery) return null;

  const key = entry.normalized?.key || '';
  const aliases = entry.normalized?.aliases || [];
  const mapCn = entry.normalized?.mapCn || '';
  const mapTw = entry.normalized?.mapTw || '';
  const achievement = entry.normalized?.achievement || '';

  // 1. Exact Key or Alias Match
  if (requireExact) {
    const keyExact = key === normalizedQuery;
    const aliasExact = aliases.includes(normalizedQuery);
    if (!keyExact && !aliasExact) return null;
    const rank = keyExact ? 0 : 2;
    const baseScore = keyExact ? 1000 : 700;
    return { rank, score: baseScore + normalizedQuery.length };
  }

  // 2. Fuzzy / Substring
  let rank = null;
  let baseScore = 0;

  // Key Prefix
  if (key.startsWith(normalizedQuery)) {
    rank = 0;
    baseScore = 1000;
  } else if (allowSubstring && key.includes(normalizedQuery)) {
    rank = 1;
    baseScore = 900;
  }
  
  // CN/TW Name Substring
  const otherMatch = allowSubstring && (mapCn.includes(normalizedQuery) || mapTw.includes(normalizedQuery) || achievement.includes(normalizedQuery));
  if (rank === null && otherMatch) {
      rank = 1;
      baseScore = 860;
  }
  
  if (rank === null && allowAlias) {
    const aliasMatch = aliases.some(alias => alias === normalizedQuery || (allowSubstring && alias.includes(normalizedQuery)));
    if (aliasMatch) {
       rank = 2;
       baseScore = 850;
    }
  }

  if (rank === null) return null;

  // Simple scoring
  // Prefer shorter keys for same match type
  const lengthPenalty = Math.min(100, key.length); 
  
  return { rank, score: baseScore - lengthPenalty };
};

// =========================================================================================
// MAP COOLDOWN LOGIC (REFACTORED)
// =========================================================================================

const mapCooldownScrollRef = ref(null);
const coolingOnly = ref(true);
const isAllMapsMode = computed(() => !coolingOnly.value);

const mapCooldownRowsCooling = ref([]);
const mapCooldownRowsAll = ref([]);
const mapCooldownKeysAll = ref([]); // Just keys for O(1) checks if needed, or ordered list
const mapCooldownRowElByKey = new Map();
const mapCooldownHeightByKey = new Map();
let mapCooldownScrollInitDone = false;
let mapCooldownLastNonZeroViewportHeight = 0;

const mapCooldownQueryInput = ref('');
const mapCooldownSearchInputRef = ref(null);
const mapCooldownSearchQuery = ref('');
const mapCooldownHighlightKey = ref('');
const mapCooldownNowEpoch = ref(Math.floor(Date.now() / 1000));
const mapCooldownNeedsRebuild = ref(true);
const mapCooldownIsFastScrolling = ref(false);
const mapcdSortMode = ref<'default' | 'availability'>('default');

// State for chunked building
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
let mapBehaviorDebugLogged = false;

const mapCooldownLocale = computed(() => curLang.value);
const mapCooldownTimeZone = ref(Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC');

const mapCooldownProgressText = computed(() => {
   const { done, total } = mapCooldownBuildProgress.value || {};
   if (!total) return '';
   const pct = Math.min(100, Math.round((done / total) * 100));
   return ` ${pct}%`;
});

const mapcdQueryTrimmed = computed(() => mapCooldownQueryInput.value.trim());
const mapCooldownSearchQueryTrimmed = computed(() => mapCooldownSearchQuery.value.trim());
const mapCooldownSearchQueryNorm = computed(() => normalizeMapSearchQuery(mapCooldownSearchQuery.value));
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
watch(mapcdDisplayedRows, (newRows) => {
  // When the visible set changes (e.g. search filter), reset window and rebuild prefix
  rebuildMapCooldownPrefixSums();
  const scrollEl = mapCooldownScrollRef.value;
  if (scrollEl) {
     mapCooldownLatestScrollTop = scrollEl.scrollTop;
     updateMapCooldownWindow(mapCooldownLatestScrollTop, { force: true });
  }
});

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

const toggleMapCooldownMode = () => {
  coolingOnly.value = !coolingOnly.value;
  nextTick(() => {
    const currentScrollTop = mapCooldownScrollRef.value?.scrollTop || mapCooldownLatestScrollTop;
    scheduleMapCooldownPrefixRebuild();
    clampMapCooldownScrollTop({ force: true });
    updateMapCooldownWindow(currentScrollTop, { force: true });
  });
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
    mapCooldownTotalHeight.value = nextPrefix[total];
};

const captureMapCooldownAnchor = () => {
    const scrollEl = mapCooldownScrollRef.value;
    const scrollTop = scrollEl ? scrollEl.scrollTop : mapCooldownLatestScrollTop;
    const rowHeight = getMapCooldownRowHeight();
    const startIndex = Math.floor(scrollTop / rowHeight);
    const offset = scrollTop - (startIndex * rowHeight);
    const keys = mapCooldownKeysAll.value;
    const key = keys[startIndex];
    return { key, offset, startIndex };
};

const applyMapCooldownAnchor = (anchor) => {
    if (!anchor || !anchor.key) return;
    const scrollEl = mapCooldownScrollRef.value;
    if (!scrollEl) return;
    
    // Find where the anchored key is now
    const keys = mapCooldownKeysAll.value; // Wait, we should use displayed rows keys
    // mapCooldownRows keys
    let anchorIndex = anchor.startIndex;
    
    // Check if index still points to same key
    if (mapCooldownRows.value[anchorIndex]?.key !== anchor.key) {
        // Linear scan nearby? or findIndex
        anchorIndex = mapCooldownRows.value.findIndex(r => r.key === anchor.key);
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
        
        // Adjust scroll position if needed (e.g. total height shrank)
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

  // Render Window Calculation
  // Overscan for smoother scrolling
  const overscanRows = mapCooldownIsFastScrolling.value ? 20 : 6;
  const scrollTopClamped = Math.max(0, Math.min(scrollTop, totalHeight - viewportHeight));
  
  // Calculate range
  const startRowFloat = scrollTopClamped / rowHeight;
  const baseStart = Math.floor(startRowFloat);
  
  // Visible count
  const visibleCount = Math.ceil(viewportHeight / rowHeight);
  
  // Apply overscan
  let start = Math.max(0, baseStart - overscanRows);
  let end = Math.min(total, baseStart + visibleCount + overscanRows);
  
  // Force even window size for stability? No, dynamic is fine.
  
  // If fast scrolling, maybe just render less detail or placeholder? 
  // We handle that in template with is-fast class.

  // Limit max rendered nodes
  const currentCount = end - start;
  const baseRows = visibleCount + (overscanRows * 2); 
  // If we try to render way too many, clamp it.
  // But usually scrollTop logic keeps it sane. 
  // However, if viewport is huge or rowHeight is small, we might have issues.
  
  // Dynamic overscan adjustment based on speed could be here.
  // const expansion = Math.floor(Math.min(50, (mapCooldownLastSpeed * 1.2)));
  const renderCount = Math.min(mapCooldownMaxRendered, Math.max(baseRows, baseRows + overscanRows * 2));
  
  // Re-center window around the viewport center to keep DOM balanced? 
  // Or just typical start/end. Typical is fine.
  
  // Ensure we don't exceed boundaries
  // Center window logic if we were clamping? 
  // Simple clamping:
  const anchorIndex = Math.floor((scrollTopClamped + viewportHeight / 2) / rowHeight);
  
  const maxStart = Math.max(0, total - renderCount);
  let startIndex = Math.min(Math.max(anchorIndex - Math.floor(renderCount / 2), 0), maxStart);
  let endIndex = Math.min(total, startIndex + renderCount);
  
  // Sanity check
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

const updateMapCooldownVisibleRows = () => {
    const total = mapCooldownRows.value.length;
    const rowHeight = getMapCooldownRowHeight();
    const totalHeight = mapCooldownTotalHeight.value;
    
    let start = mapCooldownWinStart.value;
    let end = mapCooldownWinEnd.value;
    
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


const onMapCooldownScroll = () => {
  scheduleMapCooldownRaf();
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
};

const resetMapCooldownFeedState = () => {
    mapCooldownRowsCooling.value = [];
    mapCooldownRowsAll.value = [];
    mapCooldownKeysAll.value = [];
    mapCooldownNeedsRebuild.value = true;
    mapCooldownWinStart.value = 0;
    mapCooldownWinEnd.value = 0;
    mapCooldownTopSpacerPx.value = 0;
    mapCooldownBottomSpacerPx.value = 0;
    mapCooldownVisibleRows.value = [];
    mapCooldownTotalHeight.value = 0;
};

const getMapCooldownAvailability = (row) => {
    return row.availability || 'unavailable';
};

const addMapCooldownFreshKeys = (keys) => {
    if (!keys || keys.length === 0) return;
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

watch(mapCooldownScrollRef, (scrollEl) => {
    if (!scrollEl || mapCooldownScrollInitDone) return;
    mapCooldownScrollInitDone = true;
    setupMapCooldownResizeObserver();
    setupMapCooldownContainerObserver();
    clampMapCooldownScrollTop({ force: true });
    updateMapCooldownWindow(scrollEl.scrollTop ?? 0, { force: true });
});

const ensureMapCooldownWorker = () => {
  if (mapCooldownWorker) return;
  mapCooldownWorker = new Worker(new URL('./workers/mapCooldown.worker.ts', import.meta.url), { type: 'module' });
  console.log('[mapcd] worker creating');
  
mapCooldownWorker.onmessage = (event) => {
    console.log('[mapcd] worker message', event.data?.type);
    const { type, payload } = event.data || {};
    if (type === 'PROGRESS') {
      if (!payload || payload.buildId !== mapCooldownBuildId) return;
      const done = Number(payload.done) || 0;
      const total = Number(payload.total) || 0;
      mapCooldownBuildProgress.value = { done, total };
      return;
    }
    if (type === 'RESULT') {
      if (!payload || payload.buildId !== mapCooldownBuildId) return;
      const rows = Array.isArray(payload.rows) ? payload.rows : [];
      const meta = payload.meta || {};
      if (payload.mode === 'showAll') {
        mapCooldownRowsAll.value = rows;
      } else if (payload.mode === 'coolingOnly') {
        mapCooldownRowsCooling.value = rows;
      }
      mapCooldownPendingModes.delete(payload.mode);
      mapCooldownBuildProgress.value = {
        done: Number(meta.totalRows) || rows.length,
        total: Number(meta.totalRows) || rows.length
      };
      if (mapCooldownPendingModes.size === 0) {
        mapCooldownIsBuilding.value = false;
        mapCooldownNeedsRebuild.value = false;
        mapCooldownKeysAll.value = mapCooldownRowsAll.value.map((row) => row.key);
        const rowHeight = Number(meta.rowHeight) || mapCooldownEstimatedRowHeight;
        mapCooldownLastNonZeroViewportHeight = rowHeight;
        nextTick(() => {
          scheduleMapCooldownPrefixRebuild();
          updateMapCooldownWindow(mapCooldownLatestScrollTop, { force: true });
          clampMapCooldownScrollTop({ force: true });
        });
      }
      return;
    }
    if (type === 'ERROR') {
      console.error('[mapcd worker]', payload?.message, payload?.stack);
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
  
  console.log('[mapcd] posting BUILD', { mode, locale: mapCooldownLocale.value, timeZone: mapCooldownTimeZone.value, nowEpochSec: mapCooldownNowEpoch.value, mapIndexKeys: Object.keys(mapIndexValue).length });
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
  if (!rebuildAll && !mapCooldownNeedsRebuild.value) return;
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

// [Map Sub Helper]
const hasMapIndexExgFields = (entry) => (
  entry && typeof entry === 'object' &&
  ['deadline', 'cooldown_end_epoch', 'duration_raw', 'duration_sec']
    .some((field) => Object.prototype.hasOwnProperty.call(entry, field))
);

const getExgStatus = (sub) => {
    if (!sub) return null;
    const mapKey = normalizeMapKey(sub.map || '');
    
    // Convert sub.comms (could be string[], or mixed) to pure string[]
    const comms = sub.comms || [];
    const commsNorm = Array.isArray(comms)
        ? comms
            .map((value) => {
                if (typeof value === 'string') return value;
                // If it's an object from select/option
                if (value && typeof value === 'object') {
                    return value.id ?? value.community_id ?? value.value ?? value.name ?? null;
                }
                return value !== null && value !== undefined ? String(value) : null;
            })
            .filter(Boolean)
        : [];
        
    const shouldShow = shouldShowExgStatus({ mapKey, comms: commsNorm, viewportWidth: viewportWidth.value });
    if (!shouldShow) return null;
    
    const entry = getMapIndexEntry(mapKey);
    if (!entry || !hasMapIndexExgFields(entry)) return null;

    const deadline = typeof entry.cooldown_end_epoch === 'number'
      ? entry.cooldown_end_epoch
      : (typeof entry.deadline === 'number' ? entry.deadline : null);
    const durationRaw = Object.prototype.hasOwnProperty.call(entry, 'duration_raw') ? entry.duration_raw ?? null : null;
    const durationSec = typeof entry.duration_sec === 'number' ? entry.duration_sec : null;

    if (
        (deadline === null || deadline === undefined) &&
        (durationRaw === null || durationRaw === undefined) &&
        (durationSec === null || durationSec === undefined)
    ) {
        return null;
    }

    const state = getExgStatusState(deadline, durationSec, undefined, durationRaw);
    if (state === 'hidden') return null;

    const type = state === 'cooldown' ? 'cooldown' : (state === 'available' ? 'available' : 'unavailable');
    const label = type === 'available' ? t('map_sub_exg_available') : (type === 'cooldown' ? t('map_sub_exg_cooldown') : t('unavailable'));
    const time = type === 'cooldown' && deadline ? formatExgCompactTime(formatExgDateTime(deadline)) : '';

    return { type, label, time, className: `exg-inline-status--${type}` };
};

const mapSubSearchQueryTrimmed = computed(() => subSearchQuery.value.trim());
const mapSubSelectedCount = computed(() => mapSubSelectedKeys.value.size);
const mapSubSubscribedRows = computed(() => mapSubResults.value.filter(row => subscribedMapKeys.value.has(row.key)));
const mapSubUnsubscribedRows = computed(() => mapSubResults.value.filter(row => !subscribedMapKeys.value.has(row.key)));
const mapSubPopoverSelectedCount = computed(() => mapSubPopoverSelected.value.size);
const mapSubPopoverTitle = computed(() => (mapSubPopoverMode.value === 'single' && mapSubPopoverRow.value) 
    ? mapSubPopoverRow.value.key 
    : t('map_sub_bulk_subscribe_title'));

const mapSubPopoverCommunities = computed(() => {
    const list = [{ id: 'all', name: t('all_comm'), short_name: t('all_comm') }];
    return list.concat(communities.value);
});

const getMapSubAvailabilityGroup = (status) => {
    if (!status) return 'none';
    if (status.type === 'available') return 'available';
    if (status.type === 'cooldown') return 'cooldown';
    return 'unavailable';
};

const refreshMapSubResults = () => {
    const query = mapSubSearchQueryTrimmed.value;
    if (!query) {
        mapSubResults.value = buildSubscribedRows();
        mapSubSearchTruncated.value = false;
        return;
    }

    const results = buildFullMapRows();
    mapSubResults.value = results;

    if (import.meta.env.DEV && !mapBehaviorDebugLogged) {
      const totalMatches = collectSortedMapMatches(mapSearchIndex.value, query).length;
      const visibleUnsubscribed = mapSubUnsubscribedRows.value.length;
      console.log('[map-search-check]', {
        mapSub: {
          query,
          totalMatches,
          visibleUnsubscribed,
          truncated: mapSubSearchTruncated.value
        },
        mapCd: {
          buildResultRowsAll: mapCooldownRowsAll.value.length,
          buildResultRowsCooling: mapCooldownRowsCooling.value.length,
          coolingOnly: coolingOnly.value,
          coolingVisible: mapCooldownRowsCooling.value.length,
          allVisible: mapCooldownRowsAll.value.length
        }
      });
      mapBehaviorDebugLogged = true;
    }
};

const buildSubscribedRows = () => {
    const rows = [];
    subscribedMapKeys.value.forEach((rawKey) => {
        const entry = getMapIndexEntry(rawKey);
        // Build minimal row
        const key = entry?.key || rawKey;
        // Re-find subscription data
        const sub = subscriptions.value.find(s => normalizeMapKey(s.map) === key);
        const comms = sub?.comms || [];
        
        // Match query (if any small filter applied? no, this fn is for empty query usually)
        // But if we want to filter subscribed list by query (local filter), we can.
        // Assuming this is "show all subscribed" when query is empty.
        
        const status = getExgStatus({ map: key, comms });
        
        // Score/Rank is irrelevant for default list, maybe sort by status?
        // Sort: Available -> Cooldown -> Others
        // Then by Name.
        
        // Mock match for sorting?
        const match = null;
        
        rows.push({
            key,
            displayName: isChineseLang.value ? getMapIndexDisplayName(key) : '',
            commsLabel: formatSubComms(comms),
            status,
            isSubscribed: subscribedMapKeys.value.has(rawKey),
            rank: match?.rank ?? 0,
            score: match?.score ?? 0,
            availabilityGroup: getMapSubAvailabilityGroup(status)
        });
    });
    
    rows.sort((a, b) => {
         if (a.availabilityGroup !== b.availabilityGroup) {
             return a.availabilityGroup === 'available' ? -1 : 1;
         }
         if (a.rank !== b.rank) return a.rank - b.rank;
         if (b.score !== a.score) return b.score - a.score;
         return a.key.localeCompare(b.key);
    });
    
    return rows;
};

const buildFullMapRows = () => {
    const query = mapSubSearchQueryTrimmed.value;
    if (!query) return [];

    const sortedMatches = collectSortedMapMatches(mapSearchIndex.value, query);
    const subByKey = new Map();
    subscriptions.value.forEach((sub) => {
      const key = normalizeMapKey(sub.map);
      if (key) subByKey.set(key, sub);
    });

    const subscribedRows = [];
    const unsubscribedRowsAll = [];

    sortedMatches.forEach((match) => {
      const key = match.key;
      if (!key) return;
      const isSubscribed = subscribedMapKeys.value.has(key);
      if (!isSubscribed && hiddenAfterUnsub.value.has(key)) return;

      const sub = subByKey.get(key);
      const comms = sub?.comms || [];
      const row = {
        key,
        displayName: isChineseLang.value ? getMapIndexDisplayName(key) : '',
        commsLabel: isSubscribed ? formatSubComms(comms) : '',
        status: isSubscribed ? getExgStatus({ map: key, comms }) : null,
        isSubscribed,
        rank: 0,
        score: match.score,
        availabilityGroup: isSubscribed ? getMapSubAvailabilityGroup(getExgStatus({ map: key, comms })) : 'none'
      };

      if (isSubscribed) subscribedRows.push(row);
      else unsubscribedRowsAll.push(row);
    });

    mapSubSearchTruncated.value = unsubscribedRowsAll.length > 50;
    const visibleUnsubscribedRows = unsubscribedRowsAll.slice(0, 50);
    return [...subscribedRows, ...visibleUnsubscribedRows];
};

const toggleMapSubMultiSelect = () => {
    mapSubMultiSelectMode.value = !mapSubMultiSelectMode.value;
    mapSubSelectedKeys.value = new Set();
    updateBulkToolbarPosition();
};

const onMapSubRowClick = (event, row) => {
    if (!mapSubMultiSelectMode.value) return;
    toggleSelected(row.key);
};

const isSelected = (key) => mapSubSelectedKeys.value.has(key);
const toggleSelected = (key) => {
    const next = new Set(mapSubSelectedKeys.value);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    mapSubSelectedKeys.value = next;
    updateBulkToolbarPosition();
};

const selectAllMapSub = () => {
    const next = new Set();
    mapSubUnsubscribedRows.value.forEach(row => next.add(row.key));
    mapSubSelectedKeys.value = next;
    updateBulkToolbarPosition();
};

const clearMapSubSelection = () => {
    mapSubSelectedKeys.value = new Set();
    updateBulkToolbarPosition();
};

const cancelMapSubMultiSelect = () => {
    mapSubMultiSelectMode.value = false;
    mapSubSelectedKeys.value = new Set();
    updateBulkToolbarPosition();
};

const handleMapSubSubscribe = (event, row) => {
    openMapSubPopover({ mode: 'single', row });
};

const handleMapSubUnsubscribe = (row) => {
    if (!row || !row.key) return;
    removeSubscriptionByKey(row.key);
};

const addSubscriptionByKey = (key, { silent = false, comms = ['all'] } = {}) => {
    const normalizedKey = normalizeMapKey(key);
    if (!normalizedKey) return;
    
    // Check duplication
    const existing = subscriptions.value.find(s => normalizeMapKey(s.map) === normalizedKey);
    if (existing) {
        existing.comms = comms; // Update comms
    } else {
        subscriptions.value.push({ map: normalizedKey, comms });
    }
    persistSubscriptions();
    
    // Update local state
    subscribedMapKeys.value.add(normalizedKey);
    if (hiddenAfterUnsub.value.has(normalizedKey)) {
        hiddenAfterUnsub.value.delete(normalizedKey);
    }
    
    if (embedMode) {
      postEmbedMessage('CS2ZE_SUBSCRIBE_MAP', { map: normalizedKey });
    }
    
    if (!silent) {
        showToast(formatTemplate(t('map_sub_toast_subscribed'), { map: normalizedKey }), 2000);
        refreshMapSubResults();
    }
};

const removeSubscriptionByKey = (key) => {
    const normalizedKey = normalizeMapKey(key);
    if (!normalizedKey) return;
    
    hiddenAfterUnsub.value.add(normalizedKey);
    
    if (subscribedMapKeys.value.has(normalizedKey)) {
        subscriptions.value = subscriptions.value.filter(sub => normalizeMapKey(sub.map) !== normalizedKey);
        const nextKeys = new Set(subscribedMapKeys.value);
        nextKeys.delete(normalizedKey);
        subscribedMapKeys.value = nextKeys;
        persistSubscriptions();
    }
    
    refreshMapSubResults();
    showToast(formatTemplate(t('map_sub_toast_unsubscribed'), { map: normalizedKey }), 2000);
};

const openMapSubPopover = ({ mode = 'single', row = null } = {}) => {
    mapSubPopoverMode.value = mode;
    mapSubPopoverRow.value = row;
    mapSubPopoverSelected.value = new Set();
    mapSubPopoverOpen.value = true;
};

const closeMapSubPopover = () => {
    mapSubPopoverOpen.value = false;
    mapSubPopoverSelected.value = new Set();
    mapSubPopoverRow.value = null;
};

const toggleMapSubPopoverCommunity = (commId) => {
    let next = new Set(mapSubPopoverSelected.value);
    if (commId === 'all') {
        if (next.has('all')) {
            next.delete('all');
        } else {
            next = new Set(['all']);
        }
    } else {
        if (next.has(commId)) next.delete(commId);
        else next.add(commId);
        next.delete('all');
    }
    mapSubPopoverSelected.value = next;
};

const confirmMapSubPopover = () => {
    const comms = Array.from(mapSubPopoverSelected.value);
    if (!comms.length) return;
    
    if (mapSubPopoverMode.value === 'bulk') {
        const keys = Array.from(mapSubSelectedKeys.value);
        if (!keys.length) {
            closeMapSubPopover();
            return;
        }
        keys.forEach((key) => addSubscriptionByKey(key, { silent: true, comms }));
        mapSubSelectedKeys.value = new Set();
        mapSubMultiSelectMode.value = false;
        refreshMapSubResults();
        showToast(t('map_sub_toast_bulk_subscribed'), 2000);
    } else {
        // Single
        if (mapSubPopoverRow.value) {
            addSubscriptionByKey(mapSubPopoverRow.value.key, { comms });
        }
    }
    closeMapSubPopover();
};

const persistSubscriptions = () => {
    localStorage.setItem('map_subs', JSON.stringify(subscriptions.value));
};

const openBulkSubscribePopover = (event) => {
    if (mapSubSelectedKeys.value.size === 0) return;
    openMapSubPopover({ mode: 'bulk' });
};

const removeSubscriptionByMap = (mapName) => {
  if (!mapName) return;
  removeSubscriptionByKey(mapName);
};

const isSubscribed = (mapName) => subscribedMapKeys.value.has(normalizeMapKey(mapName));

const formatSubComms = (comms) => {
  if (!Array.isArray(comms) || comms.length === 0) return '';
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
    new Notification(t('sub_notify'), { body: `[${cName}] Changed map to: ze_test_map\nTest Server`, icon: "/static/nerv_logo.png" });
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
  const base = {
    ...srv,
    online: Boolean(srv.name), // if name exists, assume queried successfully
    display_ip: srv.display_ip || (srv.ip + ':' + srv.port),
    players: srv.players || 0,
    max_players: srv.max_players || 64,
    map: srv.map || '',
    image_url: null
  };
  const mapKey = normalizeMapKey(base.map);
  if (mapKey && mapIndex.value[mapKey] && mapIndex.value[mapKey].image) {
    base.image_url = mapIndex.value[mapKey].image;
  }
  // Try fallback to workshop image if available (not implemented here, but structure allows)
  return base;
};

const checkSubscriptions = (srvData, commId) => {
  if (!srvData || !srvData.map || !subscriptions.value.length) return;
  
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
         const n = new Notification(t('sub_notify'), { body: `[${cName}] Changed map to: ${srvData.map}\n${srvData.name}`, icon: '/static/nerv_logo.png' });
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

const languageLabels = {
  'zh-CN': '简体中文',
  'zh-TW': '繁體中文',
  'en': 'English'
};

let serverRefreshTimer = null;
let statsRefreshTimer = null;
let serverRefreshEtag = null;
let serverRefreshInFlight = false;
let serverRefreshInitialized = false;

const parseConfigPayload = (payload) => {
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
    const parsed = parseConfigPayload(data);
    
    const defaultStrategy = normalizeJoinStrategy(parsed.join?.default_strategy) || 'rungameid';
    joinConfig.value = { ...parsed.join, default_strategy: defaultStrategy };

    try {
      const savedIds = JSON.parse(localStorage.getItem('comm_order'));
      if (Array.isArray(savedIds)) {
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
    
    // Normalize payload: it could be { cid: [servers] } or [ {cid...} ] (less likely for servers.json but consistent with struct)
    // Actually our servers.json usually returns { "comm_id": [ ... ] }
    if (Array.isArray(payload)) {
      // If it returns list of objects with cid?
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
      
      // Prune old
      Object.keys(cache).forEach((key) => {
        if (now - cache[key]._lastSeen > serverStaleMs) {
          delete cache[key];
        }
      });
      
      serverCache.value[cid] = cache;
      servers.value[cid] = Object.values(cache);
    });
  } catch (e) {
    // console.error(e);
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

const getServers = (cid) => {
  let list = servers.value[cid] || [];
  
  // Client-side search filtering
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
  try {
     await loadChartJs();
  } catch (e) {
    return;
  }
  
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
  
  // Only auto switch if not already there? No, user action controls view.
  // But we might want to update charts if view is stats.
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
    const textColor = isDark.value ? '#e0e0e0' : '#333';
    const gridColor = isDark.value ? '#444' : '#ddd';

    if (lineCtx) {
      if (lineChartInst) {
        lineChartInst.data = data.line_chart;
        lineChartInst.options.scales.x = { grid: { display: false } };
        lineChartInst.options.scales.y = { grid: { color: gridColor }, ticks: { color: textColor } };
        lineChartInst.update('none');
      } else {
        lineChartInst = new Chart(lineCtx, {
          type: 'line',
          data: data.line_chart,
          options: {
            maintainAspectRatio: false,
            scales: {
               x: { grid: { display: false } }
            }
          }
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

const allowedJoinStrategies = new Set([
  'rungameid', 'steam_connect', 'server_browser', 'clipboard_only'
]);

const normalizeJoinStrategy = (value) => {
  if (!value) return null;
  const normalized = String(value).trim().toLowerCase();
  return allowedJoinStrategies.has(normalized) ? normalized : null;
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
      } catch (err) { }
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
    } catch (err) { }
    document.body.removeChild(textArea);
  }
};

const joinServer = (target, comm) => {
  // Strategy Resolution
  // 1. Community specific override?
  // 2. Global config
  // 3. Default fallback
  
  let strategy = joinConfig.value.default_strategy;
  
  // Check comm override if exists (assuming structure supports it, e.g. join_strategy)
  if (comm && comm.join_strategy) {
     const commStrat = normalizeJoinStrategy(comm.join_strategy);
     if (commStrat) strategy = commStrat;
  }
  
  // Check target server game override (CSS vs CS2)
  // Logic: if game is CSS, maybe strategy changes? 
  // For now assume rungameid works for both if appid is correct.
  
  const address = getConnectAddress(target);
  
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
  
  // Default: rungameid
  if (embedMode) {
    const sent = postEmbedMessage('CS2ZE_JOIN', getJoinPayload(target));
    if (sent) return; // handled by parent
    
    // If not handled (e.g. iframe no parent support), fallback to copy
    copyText(`connect ${address}`, t('copy_console_done'));
    return;
  }
  
  // Standard web behavior
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
    const sent = postEmbedMessage('CS2ZE_COPY', { text: `connect ${address}`, kind: 'connect' });
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
  // Mock send
  feedbackSubject.value = '';
  feedbackMessage.value = '';
  showToast(t('feedback_sent'));
};
</script>

<style scoped>
/* ---------------------------------- Core Layout & Mobile Basics ---------------------------------- */
.content-wrapper {
  --page-center-max: 1100px;
  /* Safe area for notch/pill */
  padding-left: env(safe-area-inset-left);
  padding-right: env(safe-area-inset-right);
}

.map-sub-view {
  --sub-card-width: 980px;
  --sub-rail-w: 220px;
  --sub-rail-gap: 24px;
  position: relative;
}

/* Mobile Layout Override */
.is-mobile-layout {
  display: flex !important;
  flex-direction: column;
  height: 100vh !important;
  height: 100dvh !important; /* 适配移动端动态高度 */
  overflow: hidden !important;
  padding-bottom: 0 !important;
}

/* ADDED: Mobile Bottom Nav */
.mobile-bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  width: 100%;
  height: 60px;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
  border-top: 1px solid var(--card-border);
  display: flex;
  justify-content: space-around;
  align-items: center;
  z-index: 999;
  padding-bottom: env(safe-area-inset-bottom);
  transition: transform 0.3s ease;
}

.mobile-bottom-nav.nav-hidden {
  transform: translateY(100%);
}

.mob-nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: color 0.2s;
}

.mob-nav-item.active {
  color: var(--accent);
}

.mob-icon svg {
  width: 24px;
  height: 24px;
}

.mob-avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
}

.mob-label {
  font-size: 10px;
  font-weight: 500;
}

/* ---------------------------------- Small Laptop / Tablet Adapter ---------------------------------- */
@media screen and (min-width: 769px) and (max-width: 1366px) {
  /* Tighter Grid for Servers */
  .grid-container {
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 10px;
  }
  
  /* Sidebar is controlled by logic, but we can tighten nav items */
  .nav-item {
    padding: 0 10px;
  }
}

/* ---------------------------------- [修改点 3] MapCD 移动端样式重写 ---------------------------------- */
@media (max-width: 768px) {
  /* Hide Desktop Table Header */
  .mapcd-header {
    display: none !important;
  }

  /* Transform Row into a pseudo-row (stack) 移除了卡片背景，使其融入表格流 */
  .mapcd-row {
    display: grid !important;
    /* Grid Template: 
       [ Icon ] [ Map Name + Time ] [ Status ]
    */
    grid-template-columns: 1fr auto !important;
    grid-template-rows: auto auto;
    grid-template-areas: 
      "mapinfo status"
      "details status";
    gap: 4px 12px;
    
    height: auto !important; /* Allow dynamic height */
    min-height: 60px;
    padding: 12px 16px;
    margin: 0; /* 去除卡片样式，紧凑排列 */
    border-bottom: 1px solid var(--card-border);
    background: transparent !important; /* Ensure no card bg */
    align-items: center;
  }

  /* Map Name Area */
  .mapcd-cell.mapcd-col-map {
    grid-area: mapinfo;
    align-items: flex-start !important;
    justify-content: center;
    width: 100%;
    padding: 0;
  }
  
  .mapcd-map-key {
    font-size: 15px;
    font-weight: 600;
  }
  
  .mapcd-map-cn {
    font-size: 12px;
    opacity: 0.7;
    margin-top: 2px;
  }

  /* Details Row (Achievement + Length + Deadline) - Combine them via flex or something */
  /* Actually, let's just hide Achievement on mobile or put it small */
  .mapcd-cell.mapcd-col-ach {
    display: none !important; 
  }

  .mapcd-cell.mapcd-col-deadline,
  .mapcd-cell.mapcd-col-length {
    /* Combine these into the 'details' area if needed, or hide */
    /* Let's show Deadline in details area */
    grid-area: details;
    font-size: 12px;
    opacity: 0.6;
    align-items: flex-start !important;
    flex-direction: row;
    justify-content: flex-start;
    padding: 0;
  }
  
  /* Combine logic: We iterate cells. We can use CSS to show only one or merge visually? 
     Actually, the DOM structure is fixed. 
     We can make them display:inline-block within the grid area? No.
     
     Hack: Make col-length hidden, show col-deadline.
  */
  .mapcd-cell.mapcd-col-length {
    display: none !important;
  }

  /* Status Icon Area */
  .mapcd-cell.mapcd-col-availability {
    grid-area: status;
    width: auto;
    justify-content: center;
    padding: 0;
  }

  .mapcd-availability {
    width: 32px;
    height: 32px;
  }

  /* Search Bar Adjustment */
  .mapcd-search-area {
    margin-top: 10px !important;
    margin-bottom: 10px !important;
    padding: 0 16px;
  }
  
  .sub-search-box {
    height: 40px;
    font-size: 14px;
  }

  /* Header Slot (Title + Toggle) */
  .mapcd-header-slot {
    padding: 0 16px;
    margin: 10px 0;
  }
  
  .mapcd-title {
    font-size: 18px;
  }
  
  .mapcd-toggle-btn {
    height: 30px;
    font-size: 12px;
    padding: 0 10px;
  }

  /* Container Reset */
  .mapcd-container {
    border-radius: 0;
    border: none;
    border-top: 1px solid var(--card-border);
    box-shadow: none;
    background: transparent;
  }
  
  /* Remove Spacers logic interference? No, spacers are divs inside body. */
}

/* ---------------------------------- [新增] 批量操作工具栏样式 ---------------------------------- */
.sub-bulk-toolbar {
  position: fixed;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  background: var(--popover-solid-bg, #ffffff);
  border: 1px solid var(--card-border);
  box-shadow: 0 -4px 20px rgba(0,0,0,0.15);
  z-index: 2000;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  
  /* Safe area bottom handling */
  padding-bottom: calc(12px + env(safe-area-inset-bottom));
}

.sub-bulk-toolbar-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-right: auto;
}

.sub-bulk-tool-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 10px;
  color: var(--text-secondary);
  padding: 4px 8px;
  border-radius: 6px;
}

.sub-bulk-tool-btn:hover {
  background: rgba(128,128,128,0.1);
  color: var(--text-primary);
}

.sub-bulk-tool-btn--primary {
  color: var(--accent);
  background: rgba(var(--accent-rgb), 0.1);
}

.sub-bulk-tool-btn--primary:hover {
  background: rgba(var(--accent-rgb), 0.2);
}

.sub-bulk-tool-icon {
  width: 20px;
  height: 20px;
}

.sub-bulk-tool-icon svg {
  width: 100%;
  height: 100%;
}

/* Checkbox Style for Desktop/Mobile */
.fd-check {
  position: relative;
  display: inline-block;
  width: 24px;
  height: 24px;
  cursor: pointer;
}

.fd-check__input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}

.fd-check__box {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border: 2px solid var(--text-secondary); /* Unchecked border */
  border-radius: 6px;
  background: transparent;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Checked State */
.fd-check__input:checked + .fd-check__box {
  background: var(--accent);
  border-color: var(--accent);
}

/* Hover effect for unchecked */
.sub-row.is-selectable:hover .fd-check__box {
  border-color: var(--text-primary);
}

/* ---------------------------------- End New Styles ---------------------------------- */

/* Dark Mode Variables Adjustment if needed */
:root {
  --popover-solid-bg: #ffffff;
}

[data-theme="dark"] {
  --checkbox-shadow: rgba(0, 0, 0, 0.3);
  --checkbox-shadow-hover: rgba(0, 0, 0, 0.25);
  --popover-solid-bg: #2b2b2b;
}

/* Ensure dark mode vars are correct for mobile nav */
:global([data-theme="dark"]) .mobile-bottom-nav {
  background: rgba(30, 30, 30, 0.85);
}

.sub-search-box {
  width: 100%;
  max-width: 600px;
  height: 44px;
  padding: 0 18px;
  border-radius: 12px;
  border: 1px solid var(--card-border);
  background: var(--card-bg);
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
}

.sub-search-box:focus {
  border-color: color-mix(in srgb, var(--accent) 65%, transparent);
  box-shadow: 0 8px 18px rgba(0, 0, 0, 0.18);
}

.map-sub-view .sub-tags {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.map-sub-view .sub-search-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.map-sub-view .mapcd-search-area {
  margin-top: 58px;
  margin-bottom: 30px;
}

.map-sub-view .sub-search-hint {
  margin-top: 10px;
  font-size: 12px;
  color: var(--text-secondary);
}

.map-sub-view .sub-map-key-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sub-popover-backdrop {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(2px);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sub-popover-panel {
  position: relative;
  width: min(820px, calc(100vw - 48px));
  max-height: calc(100vh - 96px);
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 18px;
  border-radius: 18px;
  background: var(--popover-solid-bg, #ffffff);
  opacity: 1;
  border: 1px solid var(--card-border);
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
  z-index: 10000;
}

.sub-popover-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.sub-popover-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}

.sub-popover-hint {
  margin-left: auto;
  font-size: 12px;
  color: var(--status-offline);
  transition: opacity 0.15s ease;
}

.sub-popover-hint.is-hidden {
  opacity: 0;
  visibility: hidden;
}

.sub-popover-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  overflow: auto;
  padding-right: 4px;
}

.sub-popover-chip {
  border-radius: 9px;
  border: 1px solid var(--card-border);
  background: var(--card-bg);
  padding: 6px 14px;
  font-size: 13px;
  cursor: pointer;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.15s ease;
}

.sub-popover-chip:hover {
  background: rgba(128, 128, 128, 0.08);
}

.sub-popover-chip.is-selected {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}

.sub-popover-chip-icon {
  width: 14px;
  height: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sub-popover-footer {
  margin-top: 4px;
  display: flex;
  align-items: center;
}

.sub-popover-count {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
}

.sub-popover-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 8px;
}

.sub-popover-btn {
  height: 36px;
  padding: 0 16px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border: none;
  transition: transform 0.1s;
}

.sub-popover-btn:active {
  transform: scale(0.97);
}

.sub-popover-btn--cancel {
  background: transparent;
  color: var(--text-secondary);
}

.sub-popover-btn--cancel:hover {
  background: rgba(128, 128, 128, 0.1);
  color: var(--text-primary);
}

.sub-popover-btn--confirm {
  background: var(--accent);
  color: #fff;
}

.sub-popover-btn--confirm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Status Colors */
.map-sub-view .exg-inline-status {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.2;
}

.map-sub-view .exg-icon {
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

.map-sub-view .exg-pill.is-online {
  color: var(--status-online, #107c10);
}

.map-sub-view .exg-pill.is-offline {
  color: var(--status-offline, #0078d4);
}


.map-sub-view .sub-unsubscribed-shell {
  margin: 28px auto 0;
  width: 100%;
  max-width: var(--sub-card-width);
}

.map-sub-view .sub-unsubscribed-card {
  min-width: 0;
  width: 100%;
}

.map-sub-view .sub-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.map-sub-view .sub-card-title {
  font-size: 15px;
  font-weight: 600;
  opacity: 0.85;
  margin: 0;
}

.map-sub-view .sub-bulk-entry {
  display: flex;
  align-items: center;
  gap: 6px;
  background: transparent;
  border: 1px solid var(--card-border);
  color: var(--text-primary);
  font-size: 12px;
  font-weight: 600;
  height: 30px;
  padding: 0 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.map-sub-view .sub-bulk-entry:hover {
  background: rgba(128,128,128,0.05);
}

.map-sub-view .sub-bulk-entry-icon {
  width: 16px;
  height: 16px;
}

.map-sub-view .sub-bulk-entry-icon svg {
  width: 100%;
  height: 100%;
}


/* Re-use existing server-search-bar styles or card styles for consistency? */
@media (max-width: 768px) {
  .sub-container {
    padding: 0 16px;
    max-width: 100%;
  }
}

.sub-container {
  width: 100%;
  max-width: var(--sub-card-width);
  margin: 0 auto;
  padding: 0 16px;
}

.sub-card-surface {
  max-width: var(--sub-card-width);
  width: 100%;
  margin: 0 auto;
  min-width: 0;
}

.mapcd-page {
  --mapcd-surface-bg: var(--card-bg);
  --mapcd-surface-border: var(--card-border);
  --mapcd-surface-radius: 14px;
  --mapcd-card-max: var(--page-center-max);
  
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 0 0 16px;
  height: 100%;
  min-height: 0;
}

.mapcd-view {
  width: 100%;
  max-width: var(--mapcd-card-max);
  margin: 0 auto;
  padding: 0 16px;
  display: flex;
  flex-direction: column;
  gap: 0;
  flex: 1;
  min-height: 0;
}

.mapcd-view .mapcd-search-area {
  margin-top: 58px;
  margin-bottom: 30px;
}

.mapcd-view .mapcd-divider {
  height: 1px;
  background: var(--card-border);
  margin: 0;
}

.mapcd-view .mapcd-header-slot {
  margin: 16px 0 12px;
  padding: 0;
}

.mapcd-view .mapcd-hint {
  margin: 6px 0 10px;
  opacity: 0.85;
  text-align: center;
}

.mapcd-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.mapcd-title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  opacity: 0.9;
  display: flex;
  align-items: baseline;
  gap: 8px;
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
  border: 1px solid color-mix(in srgb, var(--mapcd-surface-border) 60%, transparent 40%);
  transition: all 0.2s ease;
}

.mapcd-search:focus-within {
  background: var(--mapcd-surface-bg);
  border-color: var(--accent);
  box-shadow: 0 0 0 2px rgba(var(--accent-rgb), 0.2);
}

.mapcd-search-input {
  flex: 1;
  background: transparent;
  border: none;
  font-size: 14px;
  color: var(--text-primary);
  outline: none;
  height: 100%;
}

.mapcd-container-wrapper {
  flex: 1;
  min-height: 0;
  width: 100%;
  max-width: var(--mapcd-card-max);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.mapcd-container {
  margin-top: 0 !important;
  padding: 0;
  background: var(--mapcd-surface-bg);
  border: 1px solid color-mix(in srgb, var(--mapcd-surface-border) 60%, transparent 40%);
  border-radius: var(--mapcd-surface-radius);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
  overflow: hidden;
  flex: 1;
  min-height: 0;
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
  font-weight: 400;
  opacity: 0.6;
}

.mapcd-table {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.mapcd-header {
  display: grid;
  grid-template-columns: 2fr 1.2fr 1.2fr 1.2fr 80px;
  padding: 0 16px;
  background: color-mix(in srgb, var(--mapcd-surface-bg) 96%, #000 4%);
  border-bottom: 1px solid color-mix(in srgb, var(--mapcd-surface-border) 50%, transparent 50%);
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  height: 40px;
  align-items: center;
  user-select: none;
}

.mapcd-body {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  position: relative;
  /* Custom scrollbar matching app theme if desired, else native */
}

.mapcd-row {
  display: grid;
  grid-template-columns: 2fr 1.2fr 1.2fr 1.2fr 80px;
  padding: 0 16px;
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
  background: rgba(var(--accent-rgb), 0.12);
}

.mapcd-row:last-child {
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

.mapcd-col-map, .mapcd-col-ach {
  align-items: flex-start;
  justify-content: center;
}

.mapcd-col-ach, .mapcd-col-length {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mapcd-row .mapcd-col-deadline, 
.mapcd-row .mapcd-col-length,
.mapcd-row .mapcd-col-ach {
  opacity: 0.9;
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
  background: rgba(128, 128, 128, 0.1);
}

.mapcd-availability.is-available {
  background: rgba(var(--status-online-rgb, 16, 124, 16), 0.15);
  color: var(--status-online);
}

.mapcd-availability.is-cooldown {
  background: rgba(var(--status-offline-rgb, 200, 0, 0), 0.1);
  color: var(--status-offline);
}

.mapcd-availability-icon svg {
  width: 18px;
  height: 18px;
}

.mapcd-empty {
  padding: 40px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 14px;
}

/* Edge Fades */
.mapcd-edge-fade {
  position: absolute;
  left: 0;
  right: 0;
  height: 24px;
  pointer-events: none;
  z-index: 2;
  opacity: 0;
  transition: opacity 0.3s;
}

.mapcd-edge-fade--top {
  top: 0;
  background: linear-gradient(to bottom, var(--mapcd-surface-bg), transparent);
}

.mapcd-edge-fade--bottom {
  bottom: 0;
  background: linear-gradient(to top, var(--mapcd-surface-bg), transparent);
}

.mapcd-view .mapcd-header .sortable {
  cursor: pointer;
  transition: color 0.2s;
}

.mapcd-view .mapcd-header .sortable:hover {
  color: var(--text-primary);
}

.mapcd-view .mapcd-header .sort-tri {
  display: inline-block;
  font-size: 8px;
  margin-left: 4px;
  opacity: 0;
  transition: opacity 0.2s, transform 0.2s;
}

.mapcd-view .mapcd-header .sortable.active,
.mapcd-view .mapcd-header .sortable.active .sort-tri {
  opacity: 1;
  color: var(--accent);
}

.mapcd-hint.mapcd-sort-hint {
  font-size: 12px; 
  color: var(--accent);
}
</style>
