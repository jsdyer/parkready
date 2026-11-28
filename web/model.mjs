export const fold = (value) =>
  String(value ?? "")
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
export function bcDay(now = new Date()) {
  return new Date(now.getTime() - 7 * 3600000).toISOString().slice(0, 10);
}
export function validDate(value) {
  return (
    /^\d{4}-\d{2}-\d{2}$/.test(value || "") &&
    !Number.isNaN(Date.parse(value)) &&
    new Date(value).toISOString().slice(0, 10) === value
  );
}
export function dateDay(value) {
  if (!value) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return validDate(value) ? value : null;
  const instant = new Date(value);
  return Number.isNaN(instant.getTime()) ? null : bcDay(instant);
}
export function relevant(advisory, date) {
  const start = dateDay(advisory.effective);
  const ends = [advisory.end, advisory.expires].filter(Boolean).map(dateDay);
  return (!start || start <= date) && ends.every((end) => end >= date);
}
export function windowLabel(notice) {
  if (!notice.relevant) return "Outside recorded dates";
  const end = notice.end || notice.expires;
  if (notice.effective && end) return "Window matches planning date";
  if (notice.effective) return "End date unreported";
  if (end) return "Effective date unreported";
  return "Effective and end dates unreported";
}
export function parkNotices(park, advisories, date) {
  return advisories
    .filter((a) => a.parks.includes(park.id))
    .map((a) => ({ ...a, relevant: relevant(a, date) }))
    .sort(
      (a, b) =>
        Number(b.relevant) - Number(a.relevant) ||
        b.urgency_rank - a.urgency_rank ||
        a.precedence - b.precedence ||
        a.title.localeCompare(b.title),
    );
}
export function gateWindows(park, date) {
  const year = Number(date.slice(0, 4));
  return park.dates.filter(
    (d) => d.kind === "Gate" && d.year === year && d.start && d.end,
  );
}
export function outsideGateDates(park, date) {
  const dates = gateWindows(park, date);
  return (
    dates.length > 0 && !dates.some((d) => d.start <= date && d.end >= date)
  );
}
export function summary(park, advisories, date) {
  const notices = parkNotices(park, advisories, date).filter((a) => a.relevant);
  const top = [...notices].sort((a, b) => a.precedence - b.precedence)[0];
  if (top && top.access && top.access.toLowerCase() !== "open")
    return {
      label: top.effective && (top.end || top.expires)
        ? top.access
        : `${top.access} notice · incomplete dates`,
      kind: top.effective && (top.end || top.expires) && top.access_group === "Closed" ? "closed" : "attention",
      count: notices.length,
    };
  if (outsideGateDates(park, date))
    return {
      label: "Outside listed gate dates",
      kind: "season",
      count: notices.length,
    };
  if (notices.length)
    return {
      label: `${notices.length} recorded notice${notices.length === 1 ? "" : "s"}`,
      kind: "attention",
      count: notices.length,
    };
  return { label: "Check official conditions", kind: "unknown", count: 0 };
}
export function filterParks(parks, advisories, filters = {}, favourites = []) {
  const q = fold(filters.q).trim();
  const words = q.split(/\s+/).filter(Boolean);
  return parks.filter((p) => {
    const search = fold(
      [p.name, p.type, p.location, ...p.activities, p.id].join(" "),
    );
    if (!words.every((w) => search.includes(w))) return false;
    if (filters.type && p.type !== filters.type) return false;
    if (
      filters.facility &&
      !p.facilities.some((f) => f.name === filters.facility)
    )
      return false;
    if (filters.saved && !favourites.includes(p.id)) return false;
    const notices = parkNotices(p, advisories, filters.date || bcDay()).filter(
      (a) => a.relevant,
    );
    if (filters.notice === "any" && !notices.length) return false;
    if (filters.notice === "high" && !notices.some((a) => a.urgency === "High"))
      return false;
    if (
      filters.notice === "closure" &&
      !notices.some((a) =>
        ["Closed", "Limited access", "Restricted"].includes(a.access_group),
      )
    )
      return false;
    if (
      filters.notice === "season" &&
      !outsideGateDates(p, filters.date || bcDay())
    )
      return false;
    return true;
  });
}
export function readState(search) {
  const p = new URLSearchParams(search);
  const date = p.get("date");
  return {
    q: (p.get("q") || "").slice(0, 200),
    type: p.get("type") || "",
    facility: p.get("facility") || "",
    notice: p.get("notice") || "",
    date: validDate(date) ? date : bcDay(),
    park: Number(p.get("park")) || null,
  };
}
export function stateQuery(filters, park) {
  const p = new URLSearchParams();
  for (const k of ["q", "type", "facility", "notice", "date"])
    if (filters[k]) p.set(k, filters[k]);
  if (park) p.set("park", park);
  return p.toString();
}
export function csvCell(value) {
  let text = String(value ?? "");
  if (/^(?:[\t\r]|\s*[=+\-@])/.test(text)) text = "'" + text;
  return '"' + text.replaceAll('"', '""') + '"';
}
export function exportCSV(parks, advisories, date, checkedAt) {
  return [
    [
      "Park",
      "Type",
      "Published notices to review and their date coverage",
      "Gate dates for year",
      "Planning date",
      "Source checked",
      "Official page",
    ],
    ...parks.map((p) => [
      p.name,
      p.type,
      parkNotices(p, advisories, date)
        .filter((a) => a.relevant)
        .map((a) => `${a.title} (${windowLabel(a)})`)
        .join(" | "),
      gateWindows(p, date)
        .map((d) => `${d.start} to ${d.end}`)
        .join(" | "),
      date,
      checkedAt,
      p.url,
    ]),
  ]
    .map((row) => row.map(csvCell).join(","))
    .join("\r\n");
}
export function tripNotes(park, advisories, date, checkedAt) {
  const notes = parkNotices(park, advisories, date);
  return `${park.name}\nPlanning date: ${date} (BC Parks date, UTC−7)\nSource checked: ${checkedAt}\nOfficial page: ${park.url}\n\nThis is a saved planning snapshot, not live opening or safety confirmation. Check the official page before travel.\n\nGate dates for ${date.slice(0, 4)}:\n${
    gateWindows(park, date)
      .map((d) => `${d.start} to ${d.end}`)
      .join("\n") || "No complete gate dates listed for this year."
  }\n${park.gate.note || ""}\n\nPublished notices:\n${notes.map((a) => `${windowLabel(a)}: ${a.title}\n${a.access || ""} · ${a.urgency}\n${a.description}`).join("\n\n") || "No published notices captured for this park. This does not confirm unrestricted access."}\n\nFacilities listed (availability may vary):\n${park.facilities.map((f) => f.name).join(", ")}`;
}
