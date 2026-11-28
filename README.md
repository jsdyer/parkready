# Park Ready

A fast, free BC park planning check at **[coolcode.ca/parkready](https://coolcode.ca/parkready/)**. Search the complete displayed, legally active BC Parks catalogue by name, location notes or activity. Filter by facilities and recorded notices, select a planning date, save parks on your device, and download a visit plan or results CSV.

<!-- coolcode:guide -->
Browse [BC park visit guides by region](https://coolcode.ca/parkready/records/) to compare entrances and facilities. At Golden Ears, for example, the gate instructions distinguish seasonal hours from access-road restrictions. Choose a visit date in the planner to check notices for that day. Read the published notices and check the recorded gate dates before following the official park link. A facility listing is a description, not a guarantee that it is available. No notice does not mean open or safe. Save parks locally for next time, copy a shareable plan link, or download a dated planning snapshot. Check the source timestamp and the official page again before travelling.
<!-- /coolcode:guide -->

## What the data means

- **Coverage:** all displayed, legally active protected areas returned by the official [BC Parks public API](https://bcparks.api.gov.bc.ca/api/protected-areas). It includes provincial parks, conservancies, ecological reserves and other protected-area types. Municipal, regional and national parks are outside this catalogue. Results are not limited to example searches.
- **Notices:** published records from [public-advisories](https://bcparks.api.gov.bc.ca/api/public-advisories), joined through their explicit protected-area identifiers. A notice may affect several parks or particular facilities; read its text. Effective, end and expiry dates remain visible. All captured notices remain available in the park view, including those outside the selected date window. Currently published notices are not a complete historical archive or a future forecast.
- **Dates:** planning dates and advisory instants follow the BC Parks date convention, UTC−7. Source date-only values retain their calendar date. A missing effective/end date is an unspecified window boundary. Gate dates match the explicit operating year; old or annually flagged records are never extrapolated into another year. Incomplete dates are not interpreted as year-round access. The selected day can overlap only part of an advisory's time window; use its exact timestamp when timing matters.
- **Facilities:** active facility descriptions, not live availability or booking inventory. Gate hours and dated operating windows do not override advisories. A recorded campfire ban/day-use pass flag is shown; absence of a flag is not permission or confirmation that no pass is needed.
- **Freshness:** an hourly GitHub Actions retrieval verifies every page of both datasets, validates the transformation and then updates `data/index.json` with `data/status.json`. A failed download, changed pagination or invalid payload fails the workflow and leaves the published last-good snapshot in place. The interface highlights snapshots older than six hours. BC Parks normally updates its advisories weekdays, 8:30 am–4:30 pm, excluding statutory holidays; our hourly check cannot make the original information more current. [Official advisories](https://bcparks.ca/active-advisories/).
- **Safety:** the app never infers “safe” or “open” from absent notices, stale data or a failed download. Check the official page, DriveBC and EmergencyInfoBC before travel.

Source fields follow the [official public API specification](https://github.com/bcgov/bcparks.ca/blob/main/infrastructure/kong/public-documentation.json). The current public service returns flat Strapi v5 records; its exposed fields differ from the internal CMS schema. HTML is converted to inert plain text; internal administrative notes are not collected. Original park content is attributed to BC Parks; this independent app is not a government service.

## Privacy and sharing

All filtering takes place in your browser. Saving a park stores only public park IDs under `coolcode:parkready:favourites:v1` on that device. Clearing saved parks removes them. Searches and selected dates appear in the shareable URL, so share only the query you intend to disclose. Favourite lists are not encoded in links. No logs, accounts, keys or paid services are required. Map links open OpenStreetMap only when clicked. CoolCode's anonymous tool-visit counter does not receive the search text or favourite IDs.

## Run and verify

Python 3.12+ and Node 24+ are used by CI. The build itself needs no third-party packages or network.

```sh
python3 scripts/refresh.py
node --test tests/*.test.mjs
python3 -m unittest discover -s tests -v
python3 scripts/build.py
python3 -m http.server 8000 --directory dist
```

For the browser smoke check:

```sh
python3 -m pip install -r tests/browser-requirements.txt
CHROMIUM_PATH=/usr/bin/google-chrome python3 tests/browser_smoke.py
```

`tests/browser_smoke.py` serves the built app at `/parkready/` and exercises a real source park, filters, date selection, saved parks, share state, downloads and narrow-screen layout. Without `CHROMIUM_PATH`, it uses an installed Playwright Chromium. Screenshots are produced in `browser-checks/`.

## Permanent park visit guides

The offline build joins reviewed destinations to the same source edition using BC Parks ORCS identifiers. Each region compares gate and facility records, and every park links to its official page, the date-aware planner and other destinations in its region. The guide shows notices whose effective and end dates cover the local date of the source check. The trip planner retains the other published notices. A park with no complete gate window for that operating year has no inferred season. The timestamp remains readable without JavaScript. The guide displays an additional age warning after the configured freshness interval when JavaScript is available.

To include another destination, find its numeric `id` in `data/index.json` and add a permanent ASCII slug mapped to that ID in the appropriate group in `config/guides.json`. Keep existing slugs when BC Parks changes a displayed name. Only a destination present in the validated source edition produces a page and sitemap entry. Run the normal tests and build below, then push the change to main. The existing hourly Pages workflow refreshes both interactive and permanent pages together.

## Publication and maintenance

`.github/workflows/pages.yml` runs on main pushes, pull requests, manual dispatch and hourly at minute 17 UTC. Main pushes, dispatches and scheduled runs retrieve the real source before tests, build and browser verification. Only a fully validated snapshot is committed and deployed. Pull requests validate the included snapshot without downloading. `data/status.json` is the small public freshness probe; `checked_at` means a successful complete source check, not a site's own update time.

`.github/workflows/schedule-guard.yml` separately renews only this repository's explicitly managed scheduled workflows (including itself), preserving intentional disablement. The CoolCode hub registers the collector and probe in its central schedule and watchdog inventory. GitHub's schedules may be delayed; the public timestamp is the evidence of the most recent successful check.

Edit `config/source.json` for pagination bounds, the stale threshold and example searches. Examples are suggestions only and do not restrict coverage. Source-host changes require reviewing the adapter. Keep `tool.json`, source notes, tests and the hub collector registry consistent when changing cadence, paths or source semantics. GitHub Pages uses GitHub Actions; the Cloudflare Worker routes `/parkready/` to the Pages project.

Software: MIT. Source content: BC Parks, linked and attributed above.
