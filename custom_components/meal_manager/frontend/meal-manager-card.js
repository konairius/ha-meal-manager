/*
 * Meal Manager card and panel for Home Assistant.
 * Plain web components without dependencies; served locally by the integration.
 */

const STRINGS = {
  en: {
    title: "Meal plan",
    tab_plan: "Plan",
    tab_bans: "Banned",
    tab_settings: "Settings",
    planning: "Planning meals…",
    no_plan: "No meal plan yet.",
    start: "Start",
    days: "Days",
    create: "Create meal plan",
    suggestion: "Suggestion",
    suggestion_for: "New plan {from} – {to}",
    all_cooked: "Everything is cooked. Here is a new suggestion.",
    all_cooked_no_draft: "Everything is cooked.",
    accept: "Accept",
    discard: "Discard",
    regenerate: "New suggestion",
    new_plan: "New plan",
    shopping: "Shopping list",
    shopping_added: "{count} items added to {list}.",
    shopping_none: "Nothing to buy.",
    decline: "Something else",
    ban: "Never again",
    ban_confirm: "Never suggest \"{title}\" again?",
    undo: "Not cooked",
    cooked: "Cooked",
    mark_cooked: "Mark as cooked",
    portions: "{n} portions",
    portion: "1 portion",
    kcal: "~{n} kcal",
    min: "{n} min",
    ingredients: "Ingredients",
    steps: "Steps",
    progress: "{done} of {total} cooked",
    no_bans: "No banned dishes.",
    unban: "Allow again",
    ban_title: "Ban a dish",
    ban_add: "Ban",
    today: "Today",
    tomorrow: "Tomorrow",
    nothing_today: "No more meals planned.",
    meals_per_day: "Meals",
    calories: "Calories",
    no_target: "no target",
    edit_settings: "Edit settings",
    origin_hint: "Where a value comes from: default, weekday, meal, or an entity.",
    col_portions: "Portions",
    col_effort: "Effort",
    col_health: "Health",
    effort_short_1: "low",
    effort_short_2: "medium",
    effort_short_3: "high",
    effort_1: "low effort",
    effort_2: "medium effort",
    effort_3: "high effort",
    health: "health {n}/5",
    slot_breakfast: "Breakfast",
    slot_lunch: "Lunch",
    slot_dinner: "Dinner",
    slot_snack: "Snack",
    not_loaded: "Meal Manager is not set up.",
    recipes: "{n} recipes available",
  },
  de: {
    title: "Essensplan",
    tab_plan: "Plan",
    tab_bans: "Gesperrt",
    tab_settings: "Einstellungen",
    planning: "Plane Mahlzeiten…",
    no_plan: "Noch kein Essensplan.",
    start: "Start",
    days: "Tage",
    create: "Essensplan erstellen",
    suggestion: "Vorschlag",
    suggestion_for: "Neuer Plan {from} – {to}",
    all_cooked: "Alles gekocht. Hier ist ein neuer Vorschlag.",
    all_cooked_no_draft: "Alles gekocht.",
    accept: "Übernehmen",
    discard: "Verwerfen",
    regenerate: "Neuer Vorschlag",
    new_plan: "Neuer Plan",
    shopping: "Einkaufsliste",
    shopping_added: "{count} Einträge zu {list} hinzugefügt.",
    shopping_none: "Nichts einzukaufen.",
    decline: "Etwas anderes",
    ban: "Nie wieder",
    ban_confirm: "\"{title}\" nie wieder vorschlagen?",
    undo: "Nicht gekocht",
    cooked: "Gekocht",
    mark_cooked: "Als gekocht markieren",
    portions: "{n} Portionen",
    portion: "1 Portion",
    kcal: "~{n} kcal",
    min: "{n} Min.",
    ingredients: "Zutaten",
    steps: "Zubereitung",
    progress: "{done} von {total} gekocht",
    no_bans: "Keine gesperrten Gerichte.",
    unban: "Wieder erlauben",
    ban_title: "Gericht sperren",
    ban_add: "Sperren",
    today: "Heute",
    tomorrow: "Morgen",
    nothing_today: "Keine weiteren Mahlzeiten geplant.",
    meals_per_day: "Mahlzeiten",
    calories: "Kalorien",
    no_target: "kein Ziel",
    edit_settings: "Einstellungen bearbeiten",
    origin_hint: "Herkunft eines Werts: Standard, Wochentag, Mahlzeit oder eine Entität.",
    col_portions: "Portionen",
    col_effort: "Aufwand",
    col_health: "Gesundheit",
    effort_short_1: "gering",
    effort_short_2: "mittel",
    effort_short_3: "hoch",
    effort_1: "wenig Aufwand",
    effort_2: "mittlerer Aufwand",
    effort_3: "viel Aufwand",
    health: "Gesundheit {n}/5",
    slot_breakfast: "Frühstück",
    slot_lunch: "Mittagessen",
    slot_dinner: "Abendessen",
    slot_snack: "Snack",
    not_loaded: "Meal Manager ist nicht eingerichtet.",
    recipes: "{n} Rezepte verfügbar",
  },
};

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const STYLE = `
  :host { display: block; }
  ha-card { overflow: hidden; }
  .wrap { padding: 12px 16px 16px; }
  .header { display: flex; align-items: center; gap: 8px; padding: 16px 16px 0; }
  .header h1 { font-size: 1.25rem; font-weight: 500; margin: 0; flex: 1; }
  .chip { font-size: 0.75rem; padding: 2px 10px; border-radius: 12px; background: var(--secondary-background-color); color: var(--secondary-text-color); }
  .tabs { display: flex; gap: 4px; padding: 8px 16px 0; border-bottom: 1px solid var(--divider-color); }
  .tab { flex: 1; border: none; background: none; padding: 10px 4px; font: inherit; color: var(--secondary-text-color); border-bottom: 2px solid transparent; cursor: pointer; }
  .tab.on { color: var(--primary-color); border-bottom-color: var(--primary-color); font-weight: 500; }
  button.btn { font: inherit; border: none; border-radius: 18px; padding: 8px 16px; min-height: 36px; cursor: pointer; background: var(--primary-color); color: var(--text-primary-color, #fff); }
  button.btn.flat { background: var(--secondary-background-color); color: var(--primary-text-color); }
  button.btn.warn { background: var(--error-color); color: #fff; }
  button.btn:disabled { opacity: 0.5; cursor: default; }
  .row-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
  .row-actions .btn { flex: 1 1 auto; }
  .banner { border-radius: 12px; padding: 12px; margin: 8px 0 12px; background: var(--secondary-background-color); }
  .banner.accent { border-left: 4px solid var(--primary-color); }
  .banner b { display: block; margin-bottom: 4px; }
  .error { color: var(--error-color); padding: 8px 0; }
  .info { color: var(--secondary-text-color); font-size: 0.9rem; padding: 8px 0; }
  .progress { height: 6px; border-radius: 3px; background: var(--secondary-background-color); overflow: hidden; margin: 4px 0 2px; }
  .progress > div { height: 100%; background: var(--success-color, #43a047); transition: width .3s; }
  .day { margin-top: 14px; }
  .day h2 { font-size: 0.85rem; text-transform: uppercase; letter-spacing: .04em; color: var(--secondary-text-color); margin: 0 0 6px; font-weight: 500; }
  .meal { border-radius: 12px; background: var(--card-background-color); border: 1px solid var(--divider-color); margin-bottom: 8px; }
  .meal.cooked .title { text-decoration: line-through; color: var(--secondary-text-color); }
  .meal-main { display: flex; align-items: center; gap: 10px; padding: 10px 12px; min-height: 48px; }
  .check { width: 36px; height: 36px; flex: none; border-radius: 50%; border: 2px solid var(--primary-color); background: none; cursor: pointer; display: grid; place-items: center; color: var(--primary-color); padding: 0; }
  .meal.cooked .check { background: var(--primary-color); color: var(--text-primary-color, #fff); }
  .check svg { width: 20px; height: 20px; fill: currentColor; }
  .body { flex: 1; min-width: 0; cursor: pointer; }
  .slot { font-size: 0.75rem; color: var(--secondary-text-color); }
  .title { font-weight: 500; overflow-wrap: anywhere; }
  .meta { font-size: 0.8rem; color: var(--secondary-text-color); }
  .details { padding: 0 12px 12px; font-size: 0.9rem; }
  .details h3 { font-size: 0.85rem; margin: 10px 0 4px; }
  .details ul, .details ol { margin: 0; padding-left: 20px; }
  .details li { margin: 2px 0; }
  .form { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 8px 0; }
  .form label { display: flex; flex-direction: column; font-size: 0.8rem; color: var(--secondary-text-color); gap: 4px; }
  input { font: inherit; padding: 8px; border-radius: 8px; border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color); min-height: 20px; }
  .ban-row { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-bottom: 1px solid var(--divider-color); }
  .ban-row span { flex: 1; }
  .ban-add { display: flex; gap: 8px; margin-top: 12px; }
  .ban-add input { flex: 1; min-width: 0; }
  table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
  td { padding: 4px 6px 4px 0; vertical-align: top; }
  tr.th td { color: var(--secondary-text-color); font-size: 0.75rem; }
  .origin { color: var(--secondary-text-color); font-size: 0.75rem; display: block; }
  .spinner { height: 3px; background: linear-gradient(90deg, transparent, var(--primary-color), transparent); background-size: 200% 100%; animation: slide 1.2s linear infinite; }
  @keyframes slide { from { background-position: 200% 0; } to { background-position: -200% 0; } }
  .toast { position: sticky; bottom: 8px; margin-top: 8px; padding: 10px 12px; border-radius: 8px; background: var(--primary-text-color); color: var(--card-background-color); font-size: 0.9rem; }
`;

const CHECK = '<svg viewBox="0 0 24 24"><path d="M9 16.17 4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>';

class MealManagerView extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._view = null;
    this._tab = "plan";
    this._expanded = new Set();
    this._busy = false;
    this._error = "";
    this._toast = "";
    this._config = {};
    this.shadowRoot.addEventListener("click", (ev) => this._onClick(ev));
  }

  set config(config) {
    this._config = config || {};
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._unsub && !this._failed) this._subscribe();
  }

  connectedCallback() {
    if (this._hass && !this._unsub) this._subscribe();
  }

  disconnectedCallback() {
    if (this._unsub) {
      this._unsub.then((unsub) => unsub()).catch(() => {});
      this._unsub = null;
    }
  }

  _subscribe() {
    if (!this._hass || !this.isConnected) return;
    this._unsub = this._hass.connection.subscribeMessage(
      (view) => {
        this._view = view;
        this._render();
      },
      { type: "meal_manager/subscribe" },
    );
    this._unsub.catch((err) => {
      this._unsub = null;
      this._failed = true;
      this._error = err.message || String(err);
      this._render();
    });
  }

  _t(key, vars = {}) {
    const lang = (this._hass?.locale?.language || this._hass?.language || "en").split("-")[0];
    const table = STRINGS[lang] || STRINGS.en;
    let text = table[key] ?? STRINGS.en[key] ?? key;
    for (const [name, value] of Object.entries(vars)) text = text.replace(`{${name}}`, value);
    return text;
  }

  _dayLabel(iso) {
    const today = this._view?.today;
    if (iso === today) return this._t("today");
    const tomorrow = new Date(`${today}T12:00:00`);
    tomorrow.setDate(tomorrow.getDate() + 1);
    if (iso === tomorrow.toISOString().slice(0, 10)) return this._t("tomorrow");
    const lang = this._hass?.locale?.language || "en";
    return new Date(`${iso}T12:00:00`).toLocaleDateString(lang, { weekday: "long", day: "numeric", month: "short" });
  }

  _shortDate(iso) {
    const lang = this._hass?.locale?.language || "en";
    return new Date(`${iso}T12:00:00`).toLocaleDateString(lang, { day: "numeric", month: "short" });
  }

  async _call(service, data = {}, returnResponse = false) {
    this._busy = true;
    this._error = "";
    this._render();
    try {
      return await this._hass.callService("meal_manager", service, data, undefined, false, returnResponse);
    } catch (err) {
      this._error = err.message || String(err);
      return null;
    } finally {
      this._busy = false;
      this._render();
    }
  }

  _showToast(text) {
    this._toast = text;
    this._render();
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => {
      this._toast = "";
      this._render();
    }, 4000);
  }

  async _onClick(ev) {
    const el = ev.target.closest("[data-action]");
    if (!el || this._busy) return;
    const { action, id, title } = el.dataset;
    const root = this.shadowRoot;
    switch (action) {
      case "tab":
        this._tab = el.dataset.tab;
        this._render();
        break;
      case "toggle":
        this._expanded.has(id) ? this._expanded.delete(id) : this._expanded.add(id);
        this._render();
        break;
      case "cooked":
        await this._call("mark_cooked", { meal_id: id, cooked: el.dataset.cooked !== "true" });
        break;
      case "decline":
        await this._call("decline_meal", { meal_id: id });
        break;
      case "ban":
        if (confirm(this._t("ban_confirm", { title }))) await this._call("ban_meal", { meal_id: id });
        break;
      case "unban":
        await this._call("unban_meal", { title });
        break;
      case "ban-title": {
        const input = root.querySelector("#ban-input");
        if (input?.value.trim()) await this._call("ban_meal", { title: input.value.trim() });
        break;
      }
      case "create": {
        const start = root.querySelector("#start")?.value;
        const days = Number(root.querySelector("#days")?.value);
        const data = {};
        if (start) data.start_date = start;
        if (days) data.days = days;
        await this._call("generate_plan", data);
        break;
      }
      case "regenerate":
        await this._call("generate_plan", { start_date: this._view.draft.start, days: this._view.draft.days });
        break;
      case "new-plan":
        await this._call("generate_plan", {});
        break;
      case "accept":
        await this._call("accept_plan");
        break;
      case "discard":
        await this._call("discard_plan");
        break;
      case "shopping": {
        const result = await this._call("add_to_shopping_list", {}, true);
        const response = result?.response;
        if (!response) break;
        if (!response.items.length) this._showToast(this._t("shopping_none"));
        else if (response.entity_id) {
          const name = this._hass.states[response.entity_id]?.attributes.friendly_name || response.entity_id;
          this._showToast(this._t("shopping_added", { count: response.items.length, list: name }));
        } else this._showToast(response.items.join(", "));
        break;
      }
      case "settings":
        history.pushState(null, "", "/config/integrations/integration/meal_manager");
        window.dispatchEvent(new CustomEvent("location-changed"));
        break;
    }
  }

  // --------------------------------------------------------------- render

  _render() {
    const root = this.shadowRoot;
    const focused = root.activeElement?.id;
    const values = {};
    for (const input of root.querySelectorAll("input[id]")) values[input.id] = input.value;

    const v = this._view;
    let body;
    if (!v) body = `<div class="spinner"></div>`;
    else if (!v.loaded) body = `<div class="wrap info">${this._t("not_loaded")}</div>`;
    else {
      const tabs = this._config.tabs === false ? "" : this._renderTabs();
      const content =
        this._tab === "bans" ? this._renderBans() : this._tab === "settings" ? this._renderSettings() : this._renderPlan();
      body = `${tabs}${v.generating || this._busy ? '<div class="spinner"></div>' : ""}<div class="wrap">
        ${this._error ? `<div class="error">${esc(this._error)}</div>` : ""}
        ${content}
        ${this._toast ? `<div class="toast">${esc(this._toast)}</div>` : ""}
      </div>`;
    }
    const title = this._config.title ?? this._t("title");
    const status = v?.active ? this._t("progress", { done: v.active.cooked, total: v.active.total }) : "";
    root.innerHTML = `<style>${STYLE}</style><ha-card>
      ${title ? `<div class="header"><h1>${esc(title)}</h1>${status ? `<span class="chip">${esc(status)}</span>` : ""}</div>` : ""}
      ${body}
    </ha-card>`;

    for (const [id, value] of Object.entries(values)) {
      const input = root.getElementById(id);
      if (input) input.value = value;
    }
    if (focused) root.getElementById(focused)?.focus();
  }

  _renderTabs() {
    const tab = (key) =>
      `<button class="tab ${this._tab === key ? "on" : ""}" data-action="tab" data-tab="${key}">${this._t(`tab_${key}`)}</button>`;
    return `<div class="tabs">${tab("plan")}${tab("bans")}${tab("settings")}</div>`;
  }

  _renderPlan() {
    const v = this._view;
    const parts = [];
    const active = v.active;
    const completed = active?.status === "completed";

    if (v.draft) {
      const last = new Date(`${v.draft.start}T12:00:00`);
      last.setDate(last.getDate() + v.draft.days - 1);
      parts.push(`<div class="banner accent">
        <b>${esc(completed ? this._t("all_cooked") : this._t("suggestion"))}</b>
        ${esc(this._t("suggestion_for", { from: this._shortDate(v.draft.start), to: this._shortDate(last.toISOString().slice(0, 10)) }))}
        <div class="row-actions">
          <button class="btn" data-action="accept">${this._t("accept")}</button>
          <button class="btn flat" data-action="regenerate">${this._t("regenerate")}</button>
          <button class="btn flat" data-action="discard">${this._t("discard")}</button>
        </div>
      </div>`);
      parts.push(this._renderMeals(v.draft.meals, true));
      if (!active) return parts.join("");
      parts.push(`<div class="day"><h2>${this._t("tab_plan")}</h2></div>`);
    } else if (completed) {
      parts.push(`<div class="banner accent"><b>${this._t("all_cooked_no_draft")}</b>
        <div class="row-actions"><button class="btn" data-action="new-plan" ${v.generating ? "disabled" : ""}>${this._t("new_plan")}</button></div></div>`);
    }

    if (!active) {
      if (!v.draft) parts.push(this._renderCreate());
      return parts.join("");
    }

    const pct = active.total ? Math.round((100 * active.cooked) / active.total) : 0;
    parts.push(`<div class="progress"><div style="width:${pct}%"></div></div>`);

    let meals = active.meals;
    const showDays = Number(this._config.days || 0);
    if (showDays > 0) {
      const end = new Date(`${v.today}T12:00:00`);
      end.setDate(end.getDate() + showDays - 1);
      const endIso = end.toISOString().slice(0, 10);
      meals = meals.filter((m) => m.day >= v.today && m.day <= endIso);
      if (!meals.length) parts.push(`<div class="info">${this._t("nothing_today")}</div>`);
    } else if (this._config.hide_past !== false) {
      meals = meals.filter((m) => m.day >= v.today || !m.cooked);
    }
    parts.push(this._renderMeals(meals, false));

    if (!v.draft) {
      parts.push(`<div class="row-actions">
        <button class="btn flat" data-action="shopping">${this._t("shopping")}</button>
        <button class="btn flat" data-action="new-plan" ${v.generating ? "disabled" : ""}>${this._t("new_plan")}</button>
      </div>`);
    }
    return parts.join("");
  }

  _renderCreate() {
    const v = this._view;
    return `<div class="info">${this._t("no_plan")} ${esc(this._t("recipes", { n: v.recipes }))}</div>
      <div class="form">
        <label>${this._t("start")}<input id="start" type="date" value="${esc(v.today)}"></label>
        <label>${this._t("days")}<input id="days" type="number" min="1" max="31" inputmode="numeric" value="${esc(v.default_days)}"></label>
      </div>
      <div class="row-actions"><button class="btn" data-action="create" ${v.generating ? "disabled" : ""}>${this._t("create")}</button></div>`;
  }

  _renderMeals(meals, draft) {
    const days = new Map();
    for (const meal of meals) {
      if (!days.has(meal.day)) days.set(meal.day, []);
      days.get(meal.day).push(meal);
    }
    return [...days.entries()]
      .map(
        ([day, list]) =>
          `<div class="day"><h2>${esc(this._dayLabel(day))}</h2>${list.map((m) => this._renderMeal(m, draft)).join("")}</div>`,
      )
      .join("");
  }

  _renderMeal(meal, draft) {
    const open = this._expanded.has(meal.id);
    const meta = [
      meal.portions === 1 ? this._t("portion") : this._t("portions", { n: meal.portions }),
      this._t("min", { n: meal.minutes }),
      this._t("kcal", { n: meal.kcal }),
      this._t(`effort_${meal.effort}`),
    ].join(" · ");
    const check = draft
      ? ""
      : `<button class="check" data-action="cooked" data-id="${esc(meal.id)}" data-cooked="${meal.cooked}"
          title="${this._t(meal.cooked ? "undo" : "mark_cooked")}" aria-label="${this._t(meal.cooked ? "undo" : "mark_cooked")}">${meal.cooked ? CHECK : ""}</button>`;
    const details = open
      ? `<div class="details">
          <div class="meta">${esc(this._t("health", { n: meal.health }))}${meal.tags.length ? " · " + esc(meal.tags.join(", ")) : ""}</div>
          ${meal.ingredients.length ? `<h3>${this._t("ingredients")}</h3><ul>${meal.ingredients
            .map((i) => `<li>${esc([i.quantity || "", i.unit === "pcs" ? "" : i.unit, i.name].filter(Boolean).join(" "))}</li>`)
            .join("")}</ul>` : ""}
          ${meal.steps.length ? `<h3>${this._t("steps")}</h3><ol>${meal.steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ol>` : ""}
          ${meal.cooked ? "" : `<div class="row-actions">
            <button class="btn flat" data-action="decline" data-id="${esc(meal.id)}">${this._t("decline")}</button>
            <button class="btn warn" data-action="ban" data-id="${esc(meal.id)}" data-title="${esc(meal.title)}">${this._t("ban")}</button>
          </div>`}
        </div>`
      : "";
    return `<div class="meal ${meal.cooked ? "cooked" : ""}">
      <div class="meal-main">${check}
        <div class="body" data-action="toggle" data-id="${esc(meal.id)}">
          <div class="slot">${esc(this._t(`slot_${meal.slot}`))}${meal.time ? " · " + esc(meal.time) : ""}</div>
          <div class="title">${esc(meal.title)}</div>
          <div class="meta">${esc(meta)}</div>
        </div>
      </div>${details}
    </div>`;
  }

  _renderBans() {
    const bans = this._view.bans;
    const list = bans.length
      ? bans
          .map(
            (b) => `<div class="ban-row"><span>${esc(b.title)}</span>
              <button class="btn flat" data-action="unban" data-title="${esc(b.title)}">${this._t("unban")}</button></div>`,
          )
          .join("")
      : `<div class="info">${this._t("no_bans")}</div>`;
    return `${list}<div class="ban-add"><input id="ban-input" placeholder="${esc(this._t("ban_title"))}" aria-label="${esc(this._t("ban_title"))}">
      <button class="btn warn" data-action="ban-title">${this._t("ban_add")}</button></div>`;
  }

  _renderSettings() {
    const origin = (r) => `<span class="origin">${esc(r.origin)}</span>`;
    const days = this._view.preview
      .map((d) => {
        const meals = d.meals
          .map(
            (m) => `<tr><td>${esc(this._t(`slot_${m.slot}`))}</td>
              <td>${esc(m.portions.value)}${origin(m.portions)}</td>
              <td>${esc(this._t(`effort_short_${m.effort.value}`))}${origin(m.effort)}</td>
              <td>${esc(m.health.value)}/5${origin(m.health)}</td>
              <td>${m.kcal_target ? esc(m.kcal_target) : "–"}</td></tr>`,
          )
          .join("");
        const kcal = d.calories.value ? `${d.calories.value} kcal` : this._t("no_target");
        return `<div class="day"><h2>${esc(this._dayLabel(d.day))}</h2>
          <div class="meta">${this._t("meals_per_day")}: ${esc(d.meals_per_day.value)} (${esc(d.meals_per_day.origin)}) ·
            ${this._t("calories")}: ${esc(kcal)} (${esc(d.calories.origin)})</div>
          <table><tr class="th"><td></td><td>${this._t("col_portions")}</td><td>${this._t("col_effort")}</td>
            <td>${this._t("col_health")}</td><td>kcal</td></tr>${meals}</table></div>`;
      })
      .join("");
    const edit = this._hass?.user?.is_admin
      ? `<div class="row-actions"><button class="btn flat" data-action="settings">${this._t("edit_settings")}</button></div>`
      : "";
    return `<div class="info">${this._t("origin_hint")}</div>${days}${edit}`;
  }
}

customElements.get("meal-manager-view") || customElements.define("meal-manager-view", MealManagerView);

class MealManagerCard extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
    if (!this._view) {
      this._view = document.createElement("meal-manager-view");
      this.appendChild(this._view);
    }
    this._view.config = this._config;
    if (this._hass) this._view.hass = this._hass;
  }

  set hass(hass) {
    this._hass = hass;
    if (this._view) this._view.hass = hass;
  }

  getCardSize() {
    return 6;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }

  static getStubConfig() {
    return { days: 1 };
  }
}

customElements.get("meal-manager-card") || customElements.define("meal-manager-card", MealManagerCard);

class MealManagerPanel extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
    this._ensure();
    this._view.hass = hass;
    this._menu.hass = hass;
  }

  set narrow(narrow) {
    this._narrow = narrow;
    this._ensure();
    this._menu.style.display = narrow ? "" : "none";
  }

  set panel(_panel) {}

  _ensure() {
    if (this._view) return;
    const style = document.createElement("style");
    style.textContent = `
      :host { display: block; background: var(--primary-background-color); min-height: 100vh; }
      .toolbar { display: flex; align-items: center; height: var(--header-height, 56px); padding: 0 8px; gap: 8px;
        background: var(--app-header-background-color, var(--primary-color)); color: var(--app-header-text-color, #fff);
        font-size: 20px; }
      .content { max-width: 720px; margin: 0 auto; padding: 8px 8px 24px; }`;
    this.attachShadow({ mode: "open" });
    const toolbar = document.createElement("div");
    toolbar.className = "toolbar";
    this._menu = document.createElement("ha-menu-button");
    this._menu.style.display = this._narrow ? "" : "none";
    const title = document.createElement("span");
    const lang = (this._hass?.locale?.language || "en").split("-")[0];
    title.textContent = (STRINGS[lang] || STRINGS.en).title;
    toolbar.append(this._menu, title);
    const content = document.createElement("div");
    content.className = "content";
    this._view = document.createElement("meal-manager-view");
    this._view.config = { title: "" };
    content.appendChild(this._view);
    this.shadowRoot.append(style, toolbar, content);
    this._menu.hass = this._hass;
    this._menu.narrow = this._narrow;
  }
}

customElements.get("meal-manager-panel") || customElements.define("meal-manager-panel", MealManagerPanel);

window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "meal-manager-card")) {
  window.customCards.push({
    type: "meal-manager-card",
    name: "Meal Manager",
    description: "Meal plan with cooked tracking, decline and ban.",
    preview: false,
  });
}
