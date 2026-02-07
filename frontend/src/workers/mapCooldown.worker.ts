import { createOpenCCConverter, getExgStatusState, stripBracketSegments } from '../mapSearchUtils.js';

const converter = createOpenCCConverter();

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

const toAvailability = (deadline: number | null, durationSec: number | null, nowEpochSec: number) => {
  const state = getExgStatusState(deadline, durationSec, nowEpochSec);
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
    if (locale === 'zh-TW') return converter ? converter(cleaned) : cleaned;
    return cleaned;
  };

  for (let i = 0; i < entries.length; i += chunkSize) {
    const chunk = entries.slice(i, i + chunkSize);
    chunk.forEach(([key, entry]) => {
      if (!shouldInclude(key)) return;
      const data = entry && typeof entry === 'object' ? entry : {};
      const deadline = typeof data.deadline === 'number' ? data.deadline : null;
      const durationSec = typeof data.duration_sec === 'number' ? data.duration_sec : null;
      const availability = toAvailability(deadline, durationSec, nowEpochSec);
      const sortGroup = availability === 'cooling' ? 0 : availability === 'available' ? 1 : 2;
      rows.push({
        key,
        mapLine1: key,
        mapLine2: resolveMapLine2(key, data),
        achievement: typeof data.achievement === 'string' ? data.achievement : '',
        deadlineEpochSec: deadline,
        deadlineText: formatDeadline(deadline, formatter),
        durationSec,
        durationText: formatDurationHuman(durationSec, locale),
        availability,
        availabilityTitle: availability === 'available' ? availabilityLabels.available : availabilityLabels.unavailable,
        sortGroup
      });
    });
    done = Math.min(total, i + chunk.length);
    if (done < total) {
      self.postMessage({ type: 'PROGRESS', payload: { done, total, buildId } });
    }
  }

  rows.sort((a, b) => {
    const groupDiff = a.sortGroup - b.sortGroup;
    if (groupDiff !== 0) return groupDiff;
    return a.key.localeCompare(b.key);
  });

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

self.onmessage = (event: MessageEvent) => {
  const { data } = event || {};
  if (!data || data.type !== 'BUILD') return;
  const buildId = data.payload?.buildId;
  try {
    const { rows, coolingRows } = buildRows(data.payload, buildId);
    self.postMessage({ type: 'RESULT', payload: { mode: 'showAll', rows, buildId } });
    self.postMessage({ type: 'RESULT', payload: { mode: 'coolingOnly', rows: coolingRows, buildId } });
  } catch (error: any) {
    self.postMessage({
      type: 'ERROR',
      payload: { message: error?.message || 'Worker error', stack: error?.stack, buildId }
    });
  }
};
