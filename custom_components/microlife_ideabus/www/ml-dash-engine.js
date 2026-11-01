// ml-dash-engine.js
import { getEffectiveRecords } from "./measurement-data.js";

export function mlFormatDate(hass, value) {
  if (!value) return "-";
  const date = new Date(value);
  try {
    return new Intl.DateTimeFormat(hass.locale?.language || "ru", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  } catch (_) {}
  return date.toLocaleString();
}

export function mlShortLabel(entity, fallback) {
  const friendlyName = entity?.attributes?.friendly_name || "";
  const parts = friendlyName.split(":");
  if (parts.length < 2) return fallback;

  let label = parts[1]
    .trim()
    .replace("Индикатор ", "")
    .replace("Режим ", "")
    .replace(" в порядке", "");

  const upper = label.toUpperCase();
  if (upper === "AFIB" || upper === "IHB" || upper === "MAM") return upper;
  return label;
}

export function mlDiscoverUsers(hass, dashboardPeriods, overrides = []) {
  const users = [];
  if (!hass || !hass.states) return users;

  const historyStates = Object.values(hass.states).filter(s => 
    s.entity_id.endsWith("_measurement_history")
  );

  // 1. Инициализируем плоскую структуру для агрегации flatMap
  const initialUsers = historyStates.map(state => {
    const slot = state.attributes?.user_slot;
    return {
      userSlot: slot,
      records: (state.attributes?.records || []).map(r => ({
        ...r,
        source_slot: r.device_user || slot,
        user_slot: null,
        user_name: null
      }))
    };
  });

  // 2. Получаем единый отфильтрованный пул эффективных записей (без excluded)
  const effectiveRecords = getEffectiveRecords(initialUsers, overrides);

  // 3. Строим карточки для каждого зарегистрированного пользователя
  historyStates.forEach((state) => {
    const slot = state.attributes?.user_slot;
    const currentPeriod = dashboardPeriods[slot] || "latest";

    // Фильтруем записи текущего слота и ГАРАНТИРОВАННО сортируем от новых к старым
    const records = effectiveRecords
      .filter(r => (r.user_slot || r.source_slot) === slot)
      .sort((a, b) => new Date(b.datetime) - new Date(a.datetime));

    const prefix = state.entity_id.replace("_measurement_history", "");
    const afibEntity = hass.states[`${prefix}_afib_indicator`];
    const ihbEntity = hass.states[`${prefix}_ihb_indicator`];
    const arrEntity = hass.states[`${prefix}_arrhythmia`];
    const mamEntity = hass.states[`${prefix}_mam`];
    const cuffEntity = hass.states[`${prefix}_cuff_ok`];

    let displayRecord = {};
    let isAverageMode = false;
    let avgCount = 0;
    let hasData = records.length > 0;

    // Теперь records[0] — это строго последняя точка
    const latest = hasData ? records[0] : null;

    if (currentPeriod === "latest") {
      displayRecord = latest || {};
    } else {
      isAverageMode = true;
      let filtered = [...records];

      if (currentPeriod === "0") {
        const todayStr = new Date().toDateString();
        filtered = records.filter(r => new Date(r.datetime).toDateString() === todayStr);
      } else {
        const now = new Date();
        const days = parseInt(currentPeriod, 10);
        const cutoff = new Date(now.setDate(now.getDate() - days));
        filtered = records.filter(r => new Date(r.datetime) >= cutoff);
      }

      if (filtered.length > 0) {
        avgCount = filtered.length;
        const sum = filtered.reduce((acc, r) => {
          acc.sys += Number(r.systolic) || 0;
          acc.dia += Number(r.diastolic) || 0;
          acc.pulse += Number(r.pulse) || 0;
          return acc;
        }, { sys: 0, dia: 0, pulse: 0 });

        displayRecord = {
          systolic: Math.round(sum.sys / filtered.length),
          diastolic: Math.round(sum.dia / filtered.length),
          pulse: Math.round(sum.pulse / filtered.length),
          // Благодаря предварительной сортировке, filtered[0] — самая свежая дата периода
          datetime: filtered[0]?.datetime
        };
      } else {
        hasData = false;
      }
    }

    users.push({
      name: state.attributes?.user_name || "Пользователь",
      slot: slot,
      currentPeriod: currentPeriod,
      isAverageMode: isAverageMode,
      avgCount: avgCount,
      hasData: hasData,
      systolic: hasData ? (displayRecord.systolic ?? "-") : "-",
      diastolic: hasData ? (displayRecord.diastolic ?? "-") : "-",
      pulse: hasData ? (displayRecord.pulse ?? "-") : "-",
      datetime: hasData ? displayRecord.datetime : null,
      
      // Считываем статусы флагов с конкретного объекта последней записи
      afib: hasData && latest && latest.afib === true,
      ihb: hasData && latest && latest.ihb === true,
      arrhythmia: hasData && latest && latest.arrhythmia === true,
      mam: hasData && latest && latest.mam === true,
      cuff: hasData && latest && latest.cuff_ok === true,
      
      afibLabel: mlShortLabel(afibEntity, "AFIB"),
      ihbLabel: mlShortLabel(ihbEntity, "IHB"),
      arrhythmiaLabel: mlShortLabel(arrEntity, "Аритмия"),
      mamLabel: mlShortLabel(mamEntity, "MAM"),
      cuffLabel: mlShortLabel(cuffEntity, "Манжета"),
    });
  });

  return users.sort((a, b) => a.name.localeCompare(b.name));
}
