// user-helpers.js

export function getUsers(hass) {

  const users = [];

  if (!hass || !hass.states) {
    return users;
  }

  Object.values(hass.states).forEach((state) => {

    if (
      !state.entity_id.endsWith(
        "_measurement_history"
      )
    ) {
      return;
    }

    const userName =
      state.attributes?.user_name ||
      "Пользователь";

    const userSlot =
      state.attributes?.user_slot;

    const records =
      (
        state.attributes?.records ||
        []
      ).map((record) => ({

        ...record,

        // Исходный пользователь из прибора
        source_slot:
          record.device_user ||
          userSlot,

        // Текущий пользователь
        user_name: null,
        user_slot: null,
          
      }));

    users.push({
      userName,
      userSlot,
      records,
    });

  });

  return users.sort(
    (a, b) =>
      a.userName.localeCompare(
        b.userName
      )
  );
}

export function getFilteredRecords(
  records,
  selectedPeriod
) {

  if (
    selectedPeriod === "all"
  ) {
    return records;
  }

  const now =
    new Date();

  const daysLimit =
    parseInt(
      selectedPeriod,
      10
    );

  const cutoffDate =
    new Date(
      now.setDate(
        now.getDate() -
        daysLimit
      )
    );

  return records.filter(
    (r) =>
      new Date(
        r.datetime
      ) >= cutoffDate
  );
}

export function getGroupedByDayRecords(
  records,
  isSingleToday = false
) {

  if (isSingleToday) {

    const todayStr =
      new Date()
        .toDateString();

    const todayRecords =
      records.filter(
        (r) =>
          new Date(
            r.datetime
          ).toDateString() ===
          todayStr
      );

    if (!todayRecords.length) {
      return [];
    }

    const sum =
      todayRecords.reduce(
        (acc, r) => {

          acc.sys +=
            Number(
              r.systolic
            ) || 0;

          acc.dia +=
            Number(
              r.diastolic
            ) || 0;

          acc.pulse +=
            Number(
              r.pulse
            ) || 0;

          return acc;

        },
        {
          sys: 0,
          dia: 0,
          pulse: 0,
        }
      );

    return [{
      datetime:
        new Date()
          .toISOString(),

      systolic:
        Math.round(
          sum.sys /
          todayRecords.length
        ),

      diastolic:
        Math.round(
          sum.dia /
          todayRecords.length
        ),

      pulse:
        Math.round(
          sum.pulse /
          todayRecords.length
        ),

      isGrouped: true,

      customLabel:
        "Среднее за сегодня",

      count:
        todayRecords.length,
    }];
  }

  const groups = {};

  records.forEach((r) => {

    const dateKey =
      new Date(
        r.datetime
      )
        .toISOString()
        .split("T")[0];

    if (!groups[dateKey]) {

      groups[dateKey] = {
        systolic: 0,
        diastolic: 0,
        pulse: 0,
        count: 0,
        datetime: dateKey,
      };
    }

    groups[dateKey]
      .systolic +=
      Number(
        r.systolic
      ) || 0;

    groups[dateKey]
      .diastolic +=
      Number(
        r.diastolic
      ) || 0;

    groups[dateKey]
      .pulse +=
      Number(
        r.pulse
      ) || 0;

    groups[dateKey]
      .count += 1;

  });

  return Object
    .values(groups)
    .map((g) => ({
      datetime:
        g.datetime,

      systolic:
        Math.round(
          g.systolic /
          g.count
        ),

      diastolic:
        Math.round(
          g.diastolic /
          g.count
        ),

      pulse:
        Math.round(
          g.pulse /
          g.count
        ),

      isGrouped: true,

      count:
        g.count,
    }))
    .sort(
      (a, b) =>
        new Date(
          a.datetime
        ) -
        new Date(
          b.datetime
        )
    );
}

export function formatDate(
  value,
  hassLanguage
) {

  if (!value) {
    return "-";
  }

  const date =
    new Date(value);

  return new Intl.DateTimeFormat(
    hassLanguage || "ru",
    {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }
  )
    .format(date)
    .replace(",", "");
}
