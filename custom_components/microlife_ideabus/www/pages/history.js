// microlife-history.js
import { LitElement, html, css } from "../vendor/lit.js";
import { getUsers, getFilteredRecords, getGroupedByDayRecords, formatDate } from "./user-helpers.js";
import { getEffectiveRecords } from "./measurement-data.js";
import { createChartInstance } from "./chart-config.js";
import { loadOverrides } from "./measurement-overrides.js";

class MicrolifeHistory extends LitElement {
  static properties = {
    hass: {},
    selectedUserSlot: { state: true },
    selectedPeriod: { state: true },
    viewMode: { state: true },
    isChartReversed: { state: true },
  };

  constructor() {
    super();
    this._chart = null;
    this.hass = null;
    this.selectedUserSlot = null;
    this.selectedPeriod = "all";
    this.viewMode = "raw"; 
    this.isChartReversed = true; 
    this.overrides = loadOverrides();
  }

  static styles = css`
    :host { display: block; }
    .history { display: flex; flex-direction: column; gap: 16px; }
    .user-selector, .period-selector, .mode-selector { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
    .selector-label { font-size: 14px; font-weight: 600; color: var(--secondary-text-color); width: 120px; }
    .user-btn, .period-btn, .mode-btn {
      border: none; cursor: pointer; border-radius: 20px; padding: 10px 18px;
      font-size: 15px; font-weight: 600; background: var(--secondary-background-color);
      transition: background 0.2s, color 0.2s;
    }
    .user-btn.active, .period-btn.active, .mode-btn.active { background: var(--primary-color); color: white; }
    .period-btn, .mode-btn { padding: 6px 14px; font-size: 13px; border-radius: 12px; }
    
    .toggle-container {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      user-select: none;
    }

    .summary { display: flex; justify-content: space-between; align-items: center; }
    .user-name { font-size: 24px; font-weight: 600; }
    .count { color: var(--secondary-text-color); }
    .table-wrapper { max-height: 70vh; overflow: auto; }
    table { width: 100%; border-collapse: collapse; }
    thead th { position: sticky; top: 0; z-index: 10; background: var(--secondary-background-color); padding: 12px; text-align: left; }
    td { padding: 12px; border-bottom: 1px solid var(--divider-color); }
    tr:hover { background: rgba(127, 127, 127, 0.08); }
    .pressure { font-weight: 700; }
    
    .indicator-true { color: #d32f2f; font-size: 18px; } 
    .indicator-false { color: #757575; font-size: 18px; } 
    .indicator-positive { color: #43a047; font-size: 18px; } 
    .no-data { text-align: center; color: var(--secondary-text-color); padding: 24px !important; font-style: italic; }
  `;

  // Хелпер динамического подхвата строк из ресурсов Home Assistant интеграции
  _localize(key, fallback) {
    return this.hass?.localize ? this.hass.localize(`component.microlife.frontend.history.${key}`) || fallback : fallback;
  }

  updated(changedProperties) {
    super.updated(changedProperties);
    if (
      changedProperties.has('selectedUserSlot') || 
      changedProperties.has('selectedPeriod') || 
      changedProperties.has('viewMode') || 
      changedProperties.has('isChartReversed') || 
      changedProperties.has('hass') ||
      !this._chart
    ) {
      setTimeout(() => this.drawChart(), 0);
    }
  }

  indicator(value, isPositiveType = false) {
    if (!value) {
      return html`<span class="indicator-false">○</span>`;
    }
    return html`<span class=${isPositiveType ? "indicator-positive" : "indicator-true"}>●</span>`;
  }

  cuffIndicator(value) {
    return html`
      <span style="font-size: 18px; color: ${value ? '#43a047' : '#d32f2f'};">●</span>
    `;
  }

  renderChart() {
    return html`<div style="position:relative; height:450px;"><canvas id="pressureChart"></canvas></div>`;
  }

  _getUserRecords(users) {
    this.overrides = loadOverrides();
    const effective = getEffectiveRecords(users, this.overrides);
    return effective.filter(r => (r.user_slot || r.source_slot) === this.selectedUserSlot);
  }
  drawChart() {
    const users = getUsers(this.hass);
    if (!users.length) return;
    if (!this.selectedUserSlot) this.selectedUserSlot = users[0].userSlot;

    const userRecords = this._getUserRecords(users);
    let records = getFilteredRecords([...userRecords], this.selectedPeriod);

    if (this.viewMode === "daily") {
      records = [...getGroupedByDayRecords(records, false)].reverse();
    } else if (this.viewMode === "today") {
      records = getGroupedByDayRecords(records, true);
    }

    const chartRecords = this.isChartReversed ? [...records] : [...records].reverse();

    const canvas = this.renderRoot.querySelector("#pressureChart");
    if (!canvas) return;

    if (this._chart) this._chart.destroy();
    this._chart = createChartInstance(canvas, chartRecords, this.hass);
  }

  render() {
    const users = getUsers(this.hass);
    if (!users.length) {
      return html`<ha-card><div class="card-content">${this._localize("no_data_msg", "История измерений отсутствует")}</div></ha-card>`;
    }

    if (!this.selectedUserSlot) this.selectedUserSlot = users[0].userSlot;

    const user = users.find((u) => u.userSlot === this.selectedUserSlot) || users[0];
    const userRecords = this._getUserRecords(users);
    
    const rawRecords = getFilteredRecords([...userRecords], this.selectedPeriod);
    
    let tableRecords = [];
    if (this.viewMode === "daily") {
      tableRecords = [...getGroupedByDayRecords(rawRecords, false)].reverse();
    } else if (this.viewMode === "today") {
      tableRecords = getGroupedByDayRecords(rawRecords, true);
    } else {
      tableRecords = [...rawRecords];
    }

    const showDetailedIndicators = this.viewMode === "raw";

    return html`
      <div class="history">
        <div class="user-selector">
          ${users.map(u => html`
            <button class="user-btn ${u.userSlot === this.selectedUserSlot ? 'active' : ''}" @click=${() => this.selectedUserSlot = u.userSlot}>
              ${u.userName}
            </button>
          `)}
        </div>

        <ha-card>
          <div class="card-content">
            <div class="summary">
              <div class="user-name">${user.userName}</div>
              <div class="count">${this._localize("points_displayed", "Точек выведено")}: ${tableRecords.length}</div>
            </div>
          </div>
        </ha-card>

        <div class="period-selector">
          <span class="selector-label">${this._localize("period", "Период")}:</span>
          <button class="period-btn ${this.selectedPeriod === 'all' ? 'active' : ''}" @click=${() => this.selectedPeriod = 'all'}>${this._localize("period_all", "Все")}</button>
          <button class="period-btn ${this.selectedPeriod === '7' ? 'active' : ''}" @click=${() => this.selectedPeriod = '7'}>${this._localize("period_7", "7 дней")}</button>
          <button class="period-btn ${this.selectedPeriod === '30' ? 'active' : ''}" @click=${() => this.selectedPeriod = '30'}>${this._localize("period_30", "30 дней")}</button>
          <button class="period-btn ${this.selectedPeriod === '90' ? 'active' : ''}" @click=${() => this.selectedPeriod = '90'}>${this._localize("period_90", "90 дней")}</button>
        </div>

        <div class="mode-selector">
          <span class="selector-label">${this._localize("chart_mode", "Режим графика")}:</span>
          <button class="mode-btn ${this.viewMode === 'raw' ? 'active' : ''}" @click=${() => this.viewMode = 'raw'}>${this._localize("mode_raw", "Все замеры")}</button>
          <button class="mode-btn ${this.viewMode === 'daily' ? 'active' : ''}" @click=${() => this.viewMode = 'daily'}>${this._localize("mode_daily", "Среднее по дням")}</button>
          <button class="mode-btn ${this.viewMode === 'today' ? 'active' : ''}" @click=${() => this.viewMode = 'today'}>${this._localize("mode_today", "Среднее за день")}</button>
          
          <label class="toggle-container" style="margin-left: auto;">
            <input 
              type="checkbox" 
              .checked=${this.isChartReversed}
              @change=${(e) => this.isChartReversed = e.target.checked}
            >
            ${this._localize("newest_on_left", "Новые замеры слева")}
          </label>
        </div>

        <ha-card>
          <div class="card-content">${this.renderChart()}</div>
        </ha-card>

        <ha-card>
          <div class="card-content">
            <div class="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>${showDetailedIndicators ? this._localize("th_datetime", "Дата и время") : this._localize("th_period_date", "Период / Дата")}</th>
                    <th>${this._localize("th_sys", "SYS")}</th>
                    <th>${this._localize("th_dia", "DIA")}</th>
                    <th>${this._localize("th_pulse", "Пульс")}</th>
                    ${showDetailedIndicators ? html`
                      <th>${this._localize("th_afib", "AFIB")}</th>
                      <th>${this._localize("th_ihb", "IHB")}</th>
                      <th>${this._localize("th_arr", "АРИТ")}</th>
                      <th>${this._localize("th_mam", "MAM")}</th>
                      <th>${this._localize("th_cuff", "Манжета")}</th>
                    ` : ''}
                  </tr>
                </thead>
                <tbody>
                  ${tableRecords.length === 0 ? html`
                    <tr>
                      <td colspan="${showDetailedIndicators ? 9 : 4}" class="no-data">${this._localize("no_measurements", "Замеры отсутствуют")}</td>
                    </tr>
                  ` : tableRecords.map(record => html`
                    <tr>
                      <td>
                        ${record.customLabel 
                          ? record.customLabel 
                          : (this.viewMode === "daily" 
                              ? new Date(record.datetime).toLocaleDateString(this.hass?.locale?.language === "en" ? "en-US" : "ru-RU") 
                              : formatDate(record.datetime, this.hass?.locale?.language))}
                      </td>
                      <td class="pressure">${record.systolic}</td>
                      <td class="pressure">${record.diastolic}</td>
                      <td>${record.pulse}</td>
                      ${showDetailedIndicators ? html`
                        <td>${this.indicator(record.afib, false)}</td>
                        <td>${this.indicator(record.ihb, false)}</td>
                        <td>${this.indicator(record.arrhythmia, false)}</td>
                        <td>${this.indicator(record.mam, true)}</td>
                        <td>${this.cuffIndicator(record.cuff_ok)}</td>
                      ` : ''}
                    </tr>
                  `)}
                </tbody>
              </table>
            </div>
          </div>
        </ha-card>
      </div>
    `;
  }
}

if (!customElements.get("microlife-history")) {
  customElements.define("microlife-history", MicrolifeHistory);
}
