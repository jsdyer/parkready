"""Render park and regional visit guides from the same validated edition as the planner."""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from html import escape
import json
import re
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

BC = timezone(timedelta(hours=-7))
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
PRIORITY = ["Drinking water", "Pit or flush toilets", "Accessibility information", "Showers",
            "Boat launch", "Picnic areas", "Electrical hook-ups", "Sani-station"]
ADVISORIES = "https://bcparks.ca/active-advisories/"


def a(url, label):
    return f'<a href="{escape(url, quote=True)}">{escape(label)}</a>'


def paragraphs(value):
    return ''.join(f'<p>{escape(line)}</p>' for line in value.splitlines() if line.strip())


def day(value):
    if not value:
        return None
    if len(value) == 10:
        return date.fromisoformat(value)
    return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(BC).date()


def human_date(value):
    return value.strftime('%b %d, %Y').replace(' 0', ' ')


def checked_time(snapshot):
    instant = datetime.fromisoformat(snapshot['checked_at'].replace('Z', '+00:00')).astimezone(BC)
    return f'{human_date(instant.date())} at {instant:%H:%M} (UTC−7)'


def relevant(notice, when):
    start = day(notice['effective'])
    ends = [day(value) for value in (notice['end'], notice['expires']) if value]
    return (not start or start <= when) and all(when <= end for end in ends)


def gates(park, year):
    return sorted({(r['start'], r['end']) for r in park['dates']
                   if r['kind'] == 'Gate' and r['year'] == year and r['start'] and r['end']})


def hours(park):
    gate = park['gate']
    if gate['present'] is not True:
        return ''
    if gate['all_day']:
        return 'BC Parks lists 24-hour gate hours.'
    start = 'dawn' if gate['dawn'] else (gate['start'] or '')[:5]
    end = 'dusk' if gate['dusk'] else (gate['end'] or '')[:5]
    if start and end:
        return f'BC Parks lists gate hours from {start} to {end}.'
    return ''


def facilities(park):
    notes = {f['name']: f['detail'] for f in park['facilities'] if f['detail']}
    return [(k, notes[k]) for k in [*PRIORITY, *sorted(notes.keys() - set(PRIORITY))] if k in notes]


def facilities_phrase(park, n=3):
    return ', '.join(name.lower() for name, _ in facilities(park)[:n])


def facility_anchor(name):
    return 'facility-' + re.sub(r'[^a-z0-9]+', '-', name.casefold()).strip('-')


def gate_hint(park, year):
    if hours(park):
        return hours(park)
    if park['gate']['note']:
        return 'Seasonal or site-specific instructions. Read the gate note for your entrance.'
    if gates(park, year):
        return f'Gate dates supplied for {year}'
    return 'Confirm entrance arrangements with BC Parks'


def stamp(snapshot):
    return (f'<p class="edition">BC Parks catalogue checked <time datetime="{escape(snapshot["checked_at"])}">'
            f'{checked_time(snapshot)}</time>. <span data-age="{escape(snapshot["checked_at"])}" '
            f'data-hours="{int(snapshot["stale_after_hours"])}"></span></p>')


def notices_block(items, when):
    matching = sorted((x for x in items if relevant(x, when)),
                      key=lambda x: (-x['urgency_rank'], x['precedence'], x['title'].casefold()))
    body = ['<section><h2>Notices for the date checked</h2>']
    if matching:
        body.append(f'<p>These published notices include {human_date(when)} in their recorded date windows. '
                    'A notice can apply to one trail, entrance or campground.</p><ul class="notice-list">')
        for notice in matching:
            dates = []
            for key, label in [('effective', 'Effective'), ('end', 'Ends'), ('expires', 'Expires')]:
                if notice[key]:
                    dates.append(label + ' ' + human_date(day(notice[key])))
            if not notice['end'] and not notice['expires']:
                dates.append('End date unspecified')
            body.append(f'<li><strong>{escape(notice["title"])}</strong><br>{escape(" · ".join(dates))}</li>')
        body.append('</ul>')
    else:
        body.append(f'<p>No park-specific notice in this edition has a date window covering {human_date(when)}. '
                    'Confirm current access and trail conditions with BC Parks before leaving.</p>')
    body.append(a(ADVISORIES, 'Check the official BC Parks advisories') + '</section>')
    return ''.join(body)


def park_content(park, items, snapshot, peers, group):
    when = day(snapshot['checked_at'])
    notes = facilities(park)
    caption = facilities_phrase(park)
    body = [f'<p class="trail">{a("../", "All BC park guides")} / {a("../"+group["slug"]+"/", group["name"])}</p>',
            f'<h1>{escape(park["name"])} visit guide</h1>']
    if caption:
        body.append(f'<p class="lead">Plan your stop with the park’s entrance information and its notes on '
                    f'{escape(caption)}.</p>')
    else:
        body.append('<p class="lead">Plan your arrival with park-specific access details and dated notices.</p>')
    body += [f'<p class="actions">{a("../../?"+urlencode({"park": park["id"]})+"#details", "Check a visit date or save this park")}'
             f'{a(park["url"], "Check the official park page")}</p>', stamp(snapshot),
             notices_block(items, when), '<section><h2>Entrance and gate information</h2>']
    specific = hours(park)
    if specific:
        body.append(paragraphs(specific))
    body.append(paragraphs(park['gate']['note']))
    windows = gates(park, when.year)
    if windows:
        body.append(f'<p>Recorded gate dates for the {when.year} operating year</p><ul>')
        for start, end in windows:
            body.append(f'<li>{human_date(day(start))} to {human_date(day(end))}</li>')
        body.append('</ul><p>Weather and notices can affect access during a recorded season.</p>')
    else:
        body.append(f'<p>The catalogue has no complete gate date range for the {when.year} operating year. '
                    'Check the entrance you plan to use.</p>')
    if park['day_pass']:
        body.append('<p>BC Parks flags a day-use pass requirement. ' +
                    a(park['day_pass_url'] or park['url'], 'Check covered dates and trailheads') + '.</p>')
    if park['location']:
        body.append(f'<details><summary>Getting there · BC Parks directions</summary>{paragraphs(park["location"])}</details>')
    body.append('</section>')
    if notes:
        body.append('<section><h2>What to expect at the park</h2><p>Read the BC Parks facility notes for locations, '
                    'seasonal limits and accessible options. Confirm availability with the park before travelling.</p>')
        for name, detail in notes:
            body.append(f'<details id="{facility_anchor(name)}"><summary>{escape(name)}</summary>{paragraphs(detail)}</details>')
        body.append('</section>')
    body.append('<section><h2>Compare other parks</h2><ul>')
    for slug, other in peers:
        if other['id'] != park['id']:
            body.append(f'<li>{a("../"+slug+"/", other["name"])}</li>')
    body += ['</ul>', a('../'+group['slug']+'/', 'Compare parks in '+group['name']), '</section>']
    return ''.join(body)


def region_content(group, rows, snapshot):
    current = day(snapshot['checked_at'])
    body = [f'<p class="trail">{a("../", "All BC park guides")}</p>',
            f'<h1>{escape(group["name"])} park trip planner</h1><p class="lead">{escape(group["intro"])}</p>',
            stamp(snapshot)]
    facility_links = []
    for topic in ['Drinking water', 'Accessibility information', 'Showers', 'Electrical hook-ups', 'Boat launch']:
        matches = [a('../'+slug+'/#'+facility_anchor(topic), park['name']) for slug, park in rows
                   if any(name == topic for name, _ in facilities(park))]
        if matches:
            facility_links.append(f'<details><summary>{escape(topic)} notes ({len(matches)} parks)</summary>'
                                  + '<ul>' + ''.join(f'<li>{link}</li>' for link in matches) + '</ul></details>')
    if facility_links:
        body.append('<section><h2>Find a facility for your trip</h2><p>Choose a topic to jump to the park’s own '
                    'instructions. Some notes describe seasonal availability or a service at only one campground.</p>'
                    + ''.join(facility_links) + '</section>')
    body.append('<section><h2>Compare park stops</h2><p>Choose a park for its exact gate instructions, '
                'dated advisories and facility descriptions.</p><ul class="stops">')
    for slug, park in rows:
        notes = facilities_phrase(park, 4)
        label = f'<p>Facility notes cover {escape(notes)}.</p>' if notes else ''
        body.append(f'<li><h3>{a("../"+slug+"/", park["name"])}</h3><p>{escape(gate_hint(park, current.year))}</p>{label}</li>')
    body.append('</ul></section>')
    return ''.join(body)


def write_guides(stage, root, snapshot, tool, home, on_coolcode):
    groups = json.loads((root / 'config/guides.json').read_text(encoding='utf-8'))
    parks = {p['id']: p for p in snapshot['parks']}
    notices = defaultdict(list)
    for item in snapshot['advisories']:
        for park_id in item['parks']:
            notices[park_id].append(item)
    canonical_base = 'https://coolcode.ca' + tool['url'] if on_coolcode else ''
    paths, assigned = set(), {}
    sitemap = ET.Element('urlset', xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")

    def emit(slug, title, description, content):
        if slug and (not SLUG.fullmatch(slug) or slug in paths):
            raise ValueError('A guide has an invalid or duplicate slug')
        paths.add(slug)
        prefix = '../../' if slug else '../'
        path = 'records/' + (slug+'/' if slug else '')
        target = stage / path
        target.mkdir(parents=True, exist_ok=True)
        canonical = ''
        metrics = ''
        if on_coolcode:
            url = canonical_base + path
            canonical = f'<link rel="canonical" href="{escape(url)}">'
            metrics = '<script defer src="/assets/tool-metrics.js" referrerpolicy="no-referrer"></script>'
            ET.SubElement(ET.SubElement(sitemap, 'url'), 'loc').text = url
        html = f'''<!doctype html><html lang="en-CA"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} · Park Ready</title>
<meta name="description" content="{escape(description, quote=True)}">{canonical}
<link rel="stylesheet" href="{prefix}style.css"><script defer src="{prefix}guide-age.js"></script>{metrics}</head>
<body data-tool-id="{escape(tool["id"])}"><a class="skip" href="#main">Skip to guide</a>
<header><nav class="nav">{a(prefix, 'Park Ready')}{a('https://coolcode.ca/', 'CoolCode.ca')}</nav></header>
<main class="visit-guide" id="main">{content}</main>
<footer>{a(prefix, 'Search the full BC Parks catalogue')}{a(ADVISORIES,'Official BC Parks advisories')}</footer></body></html>'''
        (target/'index.html').write_text(html, encoding='utf-8')

    directory = ['<h1>BC park visit guides</h1><p class="lead">Choose a region to compare entrances, gate details and facilities. '
                 'Open a park for dated notices or choose your own date in the trip planner.</p>', stamp(snapshot)]
    for group in groups:
        rows = [(slug, parks[ident]) for slug, ident in group['parks'].items() if ident in parks]
        if not rows:
            continue
        directory.append(f'<section><h2>{a(group["slug"]+"/", group["name"])}</h2><p>{escape(group["intro"])}</p><ul class="park-names">')
        for slug, park in rows:
            if park['id'] in assigned:
                raise ValueError('A park belongs to multiple guide pages')
            assigned[park['id']] = slug
            directory.append(f'<li>{a(slug+"/", park["name"])}</li>')
            topics = facilities_phrase(park)
            detail = f' Read park notes on {topics}.' if topics else ''
            emit(slug, park['name']+' gate information, facilities and advisories',
                 f'Plan a visit to {park["name"]} with BC Parks entrance details and dated notices.' + detail,
                 park_content(park, notices[park['id']], snapshot, rows, group))
        directory.append('</ul></section>')
        emit(group['slug'], group['name']+' BC park trip planner', group['intro'],
             region_content(group, rows, snapshot))
    if not assigned:
        raise ValueError('No reviewed park found in the current source edition')
    emit('', 'BC park visit guides by region', 'Compare entrance information, seasonal gate dates and facility notes for BC Parks destinations by region.',
         ''.join(directory))
    if on_coolcode:
        ET.ElementTree(sitemap).write(stage/'sitemap.xml', encoding='utf-8', xml_declaration=True)
    return home.replace('{{GUIDE_PATHS}}', json.dumps(assigned, separators=(',', ':')))
