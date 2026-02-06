import assert from 'node:assert/strict';
import {
  buildMapSearchIndex,
  createOpenCCConverter,
  formatExgDate,
  formatExgDateTime,
  getExgStatusState,
  scoreSearchEntry,
  shouldShowExgStatus,
  stripBracketSegments,
  validateMapIndexEntry
} from '../src/mapSearchUtils.js';

const converter = createOpenCCConverter();
const mapIndexFixture = {
  ze_test_map: {
    map_cn: '[EXG]测试地图',
    aliases: ['coolmap', 'alias-two'],
    achievement: 'Test Achievement',
    deadline: null,
    duration_raw: '120'
  }
};

const searchIndex = buildMapSearchIndex(mapIndexFixture, converter);
const entry = searchIndex[0];

assert.equal(stripBracketSegments('[EXG]测试地图'), '测试地图');
assert.equal(stripBracketSegments('[史诗]badges!'), 'badges!');
assert.ok(scoreSearchEntry(entry, '测试') > 0, 'simplified query should match');
assert.ok(scoreSearchEntry(entry, '測試') > 0, 'traditional query should match');
assert.ok(scoreSearchEntry(entry, 'cool') > 0, 'alias query should match');
assert.ok(scoreSearchEntry(entry, 'ceshi') > 0, 'pinyin full should match');
assert.ok(scoreSearchEntry(entry, 'cs') > 0, 'pinyin initials should match');
assert.ok(scoreSearchEntry(entry, '试地') > 0, '2-gram should match');

assert.equal(getExgStatusState(1735689600, ''), 'cooldown');
assert.equal(getExgStatusState(null, '90'), 'available');
assert.equal(getExgStatusState(null, ''), 'not_available');
assert.match(formatExgDate(1735689600), /^\d{4}\/\d{2}\/\d{2}$/);
assert.match(formatExgDateTime(1735689600), /^\d{4}\/\d{2}\/\d{2} - \d{2}:\d{2}:\d{2}$/);

let warned = false;
validateMapIndexEntry('bad_map', { map_cn: 123 }, () => { warned = true; });
assert.equal(warned, true, 'validateMapIndexEntry should warn on invalid entry');

assert.equal(
  shouldShowExgStatus({ mapKey: 'ze_test_map', comms: ['EXG'], viewportWidth: 767 }),
  false,
  'mobile width should hide EXG status'
);
assert.equal(
  shouldShowExgStatus({ mapKey: 'ze_test_map', comms: ['EXG'], viewportWidth: 768 }),
  true,
  'non-mobile width should show EXG status'
);
assert.equal(
  shouldShowExgStatus({ mapKey: 'de_dust2', comms: ['EXG'], viewportWidth: 1024 }),
  false,
  'non-matching prefix should not show EXG status'
);
assert.equal(
  shouldShowExgStatus({ mapKey: 'ze_test_map', comms: ['other'], viewportWidth: 1024 }),
  false,
  'non-EXG comms should hide EXG status'
);

console.log('mapSearchUtils tests passed');
