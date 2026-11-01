/**
 * measurement-data.js
 */

export function getRecordId(record) {
  return record.datetime;
}

export function normalizeRecord(record) {
  return {
    datetime: record.datetime,
    source_slot: record.source_slot || record.device_user || null,
    systolic: Number(record.systolic) || 0,
    diastolic: Number(record.diastolic) || 0,
    pulse: Number(record.pulse) || 0,
    afib: Boolean(record.afib),
    ihb: Boolean(record.ihb),
    arrhythmia: Boolean(record.arrhythmia),
    mam: Boolean(record.mam),
    cuff_ok: Boolean(record.cuff_ok),
    user_slot: record.user_slot || null,
    user_name: record.user_name || null,
    excluded: Boolean(record.excluded),
    comment: record.comment || "",
  };
}

export function normalizeRecords(records) {
  return records.map(normalizeRecord);
}

export function applyOverrides(records, overrides = []) {
  const overrideMap = new Map();
  overrides.forEach((o) => overrideMap.set(o.recordId, o));

  return records.map((record) => {
    const id = getRecordId(record);
    const override = overrideMap.get(id);
    if (!override) return record;

    return {
      ...record,
      user_slot: override.user_slot ?? record.user_slot,
      user_name: override.user_name ?? record.user_name,
      excluded: override.excluded ?? record.excluded,
      comment: override.comment ?? record.comment,
    };
  });
}

export function getNormalizedRecords(rawRecords, overrides = []) {
  const normalized = normalizeRecords(rawRecords);
  return applyOverrides(normalized, overrides);
}

// === НОВЫЕ ФУНКЦИИ ЕДИНОГО СЛОЯ ДАННЫХ ===

// Полный плоский пул для вкладки Коррекции (включая исключенные записи)
export function getGlobalNormalizedRecords(users, overrides = []) {
  const allRecords = users.flatMap(u => u.records);
  return getNormalizedRecords(allRecords, overrides).sort(
    (a, b) => new Date(b.datetime) - new Date(a.datetime)
  );
}

// Чистый пул эффективных записей для Dashboard, History, Export
export function getEffectiveRecords(users, overrides = []) {
  const allRecords = users.flatMap(u => u.records);
  return getNormalizedRecords(allRecords, overrides)
    .filter(r => !r.excluded)
    .sort((a, b) => new Date(b.datetime) - new Date(a.datetime));
}

export function filterByPeriod(records, days) {
  if (!days || days === "all") return records;
  const threshold = Date.now() - days * 24 * 60 * 60 * 1000;
  return records.filter(r => new Date(r.datetime).getTime() >= threshold);
}

export function sortNewestFirst(records) {
  return [...records].sort((a, b) => new Date(b.datetime) - new Date(a.datetime));
}

export function sortOldestFirst(records) {
  return [...records].sort((a, b) => new Date(a.datetime) - new Date(b.datetime));
}

export function groupByDay(records) {
  const groups = new Map();
  records.forEach((record) => {
    const date = record.datetime.substring(0, 10);
    if (!groups.has(date)) groups.set(date, []);
    groups.get(date).push(record);
  });
  return groups;
}

export function calculateDailyAverages(records) {
  const groups = groupByDay(records);
  const result = [];
  groups.forEach((dayRecords, date) => {
    const count = dayRecords.length;
    result.push({
      datetime: date,
      measurements: count,
      systolic: Math.round(dayRecords.reduce((sum, r) => sum + r.systolic, 0) / count),
      diastolic: Math.round(dayRecords.reduce((sum, r) => sum + r.diastolic, 0) / count),
      pulse: Math.round(dayRecords.reduce((sum, r) => sum + r.pulse, 0) / count),
    });
  });
  return sortOldestFirst(result);
}

export function calculateStats(records) {
  if (!records.length) {
    return { count: 0, avgSys: 0, avgDia: 0, avgPulse: 0, maxSys: 0, minSys: 0 };
  }
  return {
    count: records.length,
    avgSys: Math.round(records.reduce((s, r) => s + r.systolic, 0) / records.length),
    avgDia: Math.round(records.reduce((s, r) => s + r.diastolic, 0) / records.length),
    avgPulse: Math.round(records.reduce((s, r) => s + r.pulse, 0) / records.length),
    maxSys: Math.max(...records.map(r => r.systolic)),
    minSys: Math.min(...records.map(r => r.systolic)),
  };
}

export function exportRecords(rawRecords, overrides = [], period = "all") {
  let records = getNormalizedRecords(rawRecords, overrides);
  records = filterByPeriod(records, period);
  return sortNewestFirst(records);
}
