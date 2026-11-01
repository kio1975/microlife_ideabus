// chart-config.js
import "../vendor/chart.umd.js";
import "../vendor/chartjs-plugin-annotation.min.js";

if (window.Chart && window['chartjs-plugin-annotation']) {
  Chart.register(window['chartjs-plugin-annotation']);
}

export function createChartInstance(canvas, records, hass) {
  const lang = hass?.locale?.language || "ru";
  
  // Хелпер для получения строк из ресурсов Home Assistant
  const localize = (key, fallback) => {
    return hass?.localize ? hass.localize(`component.microlife.frontend.chart.${key}`) || fallback : fallback;
  };

  return new Chart(canvas, {
    type: "line",
    data: {
      labels: records.map((r) => {
        if (r.customLabel) return r.customLabel;
        const d = new Date(r.datetime);
        return d.toLocaleDateString(lang === "en" ? "en-US" : "ru-RU", { day: "2-digit", month: "2-digit" });
      }),
      datasets: [
        {
          label: "SYS",
          data: records.map((r) => Number(r.systolic)),
          borderColor: "#d32f2f",
          backgroundColor: "#d32f2f",
          tension: 0.25,
          pointRadius: 5,
          pointHoverRadius: 8,
        },
        {
          label: "DIA",
          data: records.map((r) => Number(r.diastolic)),
          borderColor: "#1976d2",
          backgroundColor: "#1976d2",
          tension: 0.25,
          pointRadius: 5,
          pointHoverRadius: 8,
        },
        {
          label: lang === "en" ? "Pulse" : "Пульс",
          data: records.map((r) => Number(r.pulse)),
          borderColor: "#43a047",
          backgroundColor: "#43a047",
          tension: 0.25,
          pointRadius: 5,
          pointHoverRadius: 8,
          yAxisID: "pulse",
          borderDash:[6, 6],
        }
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: true },
        tooltip: {
          callbacks: {
            title: (items) => {
              if (!items || !items.length) return "";
              const context = items[0];
              const r = records[context.dataIndex];
              if (!r) return "";
              if (r.customLabel) return r.customLabel;
              const dateStr = new Date(r.datetime).toLocaleDateString(lang === "en" ? "en-US" : "ru-RU");
              
              if (r.isGrouped) {
                const mask = localize("tooltip_average", "Среднее за {date}");
                return mask.replace("{date}", dateStr);
              }
              return new Date(r.datetime).toLocaleString(lang === "en" ? "en-US" : "ru-RU");
            },
            afterBody: (items) => {
              if (!items || !items.length) return [];
              const context = items[0];
              const r = records[context.dataIndex];
              if (r && r.isGrouped) {
                const mask = localize("tooltip_count", "Замеров учтено: {count}");
                return [mask.replace("{count}", r.count)];
              }
              return [];
            }
          },
        },
        annotation: {
          annotations: {
            limit140: {
              type: "line",
              yMin: 140,
              yMax: 140,
              borderColor: "#f9a825",
              borderWidth: 2,
              label: {
                display: true,
                content: localize("norm_sys", "Норма SYS (140)"),
                position: 'start',
                backgroundColor: 'rgba(249, 168, 37, 0.8)',
                color: '#fff',
                font: { size: 11, weight: 'bold' }
              }
            },
          },
        },
      },
      scales: {
        y: {
          title: { display: true, text: localize("axis_y", "мм рт. ст.") },
          ticks: { stepSize: 10 },
        },
        pulse: {
          position: "right",
          title: { display: true, text: localize("axis_pulse", "уд. / мин.") },
          grid: { drawOnChartArea: false },
        },
        x: {
          title: { display: true, text: localize("axis_x", "Дата") },
          ticks: { maxRotation: 45, minRotation: 45, autoSkip: true, maxTicksLimit: 6 },
        },
      },
    },
  });
}
