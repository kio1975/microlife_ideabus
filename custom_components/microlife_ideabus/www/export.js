// export.js
import { LitElement, html, css } from "../vendor/lit.js";
import { getUsers } from "./user-helpers.js";
import { getEffectiveRecords, sortNewestFirst, filterByPeriod } from "./measurement-data.js";
import { loadOverrides } from "./measurement-overrides.js";

class MicrolifeExport extends LitElement {
  static properties = {
    hass: {},
    selectedUserSlot: { state: true },
  };

  constructor() {
    super();
    this.hass = null;
    this.selectedUserSlot = null;
  }

  static styles = css`
    :host { display: block; }
    .export { display: flex; flex-direction: column; gap: 16px; }
    .selector { display: flex; flex-wrap: wrap; gap: 10px; }
    .btn {
      border: none; cursor: pointer; border-radius: 12px; padding: 8px 14px;
      background: var(--secondary-background-color); color: var(--primary-text-color);
      font-size: 14px; font-weight: 600;
    }
    .btn.active { background: var(--primary-color); color: white; }
    .export-btn {
      border: none; cursor: pointer; border-radius: 12px; padding: 12px 18px;
      background: var(--primary-color); color: white; font-size: 15px; font-weight: 600;
    }
  `;

  _localize(key, fallback) {
    return this.hass?.localize ? this.hass.localize(`component.microlife.frontend.export.${key}`) || fallback : fallback;
  }

  exportCsv() {
    const users = getUsers(this.hass);
    const user = users.find((u) => u.userSlot === this.selectedUserSlot);
    if (!user) return;

    const overrides = loadOverrides();
    const effective = getEffectiveRecords(users, overrides);
    
    const userRecords = effective.filter(r => 
      (r.user_slot || r.source_slot) === this.selectedUserSlot
    );

    const records = sortNewestFirst(filterByPeriod(userRecords, "all"));

    // Получаем переведенный массив заголовков. Если перевода нет — используем русский дефолт
    const defaultHeaders = ["Дата", "SYS", "DIA", "Пульс", "AFIB", "IHB", "Аритмия", "MAM", "Манжета", "Пользователь", "Комментарий"];
    let translatedHeaders = this._localize("csv_headers", null);
    
    if (typeof translatedHeaders === "string") {
      try { translatedHeaders = JSON.parse(translatedHeaders); } catch(_) { translatedHeaders = null; }
    }
    const headers = Array.isArray(translatedHeaders) ? translatedHeaders : defaultHeaders;

    const rows = [headers];

    records.forEach((r) => {
      const finalUserName = r.user_name || user.userName;
      rows.push([
        r.datetime, r.systolic, r.diastolic, r.pulse, r.afib, r.ihb, r.arrhythmia, r.mam, r.cuff_ok, finalUserName, r.comment
      ]);
    });

    const csv = rows.map((row) => row.join(";")).join("\n");
    const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    
    a.href = url;
    a.download = `report_${user.userName}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();

    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  render() {
    const users = getUsers(this.hass);
    if (!users.length) {
      return html`<ha-card><div class="card-content">${this._localize("no_users", "Пользователи не найдены")}</div></ha-card>`;
    }

    if (!this.selectedUserSlot) this.selectedUserSlot = users[0].userSlot;

    return html`
      <div class="export">
        <ha-card>
          <div class="card-content">
            <h2>${this._localize("title", "Экспорт измерений")}</h2>
            <div class="selector">
              ${users.map(user => html`
                <button
                  class="btn ${user.userSlot === this.selectedUserSlot ? 'active' : ''}"
                  @click=${() => this.selectedUserSlot = user.userSlot}
                >
                  ${user.userName}
                </button>
              `)}
            </div>
          </div>
        </ha-card>

        <ha-card>
          <div class="card-content">
            <button class="export-btn" @click=${() => this.exportCsv()}>${this._localize("btn_csv", "Экспорт CSV")}</button>
          </div>
        </ha-card>
      </div>
    `;
  }
}

if (!customElements.get("microlife-export")) {
  customElements.define("microlife-export", MicrolifeExport);
}

export function renderExport(hass) {
  return html`<microlife-export .hass=${hass}></microlife-export>`;
}
