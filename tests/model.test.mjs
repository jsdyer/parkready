import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  bcDay,
  dateDay,
  validDate,
  relevant,
  gateWindows,
  outsideGateDates,
  summary,
  filterParks,
  readState,
  stateQuery,
  exportCSV,
  tripNotes,
} from "../web/model.mjs";
const park = {
  id: 1,
  name: "A Hidden Place",
  type: "Park",
  location: "Nanaimo",
  url: "https://bcparks.ca/test/",
  activities: ["Canoeing"],
  facilities: [{ name: "Water", detail: "Seasonal" }],
  dates: [
    {
      kind: "Gate",
      year: 2025,
      start: "2025-05-01",
      end: "2025-09-30",
      annual: true,
    },
    { kind: "Gate", year: 2026, start: "2026-05-01", end: "2026-10-31" },
  ],
  gate: { note: "Check hours" },
};
const notice = {
  id: 2,
  title: "Access change",
  description: "Bridge closed",
  parks: [1],
  effective: "2026-06-01",
  end: "2026-06-02",
  expires: null,
  access: "Full closure",
  access_group: "Closed",
  precedence: 10,
  urgency: "High",
  urgency_rank: 3,
};
test("date-only boundaries stay on the recorded date and instants use UTC−7", () => {
  assert.equal(dateDay("2026-11-24"), "2026-11-24");
  assert.equal(dateDay("2026-11-24T01:00:00Z"), "2026-11-23");
  assert.equal(bcDay(new Date("2026-11-24T07:00:00Z")), "2026-11-24");
  assert.ok(!validDate("2026-02-30"));
  assert.ok(!validDate("bad"));
  assert.equal(dateDay("bad"), null);
  assert.equal(dateDay("2026-02-30"), null);
});
test("published advisory windows include boundary dates and respect both expiry and end", () => {
  assert.ok(relevant(notice, "2026-06-01"));
  assert.ok(relevant(notice, "2026-06-02"));
  assert.ok(!relevant(notice, "2026-06-03"));
  assert.ok(!relevant({ ...notice, expires: "2026-05-31" }, "2026-06-01"));
  assert.ok(relevant({ ...notice, effective: null, end: null }, "2027-01-01"));
});
test("gates use exact operating years and never extrapolate annual windows", () => {
  assert.equal(gateWindows(park, "2026-07-01")[0].end, "2026-10-31");
  assert.equal(gateWindows(park, "2027-07-01").length, 0);
  assert.ok(outsideGateDates(park, "2026-11-01"));
  assert.ok(!outsideGateDates(park, "2027-11-01"));
  assert.ok(!outsideGateDates(park, "2026-10-31"));
});
test("no notice or missing dates never becomes an open/safe judgment", () => {
  assert.equal(
    summary(park, [], "2027-07-01").label,
    "Check official conditions",
  );
  assert.equal(summary(park, [notice], "2026-06-01").kind, "closed");
  assert.equal(
    summary(
      park,
      [{ ...notice, access: "Open", access_group: "Open" }],
      "2026-06-01",
    ).kind,
    "attention",
  );
});
test("arbitrary catalogue parks, accent-folded search, facilities and private saved filter", () => {
  const p = { ...park, name: "Élysée Hidden Place" };
  assert.equal(
    filterParks([p], [], { q: "elysee", date: "2027-01-01" }).length,
    1,
  );
  assert.equal(
    filterParks([p], [], { q: "canoeing", facility: "Water", saved: true }, [1])
      .length,
    1,
  );
  assert.equal(filterParks([p], [], { saved: true }, []).length, 0);
  assert.equal(
    filterParks([p], [notice], { notice: "high", date: "2026-06-03" }).length,
    0,
  );
});
test("shared state excludes favourites and validates dates", () => {
  const query = stateQuery(
    { q: "Hidden Place", date: "2026-05-20", saved: true },
    1,
  );
  assert.ok(!query.includes("saved"));
  assert.equal(readState(query).q, "Hidden Place");
  assert.equal(readState(query).park, 1);
  assert.notEqual(readState("?date=2026-02-30").date, "2026-02-30");
});
test("downloads preserve source evidence and neutralize spreadsheet formulas", () => {
  const csv = exportCSV(
    [{ ...park, name: "=1+1" }],
    [notice],
    "2026-06-01",
    "2026-05-31T00:00:00Z",
  );
  assert.match(csv, /"'=1\+1"/);
  assert.match(csv, /Access change/);
  assert.match(csv, /2026-05-31T00:00:00Z/);
  assert.match(
    tripNotes(park, [notice], "2026-06-01", "checked"),
    /not live opening or safety confirmation/,
  );
});
test("real captured source supports arbitrary names and consistent complete joins", () => {
  const data = JSON.parse(
    readFileSync(new URL("../data/index.json", import.meta.url)),
  );
  assert.ok(data.parks.length > 100);
  const last = data.parks.at(-1);
  assert.ok(
    filterParks(data.parks, data.advisories, {
      q: last.name,
      date: "2026-11-24",
    }).some((p) => p.id === last.id),
  );
  const ids = new Set(data.parks.map((p) => p.id));
  assert.equal(ids.size, data.parks.length);
  assert.ok(data.advisories.every((a) => a.parks.every((id) => ids.has(id))));
  assert.ok(data.parks.some((p) => p.name.includes("Golden Ears")));
});

test("closure filter includes inaccessible parks and trails with official limited-access grouping", () => {
  for (const access of ["Inaccessible", "Trail access affected"])
    assert.equal(
      filterParks(
        [park],
        [{ ...notice, access, access_group: "Limited access" }],
        { notice: "closure", date: "2026-06-01" },
      ).length,
      1,
    );
});
