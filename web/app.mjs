import {
  bcDay,
  validDate,
  readState,
  stateQuery,
  filterParks,
  parkNotices,
  summary,
  gateWindows,
  exportCSV,
  tripNotes,
} from "./model.mjs";
const $ = (id) => document.getElementById(id),
  key = "coolcode:parkready:favourites:v1";
const el = (tag, text, className) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
};
const button = (text, action, className = "quiet") => {
  const b = el("button", text, className);
  b.type = "button";
  b.addEventListener("click", action);
  return b;
};
const link = (text, url, className) => {
  const a = el("a", text, className);
  a.href = url;
  a.target = "_blank";
  a.rel = "noopener noreferrer";
  return a;
};
const para = (parent, text, cls) => parent.append(el("p", text, cls));
const guidePaths = JSON.parse($("guide-paths").textContent);
let dataset,
  parks = [],
  advisories = [],
  filters = readState(location.search),
  selected = filters.park,
  limit = 30,
  results = [],
  favourites = [];
try {
  const saved = JSON.parse(localStorage.getItem(key) || "[]");
  if (Array.isArray(saved))
    favourites = [...new Set(saved.filter(Number.isInteger))];
} catch {}
function saveFavourites() {
  try {
    localStorage.setItem(key, JSON.stringify(favourites));
    $("storage-status").textContent = "";
  } catch {
    $("storage-status").textContent =
      "Your browser could not save these changes. This list will only be available until this page closes.";
  }
}

function download(content, name, type) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = el("a");
  a.href = url;
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
function updateURL() {
  history.replaceState(
    null,
    "",
    `${location.pathname}?${stateQuery(filters, selected)}`,
  );
}
function setOptions(id, values) {
  const select = $(id);
  for (const value of values.sort((a, b) => a.localeCompare(b))) {
    const option = el("option", value);
    option.value = value;
    select.append(option);
  }
  select.value = filters[id] || "";
  if (!select.value) filters[id] = "";
}
function dateText(value) {
  return value
    ? new Date(value).toLocaleString("en-CA", {
        timeZone: "UTC",
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      }) + " UTC"
    : "Not supplied";
}
function freshness() {
  const age = (Date.now() - Date.parse(dataset.checked_at)) / 3600000;
  const old = age > dataset.stale_after_hours;
  const target = $("freshness");
  target.className = `source-note ${old ? "stale" : ""}`;
  target.textContent = `${old ? "Older snapshot — check the official page before relying on these details. " : ""}Source successfully checked ${dateText(dataset.checked_at)}. Hourly refresh; source notices may change between checks.`;
}
function choose(id, focus = false) {
  selected = id;
  updateURL();
  renderDetails();
  renderCards();
  if (focus && matchMedia("(max-width: 680px)").matches) {
    $("details").scrollIntoView({ behavior: "smooth", block: "start" });
    $("details").focus({ preventScroll: true });
  }
}
function renderCards() {
  const container = $("list");
  container.replaceChildren();
  $("count").textContent =
    `${results.length.toLocaleString()} ${results.length === 1 ? "park" : "parks"}`;
  $("saved-count").textContent = favourites.length;
  $("export").disabled = !results.length;
  for (const p of results.slice(0, limit)) {
    const s = summary(p, advisories, filters.date);
    const card = button("", () => choose(p.id, true), "park-card");
    card.setAttribute("aria-pressed", String(p.id === selected));
    card.append(
      el("span", p.type, "park-type"),
      el("strong", p.name),
      el("span", s.label, `badge ${s.kind}`),
    );
    if (favourites.includes(p.id))
      card.append(el("span", "★ Saved", "saved-label"));
    container.append(card);
  }
  if (!results.length) {
    const empty = el("div", undefined, "empty");
    empty.append(
      el("h3", "No matching parks"),
      el(
        "p",
        "Try a shorter search, a different facility, or clear your filters.",
      ),
    );
    container.append(empty);
  }
  $("more").hidden = results.length <= limit;
  $("more").textContent =
    `Show ${Math.min(30, Math.max(0, results.length - limit))} more parks`;
}
function render() {
  if (!dataset) return;
  results = filterParks(parks, advisories, filters, favourites);
  renderCards();
  renderDetails();
  updateURL();
}
function section(title) {
  const s = el("section", undefined, "detail-section");
  s.append(el("h3", title));
  return s;
}
function renderDetails() {
  if (!selected) return;
  const p = parks.find((x) => x.id === selected);
  if (!p) {
    selected = null;
    return;
  }
  const target = $("details");
  target.replaceChildren();
  const s = summary(p, advisories, filters.date);
  if (!results.some((result) => result.id === p.id))
    para(
      target,
      "Selected park is outside your current result filters.",
      "callout",
    );
  target.append(
    el("p", p.type, "park-type"),
    el("h2", p.name),
    el("span", s.label, `badge ${s.kind}`),
  );
  para(
    target,
    `Planning for ${filters.date}. This is recorded information, not confirmation of access.`,
    "small",
  );
  const actions = el("div", undefined, "actions");
  actions.append(
    link("Official park page ↗", p.url, "primary"),
    button(favourites.includes(p.id) ? "★ Remove saved" : "☆ Save park", () => {
      favourites = favourites.includes(p.id)
        ? favourites.filter((id) => id !== p.id)
        : [...favourites, p.id];
      saveFavourites();
      render();
    }),
  );
  actions.append(
    button("Copy plan link", async (event) => {
      const target = event.currentTarget;
      try {
        await navigator.clipboard.writeText(location.href);
        target.textContent = "Link copied";
      } catch {
        target.textContent = "Copy address from browser";
      }
    }),
    button("Download plan", () =>
      download(
        tripNotes(p, advisories, filters.date, dataset.checked_at),
        `parkready-${p.id}-${filters.date}.txt`,
        "text/plain;charset=utf-8",
      ),
    ),
  );
  if (guidePaths[p.id]) {
    const guide = el("a", "Park visit guide");
    guide.href = "./records/" + guidePaths[p.id] + "/";
    actions.append(guide);
  }
  if (p.coordinates)
    actions.append(
      link(
        "View location ↗",
        `https://www.openstreetmap.org/?mlat=${p.coordinates[0]}&mlon=${p.coordinates[1]}#map=12/${p.coordinates[0]}/${p.coordinates[1]}`,
      ),
    );
  target.append(actions);
  if (p.location) {
    const location = el("details");
    location.append(
      el("summary", "Location and getting there"),
      el("p", p.location, "preserve"),
    );
    target.append(location);
  }
  const noticeSection = section("Published notices");
  const notes = parkNotices(p, advisories, filters.date);
  para(
    noticeSection,
    `${notes.filter((a) => a.relevant).length} recorded windows match your planning date. Future conditions and unpublished changes cannot be predicted.`,
    "small",
  );
  if (!notes.length)
    para(
      noticeSection,
      "No published notices were captured for this park. That does not confirm unrestricted access, open facilities or safe conditions.",
      "callout",
    );
  for (const a of notes) {
    const box = el(
      "article",
      undefined,
      `notice ${a.urgency === "High" ? "urgent" : ""}`,
    );
    box.append(
      el(
        "span",
        a.relevant
          ? "Window matches planning date"
          : "Outside recorded date window",
        `notice-window ${a.relevant ? "" : "muted"}`,
      ),
      el("h4", a.title),
    );
    para(
      box,
      [a.urgency + " urgency", a.access, a.event].filter(Boolean).join(" · "),
      "notice-meta",
    );
    para(box, a.description, "preserve");
    const dates = el("dl", undefined, "dates");
    for (const [label, value] of [
      ["Effective", a.effective],
      ["Ends", a.end],
      ["Expires", a.expires],
      ["Source updated", a.updated_at],
    ])
      if (value) {
        dates.append(
          el("dt", label),
          el("dd", value.length === 10 ? value : dateText(value)),
        );
      }
    box.append(dates);
    if (a.reservations_affected)
      para(box, "Reservations affected — see the official notice.", "small");
    for (const l of a.links) box.append(link(l.title + " ↗", l.url));
    noticeSection.append(box);
  }
  target.append(noticeSection);
  const gates = section("Gate dates and operating notes");
  const windows = gateWindows(p, filters.date);
  if (windows.length) {
    for (const d of windows) para(gates, `${d.start} → ${d.end}`, "date-range");
    para(
      gates,
      "Recorded gate date windows for " +
        filters.date.slice(0, 4) +
        ". Dates do not override closures or notices.",
      "small",
    );
  } else
    para(
      gates,
      `No complete gate dates captured for ${filters.date.slice(0, 4)}. Check the official page; missing dates do not mean year-round access.`,
      "callout",
    );
  const gate = p.gate;
  const hours = gate.all_day
    ? "Gate hours listed as 24 hours."
    : gate.start && gate.end
      ? `Listed gate hours: ${gate.start.slice(0, 5)}–${gate.end.slice(0, 5)}.`
      : gate.dawn || gate.dusk
        ? `Listed gate hours: ${gate.dawn ? "opens at dawn" : ""}${gate.dawn && gate.dusk ? ", " : ""}${gate.dusk ? "closes at dusk" : ""}.`
        : "";
  if (hours) para(gates, hours);
  if (gate.note) para(gates, gate.note, "preserve");
  if (p.operating_note) para(gates, p.operating_note, "preserve");
  const otherDates = p.dates.filter(
    (d) => d.kind !== "Gate" && d.year === Number(filters.date.slice(0, 4)),
  );
  if (otherDates.length) {
    const list = el("details");
    list.append(el("summary", "Other recorded operating dates"));
    for (const d of otherDates)
      para(
        list,
        `${d.kind}: ${d.start || "Not supplied"} → ${d.end || "Not supplied"}`,
      );
    gates.append(list);
  }
  target.append(gates);
  if (p.day_pass) {
    const pass = section("Day-use passes");
    para(
      pass,
      "The park record flags a day-use pass requirement. Check the official page for dates, locations and booking rules.",
    );
    pass.append(link("Check pass information ↗", p.day_pass_url || p.url));
    target.append(pass);
  }
  if (p.campfire_ban) {
    const fire = section("Campfire restriction recorded");
    para(
      fire,
      "The source flags a campfire ban. Check official fire restrictions immediately before your visit.",
      "warning",
    );
    target.append(fire);
  }
  const facilities = section("Facilities listed");
  para(
    facilities,
    "These describe park facilities, not their current availability. Check notices for affected areas and facilities.",
    "small",
  );
  if (!p.facilities.length)
    para(
      facilities,
      "No facility descriptions captured. See the official park page.",
    );
  for (const f of p.facilities) {
    const d = el("details");
    d.append(
      el("summary", f.name),
      el("p", f.detail || "No description supplied.", "preserve"),
    );
    facilities.append(d);
  }
  target.append(facilities);
  if (p.activities.length) {
    const activities = section("Activities listed");
    para(activities, p.activities.join(" · "));
    target.append(activities);
  }
  para(
    target,
    `Catalogue checked ${dateText(dataset.checked_at)}. Park record updated ${dateText(p.updated_at)}.`,
    "small",
  );
}
async function start() {
  try {
    const response = await fetch("./data/index.json", { cache: "no-cache" });
    if (!response.ok) throw new Error("The snapshot could not be downloaded.");
    dataset = await response.json();
    if (
      dataset.schema_version !== 1 ||
      !Array.isArray(dataset.parks) ||
      !dataset.parks.length ||
      !Array.isArray(dataset.advisories) ||
      !Number.isFinite(Date.parse(dataset.checked_at))
    )
      throw new Error("The snapshot could not be read.");
    parks = dataset.parks;
    advisories = dataset.advisories;
    favourites = favourites.filter((id) => parks.some((p) => p.id === id));
    $("stats").textContent =
      `${parks.length.toLocaleString()} protected areas · ${advisories.length.toLocaleString()} published notices · Free to use`;
    $("search").value = filters.q;
    $("date").value = filters.date;
    $("notice").value = filters.notice;
    if (!$("notice").value) filters.notice = "";
    setOptions("type", [...new Set(parks.map((p) => p.type))]);
    setOptions("facility", [
      ...new Set(parks.flatMap((p) => p.facilities.map((f) => f.name))),
    ]);
    for (const name of dataset.examples || [])
      $("examples").append(
        button(
          name,
          () => {
            filters.q = name;
            $("search").value = name;
            limit = 30;
            render();
          },
          "example",
        ),
      );
    freshness();
    setInterval(freshness, 60000);
    render();
  } catch (error) {
    $("stats").textContent = "Catalogue unavailable";
    $("freshness").className = "source-note stale";
    $("freshness").replaceChildren(
      el("span", `${error.message} `),
      link("Check the official BC Parks website ↗", "https://bcparks.ca/"),
    );
    $("list").append(
      el(
        "p",
        "Try again later. No conditions have been inferred from this failed download.",
      ),
    );
  }
}
for (const [id, event] of [
  ["search", "input"],
  ["date", "change"],
  ["type", "change"],
  ["facility", "change"],
  ["notice", "change"],
  ["saved", "change"],
])
  $(id).addEventListener(event, () => {
    const value = $(id).value;
    if (id === "date" && !validDate(value)) return;
    filters[id === "search" ? "q" : id] =
      id === "saved" ? $(id).checked : value;
    limit = 30;
    render();
  });
$("reset").addEventListener("click", () => {
  filters = {
    q: "",
    type: "",
    facility: "",
    notice: "",
    date: bcDay(),
    saved: false,
  };
  for (const id of ["search", "type", "facility", "notice"]) $(id).value = "";
  $("date").value = filters.date;
  $("saved").checked = false;
  limit = 30;
  render();
});
$("more").addEventListener("click", () => {
  limit += 30;
  renderCards();
});
$("export").addEventListener("click", () =>
  download(
    exportCSV(results, advisories, filters.date, dataset.checked_at),
    "parkready-results.csv",
    "text/csv;charset=utf-8",
  ),
);
$("clear-saved").addEventListener("click", () => {
  favourites = [];
  saveFavourites();
  render();
});
window.addEventListener("popstate", () => {
  filters = { ...readState(location.search), saved: $("saved").checked };
  selected = filters.park;
  $("search").value = filters.q;
  for (const id of ["date", "type", "facility", "notice"])
    $(id).value = filters[id];
  render();
});
start();
