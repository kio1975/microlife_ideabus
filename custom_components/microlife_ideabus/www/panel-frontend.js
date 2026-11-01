import {
  LitElement,
  html,
  css,
  until,
} from "./vendor/lit.js";

import {
  router,
  navigate,
  currentPath,
} from "./router.js";

const PANEL_VERSION = "1.0.1";

class MicrolifePanel extends LitElement {

  static properties = {
    hass: {},
    narrow: {},
    _currentPage: { state: true },
    _pagePromise: { state: true },
  };

  constructor() {

    super();

    this._currentPage =
      "/dashboard";

    this._pagePromise =
      null;

    this._onNavigate =
      (ev) => {
        this._navigate(
          ev.detail.path
        );
      };
  }

  connectedCallback() {

    super.connectedCallback();

    window.addEventListener(
      "microlife-navigate",
      this._onNavigate
    );

    this._navigate(
      currentPath()
    );
  }

  disconnectedCallback() {

    super.disconnectedCallback();

    window.removeEventListener(
      "microlife-navigate",
      this._onNavigate
    );
  }

  updated(changedProps) {

    if (
      changedProps.has("hass") &&
      this.hass &&
      !this._pagePromise
    ) {
      this._navigate(
        this._currentPage
      );
    }
  }

  async _loadPage(path) {

    try {

      const pageLoader =
        router[path] ||
        router["/error"];

      this._pagePromise =
        pageLoader(
          this.hass
        );

      this.requestUpdate();

    } catch (err) {

      console.error(
        "Microlife page load error",
        err
      );

      this._pagePromise =
        router["/error"](
          this.hass
        );
    }
  }

  _navigate(path) {

    this._currentPage =
      path;

    navigate(path);

    this._loadPage(path);
  }

  renderLoading() {

    return html`

      <div class="loading">

        <ha-circular-progress
          active>
        </ha-circular-progress>

        <div class="loading-text">
          Загрузка...
        </div>

      </div>

    `;
  }

  render() {

    return html`

      <ha-app-layout>

        <ha-top-app-bar
          slot="header"
        >

          <ha-menu-button
            .hass=${this.hass}
            .narrow=${this.narrow}
          >
          </ha-menu-button>

          <div main-title>
            Microlife
          </div>

          <div class="version">
            v${PANEL_VERSION}
          </div>

        </ha-top-app-bar>

        <div
          slot="content"
          class="content"
        >

          <div class="nav">

            <button
              class=${this._currentPage === "/dashboard"
                ? "active"
                : ""}
              @click=${() =>
                this._navigate(
                  "/dashboard"
                )}
            >
              Обзор
            </button>

            <button
              class=${this._currentPage === "/history"
                ? "active"
                : ""}
              @click=${() =>
                this._navigate(
                  "/history"
                )}
            >
              История
            </button>

            <button
              class=${this._currentPage === "/export"
                ? "active"
                : ""}
              @click=${() =>
                this._navigate(
                  "/export"
                )}
            >
              Экспорт
            </button>

            <button
              class=${this._currentPage === "/correction"
                ? "active"
                : ""}
              @click=${() =>
                this._navigate(
                  "/correction"
                )}
            >
              Коррекция
            </button>

            <button
              class=${this._currentPage === "/device"
                ? "active"
                : ""}
              @click=${() =>
                this._navigate(
                  "/device"
                )}
            >
              Устройство
            </button>

          </div>

          ${until(
            this._pagePromise,
            this.renderLoading()
          )}

        </div>

      </ha-app-layout>

    `;
  }

  static styles = css`

    :host {
      display: block;
      height: 100%;
    }

    .content {
      padding: 16px;
    }

    .nav {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 20px;
    }

    .nav button {

      border: none;
      cursor: pointer;

      border-radius: 20px;

      padding: 10px 18px;

      background:
        var(--primary-color);

      color: white;

      font-size: 14px;
      font-weight: 600;
    }

    .nav button.active {

      background:
        var(--accent-color);

    }

    .loading {

      display: flex;

      flex-direction: column;

      align-items: center;
      justify-content: center;

      padding: 60px;
    }

    .loading-text {

      margin-top: 16px;

      font-size: 16px;
    }

    .version {

      margin-left: auto;

      font-size: 12px;

      opacity: 0.7;
    }

  `;
}

if (
  !customElements.get(
    "microlife-panel"
  )
) {

  customElements.define(
    "microlife-panel",
    MicrolifePanel
  );
}