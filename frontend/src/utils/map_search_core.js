import { normalizeSearchText, scoreSearchEntry } from '../mapSearchUtils';

export const normalizeMapSearchQuery = (query) => normalizeSearchText(query || '');

export const matchMapSearchEntry = (entry, query) => {
  if (!entry) return null;
  const normalizedQuery = normalizeMapSearchQuery(query);
  if (!normalizedQuery) return null;
  const score = scoreSearchEntry(entry, normalizedQuery);
  if (score <= 0) return null;
  return { key: entry.key, score };
};

export const sortMapSearchMatches = (a, b) => (b.score - a.score) || a.key.localeCompare(b.key);

export const collectSortedMapMatches = (entries, query) => {
  const normalizedQuery = normalizeMapSearchQuery(query);
  if (!normalizedQuery) return [];
  const matches = [];
  entries.forEach((entry) => {
    const match = matchMapSearchEntry(entry, normalizedQuery);
    if (match) matches.push(match);
  });
  matches.sort(sortMapSearchMatches);
  return matches;
};
