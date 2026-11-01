// measurement-overrides.js

const STORAGE_KEY =
  "microlife_overrides";

export function loadOverrides() {
  const raw =
    localStorage.getItem(
      STORAGE_KEY
    );

  if (!raw) {
    return [];
  }

  try {

    return JSON.parse(
      raw
    );

  } catch {

    return [];
  }
}

export function saveOverrides(
  overrides
) {

  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify(
      overrides
    )
  );
}

export function upsertOverride(
  overrides,
  recordId,
  updates
) {

  const index =
    overrides.findIndex(
      (item) =>
        item.recordId ===
        recordId
    );

  if (index >= 0) {

    overrides[index] = {
      ...overrides[index],
      ...updates,
    };

  } else {

    overrides.push({
      recordId,
      ...updates,
    });

  }

  saveOverrides(
    overrides
  );

  return overrides;
}

export function removeOverride(
  overrides,
  recordId
) {

  const filtered =
    overrides.filter(
      (item) =>
        item.recordId !==
        recordId
    );

  saveOverrides(
    filtered
  );

  return filtered;
}
