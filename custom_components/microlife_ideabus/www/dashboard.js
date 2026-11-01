// dashboard.js
import { LitElement, html, css } from "../vendor/lit.js";
import { mlFormatDate, mlDiscoverUsers } from "./ml-dash-engine.js";
import { loadOverrides } from "./measurement-overrides.js"; // Импортируем загрузку оверрайдов

function badge(label, state, type = "alert") {
  let background = "#757575";
  if (type === "alert") background = state ? "#d32f2f" : "#757575";
  if (type === "positive") background = state ? "#9ccc65" : "#757575";

  return html`
    <div class="badge" style="background:${background};">
      ${label}
    </div>
  `;
}

class MicrolifeDashboard extends LitElement {
  static properties = {
    hass: {},
    dashboardPeriods: { state: true },
    overrides: { state: true },
  };

  constructor() {
    super();
    this.hass = null;
    this.dashboardPeriods = {};
    this.overrides = loadOverrides(); // Инициализируем массив оверрайдов из localStorage
  }

  static styles = css`
    :host {
      display: block;
    }
    .dashboard-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(520px, 1fr));
      gap: 16px;
    }
    .card-content {
      padding: 16px;
    }
    .name {
      font-size: 26px;
      font-weight: 600;
      margin-bottom: 4px;
    }
    .pressure {
      font-size: 56px;
      font-weight: 700;
      line-height: 1;
      margin-bottom: 18px;
    }
    .pulse {
      font-size: 32px;
      font-weight: 500;
      line-height: 1.2;
    }
    .datetime {
      font-size: 24px;
      font-weight: 400;
      line-height: 1.2;
      color: var(--primary-text-color);
      margin-top: 4px;
    }
    .badges {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 20px;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      height: 42px;
      min-width: 110px;
      padding: 0 18px;
      border-radius: 999px;
      color: white;
      font-size: 16px;
      font-weight: 700;
    }
    .dash-filter-bar {
      display: flex;
      gap: 6px;
      margin-bottom: 14px;
      flex-wrap: wrap;
    }
    .dash-filter-btn {
      border: none;
      cursor: pointer;
      padding: 4px 10px;
      font-size: 12px;
      font-weight: 600;
      border-radius: 8px;
      background: var(--secondary-background-color);
      color: var(--primary-text-color);
      transition: background 0.2s;
    }
    .dash-filter-btn.active {
      background: var(--primary-color);
      color: white;
    }
    .empty-msg {
      font-size: 22px;
      color: var(--secondary-text-color);
      margin: 20px 0;
      font-style: italic;
    }
    @media (max-width: 900px) {
      .dashboard-grid { grid-template-columns: 1fr; }
      .pressure { font-size: 48px; }
      .pulse { font-size: 28px; }
      .datetime { font-size: 22px; }
      .badge { min-width: 100px; height: 40px; font-size: 15px; }
    }
  `;

  setPeriod(slot, period) {
    this.dashboardPeriods = {
      ...this.dashboardPeriods,
      [slot]: period
    };
  }

  render() {
    // Подгружаем актуальные оверрайды прямо перед передачей в движок рендеринга дашборда
    this.overrides = loadOverrides();
    const users = mlDiscoverUsers(this.hass, this.dashboardPeriods, this.overrides);

    return html`
      ${users.length === 0
        ? html`<ha-card><div class="card-content">Пользователи не найдены</div></ha-card>`
        : html`
            <div class="dashboard-grid">
              ${users.map((user) => html`
                <ha-card>
                  <div class="card-content">
                    <div class="name">${user.name}</div>

                    <div class="dash-filter-bar">
                      <button class="dash-filter-btn ${user.currentPeriod === 'latest' ? 'active' : ''}" @click=${() => this.setPeriod(user.slot, 'latest')}>Последнее</button>
                      <button class="dash-filter-btn ${user.currentPeriod === '0' ? 'active' : ''}" @click=${() => this.setPeriod(user.slot, '0')}>День</button>
                      <button class="dash-filter-btn ${user.currentPeriod === '7' ? 'active' : ''}" @click=${() => this.setPeriod(user.slot, '7')}>7 дней</button>
                      <button class="dash-filter-btn ${user.currentPeriod === '30' ? 'active' : ''}" @click=${() => this.setPeriod(user.slot, '30')}>30 дней</button>
                      <button class="dash-filter-btn ${user.currentPeriod === '90' ? 'active' : ''}" @click=${() => this.setPeriod(user.slot, '90')}>90 дней</button>
                    </div>

                    ${!user.hasData 
                      ? html`<div class="empty-msg">Замеры за этот период отсутствуют</div>` 
                      : html`
                        <div class="pressure">${user.systolic} / ${user.diastolic}</div>
                        <div class="pulse">Пульс ${user.pulse} bpm</div>
                        <div class="datetime">
                          ${user.isAverageMode 
                            ? `Усреднено замеров: ${user.avgCount}` 
                            : mlFormatDate(this.hass, user.datetime)}
                        </div>
                    `}

                    <div class="badges">
                      ${badge(user.afibLabel, user.afib, "alert")}
                      ${badge(user.ihbLabel, user.ihb, "alert")}
                      ${badge(user.arrhythmiaLabel, user.arrhythmia, "alert")}
                      ${badge(user.mamLabel, user.mam, "positive")}
                      ${badge(user.cuffLabel, true, user.cuff ? "positive" : "alert")}
                    </div>
                  </div>
                </ha-card>
              `)}
            </div>
          `}
    `;
  }
}

if (!customElements.get("microlife-dashboard")) {
  customElements.define("microlife-dashboard", MicrolifeDashboard);
}

export function renderDashboard(hass) {
  return html`
    <microlife-dashboard
      .hass=${hass}
    ></microlife-dashboard>
  `;
}
