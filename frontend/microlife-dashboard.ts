import { LitElement, css, html } from "lit";
import { customElement, property, state } from "lit/decorators.js";

interface HomeAssistant {
  states: Record<string, any>;
}

@customElement("microlife-dashboard")
export class MicrolifeDashboard extends LitElement {
  @property({ attribute: false })
  public hass!: HomeAssistant;

  @state()
  private activeTab = "u1";

  protected render() {
    if (!this.hass) {
      return html`<div>Loading...</div>`;
    }

    return html`
      <div class="container">
        <div class="header">
          <h1>Microlife</h1>
        </div>

        <div class="tabs">
          <button
            class=${this.activeTab === "u1" ? "active" : ""}
            @click=${() => (this.activeTab = "u1")}
          >
            Константин
          </button>

          <button
            class=${this.activeTab === "u2" ? "active" : ""}
            @click=${() => (this.activeTab = "u2")}
          >
            Ольга
          </button>

          <button
            class=${this.activeTab === "device" ? "active" : ""}
            @click=${() => (this.activeTab = "device")}
          >
            Устройство
          </button>
        </div>

        ${this.activeTab === "u1"
          ? this.renderUser(
              "Константин",
              "sensor.microlife_blood_pressure_user_1_systolic",
              "sensor.microlife_blood_pressure_user_1_diastolic",
              "sensor.microlife_blood_pressure_user_1_pulse",
              "sensor.microlife_blood_pressure_user_1_measurement_time"
            )
          : ""}

        ${this.activeTab === "u2"
          ? this.renderUser(
              "Ольга",
              "sensor.microlife_blood_pressure_user_2_systolic",
              "sensor.microlife_blood_pressure_user_2_diastolic",
              "sensor.microlife_blood_pressure_user_2_pulse",
              "sensor.microlife_blood_pressure_user_2_measurement_time"
            )
          : ""}

        ${this.activeTab === "device" ? this.renderDevice() : ""}
      </div>
    `;
  }

  private renderUser(
    title: string,
    sysEntity: string,
    diaEntity: string,
    pulseEntity: string,
    timeEntity: string
  ) {
    const sys = this.hass.states[sysEntity];
    const dia = this.hass.states[diaEntity];
    const pulse = this.hass.states[pulseEntity];
    const time = this.hass.states[timeEntity];

    return html`
      <div class="user-card">

        <div class="user-title">
          ${title}
        </div>

        <div class="pressure">
          ${sys?.state ?? "-"}
          <span>/</span>
          ${dia?.state ?? "-"}
        </div>

        <div class="pulse">
          ❤️ ${pulse?.state ?? "-"} bpm
        </div>

        <div class="datetime">
          ${time?.state ?? ""}
        </div>

      </div>
    `;
  }

  private renderDevice() {
    const rssi = this.hass.states[
      "sensor.microlife_b6_connect_blood_pressure_monitor_rssi"
    ];

    const firmware = this.hass.states[
      "sensor.microlife_b6_connect_blood_pressure_monitor_firmware_version"
    ];

    const software = this.hass.states[
      "sensor.microlife_b6_connect_blood_pressure_monitor_software_revision"
    ];

    return html`
      <div class="device-card">
        <div class="row">
          <span>RSSI</span>
          <span>${rssi?.state ?? "-"}</span>
        </div>

        <div class="row">
          <span>Firmware</span>
          <span>${firmware?.state ?? "-"}</span>
        </div>

        <div class="row">
          <span>Software</span>
          <span>${software?.state ?? "-"}</span>
        </div>
      </div>
    `;
  }

  static styles = css`
    :host {
      display: block;
      height: 100%;
      background: var(--primary-background-color);
      color: var(--primary-text-color);
    }

    .container {
      max-width: 1000px;
      margin: 0 auto;
      padding: 24px;
    }

    .header h1 {
      margin: 0 0 24px 0;
      font-size: 32px;
      font-weight: 500;
    }

    .tabs {
      display: flex;
      gap: 12px;
      margin-bottom: 24px;
      flex-wrap: wrap;
    }

    .tabs button {
      border: none;
      border-radius: 12px;
      padding: 12px 18px;
      cursor: pointer;
      font-size: 16px;
      background: var(--card-background-color);
      color: var(--primary-text-color);
    }

    .tabs button.active {
      background: var(--primary-color);
      color: white;
    }

    .user-card,
    .device-card {
      background: var(--card-background-color);
      border-radius: 20px;
      padding: 24px;
      box-shadow: var(--ha-card-box-shadow, none);
    }

    .user-title {
      font-size: 24px;
      margin-bottom: 20px;
    }

    .pressure {
      font-size: 72px;
      line-height: 1;
      font-weight: 300;
    }

    .pressure span {
      opacity: 0.4;
    }

    .pulse {
      margin-top: 16px;
      font-size: 26px;
    }

    .datetime {
      margin-top: 12px;
      opacity: 0.7;
      font-size: 16px;
    }

    .row {
      display: flex;
      justify-content: space-between;
      padding: 12px 0;
      border-bottom: 1px solid var(--divider-color);
    }

    .row:last-child {
      border-bottom: 0;
    }
  `;
}

declare global {
  interface HTMLElementTagNameMap {
    "microlife-dashboard": MicrolifeDashboard;
  }
}
