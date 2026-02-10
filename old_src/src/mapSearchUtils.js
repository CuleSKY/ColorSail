import * as OpenCC from 'opencc-js';
import { pinyin } from 'pinyin-pro';

export const createOpenCCConverter = () => {
  try {
    return OpenCC.Converter({ from: 'cn', to: 'tw' });
  } catch (e) {
    return null;
  }
};

export const stripBracketSegments = (value) => (value || '').toString().replace(/\[[^\]]*]/g, '').trim();
export const normalizeSearchText = (value) => (value || '').toString().toLowerCase().replace(/\s+/g, '');

const ZH_VARIANT_PAIRS = [
  ['图', '圖'],
  ['显', '顯'],
  ['却', '卻'],
  ['乐', '樂'],
  ['发', '發'],
  ['无', '無'],
  ['龙', '龍'],
  ['圣', '聖'],
  ['战', '戰'],
  ['终', '終'],
  ['爱', '愛'],
  ['梦', '夢'],
  ['炉', '爐'],
  ['魔', '魔'],
  ['光', '光'],
  ['败', '敗'],
  ['风', '風'],
  ['云', '雲'],
  ['书', '書'],
  ['车', '車'],
  ['门', '門'],
  ['国', '國'],
  ['岛', '島'],
  ['剑', '劍'],
  ['进', '進'],
  ['觉', '覺'],
  ['体', '體'],
  ['击', '擊'],
  ['队', '隊'],
  ['续', '續'],
  ['绝', '絕']
];

const ZH_VARIANT_MAP = ZH_VARIANT_PAIRS.reduce((acc, [simp, trad]) => {
  acc[simp] = simp;
  acc[trad] = simp;
  return acc;
}, {});

export const normalizeZh = (value) => {
  const base = (value || '').toString().toLowerCase().trim().replace(/\s+/g, ' ');
  if (!base) return '';
  return Array.from(base).map((char) => ZH_VARIANT_MAP[char] ?? char).join('');
};

const normalizeTokenText = (value) => (value || '').toString().toLowerCase().trim();
const splitTokens = (value) => normalizeTokenText(value).split(/[\s_-]+/).filter(Boolean);

const buildPinyinIndex = (text) => {
  const cleaned = stripBracketSegments(text);
  if (!cleaned) return { full: '', initials: '' };
  try {
    const full = pinyin(cleaned, { toneType: 'none', type: 'array' }).join('');
    const initials = pinyin(cleaned, { pattern: 'first', toneType: 'none', type: 'array' }).join('');
    return { full, initials };
  } catch (e) {
    return { full: '', initials: '' };
  }
};

const buildNgrams = (value, size = 2) => {
  if (!value || value.length < size) return [];
  const grams = [];
  for (let i = 0; i <= value.length - size; i += 1) {
    grams.push(value.slice(i, i + size));
  }
  return grams;
};

const countNgramMatches = (query, target) => {
  if (!query || !target) return 0;
  const grams = buildNgrams(query, 2);
  if (grams.length === 0) return 0;
  return grams.reduce((acc, gram) => acc + (target.includes(gram) ? 1 : 0), 0);
};

export const buildMapSearchIndex = (mapIndex, converter) => {
  const entries = [];
  if (!mapIndex || typeof mapIndex !== 'object') return entries;
  Object.entries(mapIndex).forEach(([key, value]) => {
    const entry = value && typeof value === 'object' ? value : {};
    const mapCnRaw = typeof entry.map_cn === 'string' ? entry.map_cn : '';
    const mapCn = stripBracketSegments(mapCnRaw);
    const mapTw = converter ? converter(mapCn) : mapCn;
    const aliases = Array.isArray(entry.aliases) ? entry.aliases.filter(Boolean) : [];
    const achievement = typeof entry.achievement === 'string' ? entry.achievement : '';
    const normalizedAliases = aliases.map(normalizeSearchText).filter(Boolean);
    const tokens = [...splitTokens(key), ...aliases.flatMap(splitTokens)];
    const pinyinIndex = buildPinyinIndex(mapCn);
    const deadline = entry.cooldown_end_epoch ?? entry.deadline ?? null;
    const durationRaw = entry.duration_raw ?? null;
    const durationSec = entry.duration_sec ?? null;
    entries.push({
      key,
      mapCn,
      mapTw,
      aliases,
      achievement,
      deadline,
      durationRaw,
      durationSec,
      normalized: {
        key: normalizeSearchText(key),
        mapCn: normalizeSearchText(mapCn),
        mapTw: normalizeSearchText(mapTw),
        aliases: normalizedAliases,
        achievement: normalizeSearchText(achievement)
      },
      tokens,
      pinyin: pinyinIndex
    });
  });
  return entries;
};

export const scoreSearchEntry = (entry, query) => {
  if (!entry || !query) return 0;
  const rawQuery = query.toString();
  const normalizedQuery = normalizeSearchText(rawQuery);
  if (!normalizedQuery) return 0;

  const hasCjk = /[\u4e00-\u9fff]/.test(rawQuery);
  const queryTokens = splitTokens(rawQuery);
  const isAlphaQuery = /^[a-z0-9]+$/i.test(normalizedQuery);
  let score = 0;

  if (entry.normalized.key.includes(normalizedQuery)) score += 200;
  if (entry.normalized.aliases.some(alias => alias.includes(normalizedQuery))) score += 160;
  if (entry.normalized.achievement && entry.normalized.achievement.includes(normalizedQuery)) score += 40;

  if (queryTokens.length > 0 && entry.tokens.length > 0) {
    const tokenMatches = queryTokens.filter(token => entry.tokens.some(t => t.startsWith(token)));
    if (tokenMatches.length === queryTokens.length) score += 120;
    else if (tokenMatches.length > 0) score += 60;
  }

  if (hasCjk) {
    const cnHit = entry.normalized.mapCn.includes(normalizedQuery);
    const twHit = entry.normalized.mapTw.includes(normalizedQuery);
    if (cnHit || twHit) score += 180;
    const cnGram = countNgramMatches(normalizedQuery, entry.normalized.mapCn);
    const twGram = countNgramMatches(normalizedQuery, entry.normalized.mapTw);
    const gramHits = Math.max(cnGram, twGram);
    if (gramHits > 0) score += 80 + gramHits;
  }

  if (!hasCjk && isAlphaQuery) {
    const pinyinFull = entry.pinyin.full || '';
    const pinyinInitials = entry.pinyin.initials || '';
    if (pinyinFull) {
      if (pinyinFull.startsWith(normalizedQuery)) score += 140;
      else if (pinyinFull.includes(normalizedQuery)) score += 100;
    }
    if (pinyinInitials) {
      if (pinyinInitials.startsWith(normalizedQuery)) score += 120;
      else if (pinyinInitials.includes(normalizedQuery)) score += 80;
    }
  }

  return score;
};

export const getExgStatusState = (
  deadline,
  durationSec,
  nowSec = Math.floor(Date.now() / 1000),
  durationRaw = null
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
  if (durationRaw !== null && durationRaw !== undefined && durationRaw !== '0分') return 'available';
  if (durationSec === 0) return 'not_available';
  if (typeof durationSec === 'number' && durationSec > 0) return 'available';
  return 'hidden';
};

export const formatExgDate = (timestampSec) => {
  const date = new Date(timestampSec * 1000);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}/${month}/${day}`;
};

export const formatExgDateTime = (timestampSec) => {
  const date = new Date(timestampSec * 1000);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  const seconds = String(date.getSeconds()).padStart(2, '0');
  return `${year}/${month}/${day} - ${hours}:${minutes}:${seconds}`;
};

export const formatLocalDateTime = (timestampSec) => {
  const date = new Date(timestampSec * 1000);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  const seconds = String(date.getSeconds()).padStart(2, '0');
  return `${year}/${month}/${day} ${hours}:${minutes}:${seconds}`;
};

export const validateMapIndexEntry = (mapKey, entry, warn = console.warn) => {
  if (!entry || typeof entry !== 'object') {
    warn?.(`[map_index] invalid entry for ${mapKey}: not an object`);
    return;
  }
  if (typeof entry.map_cn !== 'string') {
    warn?.(`[map_index] missing map_cn for ${mapKey}`);
  }
  if (entry.aliases !== undefined && !Array.isArray(entry.aliases)) {
    warn?.(`[map_index] aliases should be array for ${mapKey}`);
  }
  if (entry.deadline !== undefined && entry.deadline !== null && typeof entry.deadline !== 'number') {
    warn?.(`[map_index] deadline should be number|null for ${mapKey}`);
  }
  if (
    entry.cooldown_end_epoch !== undefined
    && entry.cooldown_end_epoch !== null
    && typeof entry.cooldown_end_epoch !== 'number'
  ) {
    warn?.(`[map_index] cooldown_end_epoch should be number|null for ${mapKey}`);
  }
  if (entry.duration_raw !== undefined && entry.duration_raw !== null && typeof entry.duration_raw !== 'string') {
    warn?.(`[map_index] duration_raw should be string|null for ${mapKey}`);
  }
  if (entry.duration_sec !== undefined && entry.duration_sec !== null && typeof entry.duration_sec !== 'number') {
    warn?.(`[map_index] duration_sec should be number|null for ${mapKey}`);
  }
};

export const shouldShowExgStatus = ({ mapKey, comms, viewportWidth }) => {
  if (!mapKey) return false;
  if (typeof viewportWidth === 'number' && viewportWidth < 768) return false;
  if (!Array.isArray(comms)) return false;
  return comms.includes('all') || comms.some((cid) => cid.toString().toLowerCase() === 'exg');
};
