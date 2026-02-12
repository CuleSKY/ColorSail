export const stripBracketSegments = (value) => (value || '').toString().replace(/\[[^\]]*]/g, '').trim();
export const normalizeSearchText = (value) => (value || '').toString().toLowerCase().replace(/\s+/g, '');

const ZH_VARIANT_PAIRS = [
  ['国', '國'],
  ['图', '圖'],
  ['关', '關'],
  ['乐', '樂'],
  ['气', '氣'],
  ['时', '時'],
  ['龙', '龍'],
  ['场', '場'],
  ['战', '戰'],
  ['线', '線'],
  ['爱', '愛'],
  ['梦', '夢'],
  ['点', '點'],
  ['魔', '魔'],
  ['剑', '劍'],
  ['败', '敗'],
  ['风', '風'],
  ['云', '雲'],
  ['业', '業'],
  ['机', '機'],
  ['门', '門'],
  ['岛', '島'],
  ['剂', '劑'],
  ['远', '遠'],
  ['觉', '覺'],
  ['体', '體'],
  ['击', '擊'],
  ['阳', '陽'],
  ['级', '級'],
  ['终', '終']
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
