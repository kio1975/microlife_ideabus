// correction.js
import { LitElement, html, css } from "../vendor/lit.js";
import { getUsers, formatDate } from "./user-helpers.js";
import { getGlobalNormalizedRecords, getRecordId } from "./measurement-data.js";
import { loadOverrides, saveOverrides } from "./measurement-overrides.js";

class MicrolifeCorrection extends LitElement {
  static properties = {
    hass: {},
    overrides: { state: true },
  };

  constructor() {
    super();
    this.hass = null;
    this.overrides = loadOverrides();
  }

  static styles = css`
    :host { display: block; }
    .table-wrapper { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; }
    th, td { padding: 10px; border-bottom: 1px solid var(--divider-color); text-align: left; }
    th { position: sticky; top: 0; z-index: 1; background: var(--card-background-color); }
    select, input[type="text"] { width: 100%; box-sizing: border-box; }
    
    /* Статистика коррекций */
    .stats-panel {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 16px;
      padding: 12px;
      background: var(--secondary-background-color, #f5f5f5);
      border-radius: 8px;
      font-size: 14px;
    }
    .stats-item {
      padding: 4px 10px;
      background: var(--card-background-color, #fff);
      border-radius: 6px;
      border: 1px solid var(--divider-color, #e0e0e0);
      font-weight: 500;
    }

    /* Стили строк */
    .overridden {
      background-color: #fffde7 !important; /* Очень светло-желтый */
    }
    .excluded {
      opacity: 0.5;
      background-color: rgba(128, 128, 128, 0.08) !important;
    }
    
    .slot { width: 55px; text-align: center; font-weight: 700; font-family: monospace; }
    .number { font-weight: 600; white-space: nowrap; }
  `;

  // Хелпер для получения строк из вашей интеграции Home Assistant
  _localize(key, fallback) {
    return this.hass?.localize ? this.hass.localize(`component.microlife.frontend.correction.${key}`) || fallback : fallback;
  }

  upsertOverride(recordId, updates) {
    console.log("CARD UPSERT", recordId, updates);
    const idx = this.overrides.findIndex((item) => item.recordId === recordId);
    if (idx >= 0) {
      this.overrides = [
        ...this.overrides.slice(0, idx),
        { ...this.overrides[idx], ...updates },
        ...this.overrides.slice(idx + 1),
      ];
    } else {
      this.overrides = [...this.overrides, { recordId, ...updates }];
    }
    saveOverrides(this.overrides);
    this.requestUpdate();
  }

  render() {
    console.error("MICROLIFE BUILD 999");
    const users = getUsers(this.hass);
    const records = getGlobalNormalizedRecords(users, this.overrides);

    // Расчет статистики
    const stats = {
      reassigned: {}, // { 'u1 -> u2': count }
      hidden: {},     // { 'u1': count }
    };

    // Инициализируем маппинг слотов в читаемые имена для красивого вывода
    const slotToName = {};
    users.forEach(u => {
      slotToName[u.userSlot] = u.userName;
    });

    records.forEach(r => {
      const hasSlotOverride = r.user_slot !== null && r.user_slot !== r.source_slot;
      
      if (r.excluded) {
        // Если запись скрыта, считаем её в скрытые по исходному слоту устройства
        stats.hidden[r.source_slot] = (stats.hidden[r.source_slot] || 0) + 1;
      } else if (hasSlotOverride) {
        // Если не скрыта, но переназначена — считаем перенос
        const key = `${r.source_slot} → ${r.user_slot}`;
        stats.reassigned[key] = (stats.reassigned[key] || 0) + 1;
      }
    });

    return html`
      <ha-card>
        <div class="card-content">
          <h2>${this._localize("title", "Коррекция измерений")}</h2>

          <!-- Панель сводки по корректировкам -->
          <div class="stats-panel">
            ${Object.entries(stats.reassigned).map(([route, count]) => {
              const [fromSlot, toSlot] = route.split(' → ');
              const fromName = slotToName[fromSlot] || fromSlot;
              const toName = slotToName[toSlot] || toSlot;
              
              return html`
                <div class="stats-item">
                  🔄 ${this._localize("reassigned_from", "Переведено: с")} <b>${fromName}</b> 
                  ${this._localize("reassigned_to", "на")} <b>${toName}</b> 
                  — ${count}
                </div>
              `;
            })}
            
            ${Object.entries(stats.hidden).map(([slot, count]) => {
              const name = slotToName[slot] || slot;
              return html`
                <div class="stats-item">
                  🚫 ${this._localize("hidden_prefix", "Скрыто замеров")} (<b>${name}</b>): ${count}
                </div>
              `;
            })}
            
            ${Object.keys(stats.reassigned).length === 0 && Object.keys(stats.hidden).length === 0
              ? html`<div style="color: var(--secondary-text-color); font-style: italic;">${this._localize("no_corrections", "Активные корректировки отсутствуют")}</div>`
              : ''
            }
          </div>

          <div class="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>${this._localize("th_date", "Дата")}</th>
                  <th>${this._localize("th_sys", "SYS")}</th>
                  <th>${this._localize("th_dia", "DIA")}</th>
                  <th>${this._localize("th_pulse", "Пульс")}</th>
                  <th>${this._localize("th_u", "U")}</th>
                  <th>${this._localize("th_user", "Пользователь")}</th>
                  <th>${this._localize("th_excl", "Искл.")}</th>
                  <th>${this._localize("th_comment", "Примечание")}</th>
                </tr>
              </thead>
              <tbody>
                ${records.map((record) => {
                  const id = getRecordId(record);
                  const currentSlot = record.user_slot || record.source_slot;
                  
                  // Условие для подсветки: слот был явно изменен пользователем
                  const isOverridden = record.user_slot !== null && record.user_slot !== record.source_slot;

                  // Формируем результирующий класс строки
                  let rowClass = "";
                  if (record.excluded) {
                    rowClass = "excluded";
                  } else if (isOverridden) {
                    rowClass = "overridden";
                  }

                  return html`
                    <tr class=${rowClass}>
                      <td>${formatDate(record.datetime, this.hass?.locale?.language)}</td>
                      <td class="number">${record.systolic}</td>
                      <td class="number">${record.diastolic}</td>
                      <td class="number">${record.pulse}</td>
                      <td class="slot" title="${this._localize("original_slot", "Исходный слот прибора")}">${record.source_slot}</td>
                      <td>
                        <select
                          .value=${currentSlot || ""}
                          @change=${(e) => {
                            const selected = users.find((u) => u.userSlot === e.target.value);
                            if (!selected) return;
                            this.upsertOverride(id, {
                              user_slot: selected.userSlot,
                              user_name: selected.userName,
                            });
                          }}
                        >
                          ${users.map(u => html`
                            <option value=${u.userSlot} ?selected=${currentSlot === u.userSlot}>
                              ${u.userName}
                            </option>
                          `)}
                        </select>
                      </td>
                      <td>
                        <input
                          type="checkbox"
                          .checked=${Boolean(record.excluded)}
                          @change=${(e) => this.upsertOverride(id, { excluded: e.target.checked })}
                        >
                      </td>
                      <td>
                        <input
                          type="text"
                          .value=${record.comment || ""}
                          placeholder="${this._localize("comment_placeholder", "Например: замер соседа")}"
                          @change=${(e) => this.upsertOverride(id, { comment: e.target.value })}
                        >
                      </td>
                    </tr>
                  `;
                })}
              </tbody>
            </table>
          </div>
        </div>
      </ha-card>
    `;
  }
}

if (!customElements.get("microlife-correction")) {
  customElements.define("microlife-correction", MicrolifeCorrection);
}

export function renderCorrection(hass) {
  return html`<microlife-correction .hass=${hass}></microlife-correction>`;
}
