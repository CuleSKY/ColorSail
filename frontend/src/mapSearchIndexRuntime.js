import { normalizeSearchText, stripBracketSegments } from './mapSearchCore.js';

const normalizeTokenText = (value) => (value || '').toString().toLowerCase().trim();
const splitTokens = (value) => normalizeTokenText(value).split(/[\s_-]+/).filter(Boolean);

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

const normalizePinyin = (value) => (value || '').toString().toLowerCase().replace(/\s+/g, '');

export const buildMapSearchIndex = (mapIndex, _converter = null) => {
  const entries = [];
  if (!mapIndex || typeof mapIndex !== 'object') return entries;

  Object.entries(mapIndex).forEach(([key, value]) => {
    const entry = value && typeof value === 'object' ? value : {};
    const mapCnRaw = typeof entry.map_cn === 'string' ? entry.map_cn : '';
    const mapCn = stripBracketSegments(mapCnRaw);
    const mapTwRaw = typeof entry.map_tw === 'string' ? entry.map_tw : '';
    const mapTw = stripBracketSegments(mapTwRaw) || mapCn;
    const aliases = Array.isArray(entry.aliases) ? entry.aliases.filter(Boolean) : [];
    const achievement = typeof entry.achievement === 'string' ? entry.achievement : '';
    const normalizedAliases = aliases.map(normalizeSearchText).filter(Boolean);
    const tokens = [...splitTokens(key), ...aliases.flatMap(splitTokens)];
    const deadline = entry.cooldown_end_epoch ?? entry.deadline ?? null;
    const durationRaw = entry.duration_raw ?? null;
    const durationSec = entry.duration_sec ?? null;
    const pinyinFull = normalizePinyin(entry.pinyin_full);
    const pinyinInitials = normalizePinyin(entry.pinyin_initials);

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
      pinyin: {
        full: pinyinFull,
        initials: pinyinInitials
      }
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
  if (entry.normalized.aliases.some((alias) => alias.includes(normalizedQuery))) score += 160;
  if (entry.normalized.achievement && entry.normalized.achievement.includes(normalizedQuery)) score += 40;

  if (queryTokens.length > 0 && entry.tokens.length > 0) {
    const tokenMatches = queryTokens.filter((token) => entry.tokens.some((t) => t.startsWith(token)));
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
