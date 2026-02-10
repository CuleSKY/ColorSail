// mapCooldown.worker.ts

// [核心修复] 移除所有外部依赖导入，防止 Worker 启动崩溃
// import { createOpenCCConverter, getExgStatusState, stripBracketSegments } from '../mapSearchUtils.js';

// --- 内联辅助函数 (从 mapSearchUtils.js 复制并精简) ---

const stripBracketSegments = (value: any) => {
  return (value || '').toString().replace(/\[[^\]]*]/g, '').trim();
};

const normalizeSearchText = (value: any) => {
  return (value || '').toString().toLowerCase().replace(/\s+/g, '');
};

const getExgStatusState = (
  deadline: any,
  durationSec: any,
  nowSec: number,
  durationRaw: any
) => {
  if (deadline !== null && deadline !== undefined) return 'cooldown';
  
  if (deadline === null || deadline === undefined) {
    if (durationRaw === '0分') return 'not_available';
    if (durationRaw !== null && durationRaw !== undefined && durationRaw !== '0分') return 'available';
    if (durationSec === 0) return 'not_available';
    if (typeof durationSec === 'number' && durationSec > 0) return 'available';
    return 'hidden';
  }
  
  if (durationRaw === '0分') return 'not_available';
  return 'available';
};

// --- 业务逻辑 ---

const formatDurationHuman = (seconds: number | null, locale: string) => {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return '-';
  const total = Math.max(0, Math.floor(seconds));
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  const isZh = (locale || '').startsWith('zh');
  const parts: string[] = [];
  if (days) parts.push(isZh ? `${days}天` : `${days}d`);
  if (hours) parts.push(isZh ? `${hours}小时` : `${hours}h`);
  if (minutes) parts.push(isZh ? `${minutes}分` : `${minutes}m`);
  if (total < 60 || parts.length === 0) parts.push(isZh ? `${secs}秒` : `${secs}s`);
  return isZh ? parts.join('') : parts.join(' ');
};

const formatDeadline = (epochSec: number | null, formatter: Intl.DateTimeFormat) => {
  if (!epochSec) return '-';
  return formatter.format(new Date(epochSec * 1000));
};

const toAvailability = (
  deadline: number | null,
  durationSec: number | null,
  nowEpochSec: number,
  durationRaw: string | null
) => {
  const state = getExgStatusState(deadline, durationSec, nowEpochSec, durationRaw);
  if (state === 'cooldown') return 'cooling';
  if (state === 'available') return 'available';
  return 'unavailable';
};

const buildRows = (payload: any, buildId?: number) => {
  const {
    mapIndex = {},
    nowEpochSec,
    locale = 'en-US',
    timeZone,
    prefixes = [],
    availabilityLabels = { available: '', unavailable: '' }
  } = payload || {};

  const formatter = new Intl.DateTimeFormat(locale, {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  });

  const entries = Object.entries(mapIndex);
  const total = entries.length;
  const rows: any[] = [];
  const chunkSize = 500;
  let done = 0;

  const shouldInclude = (key: string) => prefixes.length === 0 || prefixes.some((prefix: string) => key.startsWith(prefix));
  
  const resolveMapLine2 = (key: string, entry: any) => {
    if (!locale.startsWith('zh')) return '';
    const raw = typeof entry?.map_cn === 'string' ? entry.map_cn : '';
    const cleaned = stripBracketSegments(raw);
    if (!cleaned) return '';
    
    // [注意] Worker 中为了稳定性移除了 OpenCC。
    // 如果必须要在繁体环境下显示繁体，建议在主线程转换好再传进来，或者直接回退到简体显示。
    // 这里直接返回清洗后的文本，确保不崩。
    return cleaned; 
  };

  for (let i = 0; i < entries.length; i += chunkSize) {
    const chunk = entries.slice(i, i + chunkSize);
    chunk.forEach(([key, entry]) => {
      if (!shouldInclude(key)) return;
      const data = entry && typeof entry === 'object' ? entry : {};
      const deadline = typeof data.cooldown_end_epoch === 'number'
        ? data.cooldown_end_epoch
        : (typeof data.deadline === 'number' ? data.deadline : null);
      const durationSec = typeof data.duration_sec === 'number' ? data.duration_sec : null;
      const durationRaw = Object.prototype.hasOwnProperty.call(data, 'duration_raw')
        ? data.duration_raw ?? null
        : null;
      
      const hasExgFields = deadline !== null || durationSec !== null || durationRaw !== null;
      const availability = hasExgFields
        ? toAvailability(deadline, durationSec, nowEpochSec, durationRaw)
        : 'unavailable';
      const sortGroup = availability === 'cooling' ? 0 : availability === 'available' ? 1 : 2;
      
      const deadlineText = hasExgFields ? formatDeadline(deadline, formatter) : '-';
      const durationText = hasExgFields ? formatDurationHuman(durationSec, locale) : '-';
      
      const mapCnRaw = stripBracketSegments(typeof data?.map_cn === 'string' ? data.map_cn : '');
      const mapLine2 = resolveMapLine2(key, data);
      const achievement = typeof data.achievement === 'string' ? data.achievement : '';
      const aliases = Array.isArray(data.aliases) ? data.aliases.filter((alias: any) => typeof alias === 'string') : [];
      
      // 构建搜索文本
      const searchTextRaw = `${key}\n${mapCnRaw}\n${mapLine2}\n${achievement}\n${aliases.join(' ')}`.trim();
      const searchTextNorm = normalizeSearchText(searchTextRaw);
      
      rows.push({
        key,
        mapLine1: key,
        mapLine2,
        achievement,
        deadlineEpochSec: deadline,
        deadlineText,
        durationSec,
        durationText,
        availability,
        availabilityTitle: availability === 'available' ? availabilityLabels.available : availabilityLabels.unavailable,
        sortGroup,
        searchTextNorm
      });
    });
    
    done = Math.min(total, i + chunk.length);
    // 进度消息
    if (done < total) {
      self.postMessage({ 
        type: 'BUILD_RESULT', 
        payload: { 
          buildId, 
          progress: { done, total } 
        } 
      });
    }
  }

  // 排序逻辑
  rows.sort((a, b) => {
    const groupDiff = a.sortGroup - b.sortGroup;
    if (groupDiff !== 0) return groupDiff;
    return a.key.localeCompare(b.key);
  });

  // 冷却中单独列表
  const coolingRows = rows
    .filter((row) => row.deadlineEpochSec !== null && row.deadlineEpochSec > nowEpochSec)
    .slice()
    .sort((a, b) => {
      if (a.deadlineEpochSec === null && b.deadlineEpochSec === null) return a.key.localeCompare(b.key);
      if (a.deadlineEpochSec === null) return 1;
      if (b.deadlineEpochSec === null) return -1;
      const diff = a.deadlineEpochSec - b.deadlineEpochSec;
      if (diff !== 0) return diff;
      return a.key.localeCompare(b.key);
    });

  return { rows, coolingRows };
};

// 消息监听
self.onmessage = (event: MessageEvent) => {
  const { data } = event || {};
  if (!data || data.type !== 'BUILD') return;
  const buildId = data.payload?.buildId;
  
  try {
    const { rows, coolingRows } = buildRows(data.payload, buildId);
    
    self.postMessage({
      type: 'BUILD_RESULT',
      payload: {
        buildId,
        rowsAll: rows,
        rowsCooling: coolingRows,
        done: true,
        progress: { done: rows.length, total: rows.length }
      }
    });
    
  } catch (error: any) {
    self.postMessage({
      type: 'ERROR',
      payload: { message: error?.message || 'Worker error', stack: error?.stack, buildId }
    });
  }
};