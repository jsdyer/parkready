#!/usr/bin/env python3
"""Retrieve a complete, validated BC Parks catalogue and published advisory snapshot."""
import concurrent.futures
from datetime import date, datetime, timezone
from html.parser import HTMLParser
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]

class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.parts=[]; self.skip=0
    def handle_starttag(self, tag, attrs):
        if tag in {'script','style'}: self.skip += 1
        if tag in {'p','div','li','br','h2','h3','h4','tr'}: self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in {'script','style'}: self.skip=max(0,self.skip-1)
        if tag in {'p','div','li','tr'}: self.parts.append('\n')
    def handle_data(self, value):
        if not self.skip: self.parts.append(value)

def plain(value):
    parser=PlainText(); parser.feed(str(value or ''))
    return '\n'.join(' '.join(line.split()) for line in ''.join(parser.parts).splitlines() if line.strip()).strip()

def https_url(value):
    try:
        url=urlsplit(value or '')
        return value if url.scheme=='https' and url.hostname and not url.username and not url.password else None
    except ValueError: return None

def request_json(url):
    last=None
    for attempt in range(3):
        try:
            with urlopen(Request(url,headers={'User-Agent':'CoolCode Park Ready (https://coolcode.ca/parkready/)','Accept':'application/json'}),timeout=45) as response:
                raw=response.read(8_000_001)
            if len(raw)>8_000_000: raise ValueError('Source page exceeded size limit')
            return json.loads(raw)
        except (OSError, ValueError) as exc:
            last=exc
            if attempt<2: time.sleep(attempt+1)
    raise RuntimeError('Official source retrieval failed; previous snapshot was preserved') from last

def projection(fields, relations):
    params={f'fields[{i}]':field for i,field in enumerate(fields)}
    for relation, rfields in relations.items():
        for i,field in enumerate(rfields): params[f'populate[{relation}][fields][{i}]']=field
    return params

PARK_PARAMS=projection(
    ['orcs','protectedAreaName','type','url','slug','latitude','longitude','isDisplayed','legalStatus','hasCampfireBan','campfireBanEffectiveDate','campfireBanRescindedDate','updatedAt','locationNotes'],
    {'parkFacilities':['name','description','isActive'], 'parkActivities':['name','isActive'],
     'parkDates':['name','isActive','operatingYear','startDate','endDate','isDateAnnual'],
     'parkGate':['hasGate','gateOpenHoursStartTime','gateOpenHoursEndTime','gateOpensAtDawn','gateClosesAtDusk','gateOpen24Hours','gateNote'],
     'parkOperation':['hasDayUsePass','dayUsePassUrl','hasReservations','reservationUrl','openNote','offSeasonNote','generalNote']})
# The type relation describes what a date window is for; never infer it from internal names.
PARK_PARAMS['populate[parkDates][populate][parkDateType][fields][0]']='dateType'
# dateTypeNumber exists in the CMS source but is not exposed by the public projection.
ADVISORY_PARAMS=projection(
    ['advisoryNumber','revisionNumber','title','description','effectiveDate','endDate','expiryDate','updatedDate','advisoryDate','modifiedDate','isSafetyRelated','isReservationsAffected'],
    {'protectedAreas':['orcs'],'accessStatus':['accessStatus','precedence','groupLabel'], 'urgency':['urgency','sequence'],
     'eventType':['eventType'], 'advisoryStatus':['code'],'links':['title','url']})
ADVISORY_PARAMS['filters[advisoryStatus][code][$eq]']='PUB'

def fetch_all(endpoint, params, config, fetch=request_json):
    size=int(config['page_size']); max_pages=int(config['max_pages'])
    if not 1<=size<=1000 or not 1<=max_pages<=1000: raise ValueError('Invalid pagination configuration')
    rows=[]; seen=set(); total=None; pages=None
    for page in range(1,max_pages+1):
        q={**params,'sort':'id:asc','pagination[page]':page,'pagination[pageSize]':size}
        document=fetch(config['api_base'].rstrip('/')+'/'+endpoint+'?'+urlencode(q))
        if not isinstance(document,dict) or not isinstance(document.get('data'),list): raise ValueError('Unexpected source schema')
        meta=document.get('meta',{}).get('pagination',{})
        if not all(isinstance(meta.get(k),int) for k in ['page','pageSize','pageCount','total']): raise ValueError('Missing pagination evidence')
        if meta['page']!=page or meta['pageSize']!=size: raise ValueError('Source did not honor pagination')
        if total is None: total=meta['total']; pages=meta['pageCount']
        if total!=meta['total'] or pages!=meta['pageCount']: raise ValueError('Source changed during pagination; retry complete retrieval')
        batch=document['data']
        for row in batch:
            identity=row.get('documentId') or row.get('id')
            if identity is None or identity in seen: raise ValueError('Duplicate source row; incomplete pagination')
            seen.add(identity); rows.append(row)
        if page>=pages:
            if len(rows)!=total: raise ValueError('Source row count differs from declared total')
            return rows
        if not batch: raise ValueError('Unexpected empty source page')
    raise ValueError('Page limit exceeded; no partial snapshot published')

def source_date(value):
    if value is None or value == '':return None
    if not isinstance(value,str):raise ValueError('Source date must be text')
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):date.fromisoformat(value)
    else:
        parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
        if parsed.tzinfo is None:raise ValueError('Advisory instant needs an explicit timezone')
    return value

def normalize(parks, advisories):
    result=[]; ids=set()
    for p in parks:
        if not p.get('isDisplayed') or p.get('legalStatus')!='Active': continue
        if not isinstance(p.get('orcs'),int) or not p.get('protectedAreaName'): raise ValueError('Park identity missing')
        if p['orcs'] in ids: raise ValueError('Duplicate ORCS park identity')
        url=https_url(p.get('url'))
        if not url or urlsplit(url).hostname!='bcparks.ca': raise ValueError('Expected official park URL')
        ids.add(p['orcs'])
        coordinates=[p.get('latitude'),p.get('longitude')]
        if not all(isinstance(n,(int,float)) and not isinstance(n,bool) for n in coordinates) or not (-90<=coordinates[0]<=90 and -180<=coordinates[1]<=180) or coordinates==[0,0]:coordinates=None
        dates=[]
        for d in p.get('parkDates',[]):
            if d.get('isActive') is not True:continue
            typ=d.get('parkDateType') or {}
            start,end=d.get('startDate'),d.get('endDate')
            for value in [start,end]:
                if value and date.fromisoformat(value).isoformat()!=value:raise ValueError('Invalid operating dates')
            if start and end and start>end:raise ValueError('Reversed operating dates')
            dates.append({'kind':plain(typ.get('dateType') or 'Operating dates'),'kind_id':typ.get('id'),'annual':d.get('isDateAnnual') is True,'year':d.get('operatingYear'),'start':start,'end':end})
        gate=p.get('parkGate') or {}; operation=p.get('parkOperation') or {}
        result.append({'id':p['orcs'],'name':plain(p['protectedAreaName']),'type':p.get('type') or 'Protected area','url':url,'coordinates':coordinates,'location':plain(p.get('locationNotes')),
          'facilities':[{'name':plain(f.get('name')).split(':',1)[-1].strip(),'detail':plain(f.get('description'))} for f in p.get('parkFacilities',[]) if f.get('isActive') is True],
          'activities':sorted({plain(a.get('name')).split(':',1)[-1].strip() for a in p.get('parkActivities',[]) if a.get('isActive') is True}),
          'dates':dates,'gate':{'present':gate.get('hasGate'),'start':gate.get('gateOpenHoursStartTime'),'end':gate.get('gateOpenHoursEndTime'),'dawn':gate.get('gateOpensAtDawn'),'dusk':gate.get('gateClosesAtDusk'),'all_day':gate.get('gateOpen24Hours'),'note':plain(gate.get('gateNote'))},
          'campfire_ban':p.get('hasCampfireBan') is True,'campfire_effective':p.get('campfireBanEffectiveDate'),'campfire_rescinded':p.get('campfireBanRescindedDate'),
          'day_pass':operation.get('hasDayUsePass') is True,'day_pass_url':https_url(operation.get('dayUsePassUrl')),
          'operating_note':plain(operation.get('openNote')),'updated_at':p.get('updatedAt')})
    notices=[]; notice_ids=set()
    for a in advisories:
        if (a.get('advisoryStatus') or {}).get('code')!='PUB': continue
        if not isinstance(a.get('advisoryNumber'),int) or not a.get('title'):raise ValueError('Advisory identity missing')
        if a['advisoryNumber'] in notice_ids:raise ValueError('Duplicate advisory identity')
        notice_ids.add(a['advisoryNumber'])
        status=a.get('accessStatus') or {}; urgency=a.get('urgency') or {}
        notices.append({'id':a['advisoryNumber'],'revision':a.get('revisionNumber'),'title':plain(a['title']),'description':plain(a.get('description')),
          'parks':sorted({p['orcs'] for p in a.get('protectedAreas',[]) if p.get('orcs') in ids}),
          'access':status.get('accessStatus'),'access_group':status.get('groupLabel'),'precedence':status.get('precedence') or 99,
          'urgency':urgency.get('urgency') or 'Not specified','urgency_rank':urgency.get('sequence') or 0,
          'event':(a.get('eventType') or {}).get('eventType'),'effective':source_date(a.get('effectiveDate')),'end':source_date(a.get('endDate')),'expires':source_date(a.get('expiryDate')),
          'updated_at':source_date(a.get('updatedDate') or a.get('advisoryDate')),'source_modified':source_date(a.get('modifiedDate')),'reservations_affected':a.get('isReservationsAffected') is True,
          'links':[{'title':plain(l.get('title')) or 'Official information','url':https_url(l.get('url'))} for l in a.get('links',[]) if https_url(l.get('url'))]})
    return sorted(result,key=lambda p:p['name'].casefold()), sorted(notices,key=lambda a:a['id'])

def refresh(root=ROOT, fetch=request_json):
    config=json.loads((root/'config/source.json').read_text())
    if config['api_base']!='https://bcparks.api.gov.bc.ca/api':raise ValueError('Review a new source adapter before changing the API host')
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        p=pool.submit(fetch_all,'protected-areas',PARK_PARAMS,config,fetch)
        a=pool.submit(fetch_all,'public-advisories',ADVISORY_PARAMS,config,fetch)
        raw_parks,raw_advisories=p.result(),a.result()
    parks,advisories=normalize(raw_parks,raw_advisories)
    if not parks:raise ValueError('No displayed active parks; refusing empty replacement')
    # Zero published advisories can be legitimate; complete pagination proves the response.
    now=datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
    data={'schema_version':1,'checked_at':now,'scope':config['scope'],'stale_after_hours':config['stale_after_hours'],'examples':config['default_examples'],'parks':parks,'advisories':advisories}
    payload=(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n').encode()
    status={'schema_version':1,'checked_at':now,'count':len(parks),'advisory_count':len(advisories),'linked_advisory_count':sum(bool(a['parks']) for a in advisories),'source_park_count':len(raw_parks),'source_advisory_count':len(raw_advisories),'sha256':hashlib.sha256(payload).hexdigest(),'source':'https://bcparks.ca/active-advisories/'}
    # No writes occur before both complete datasets and transformations validate.
    (root/'data').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root/'data') as temp:
        directory=Path(temp);(directory/'index.json').write_bytes(payload);(directory/'status.json').write_text(json.dumps(status,indent=2)+'\n')
        for filename in ['index.json','status.json']:os.replace(directory/filename,root/'data'/filename)
    print(f'Validated {len(parks)} protected areas and {len(advisories)} published advisories; checked {now}')

if __name__=='__main__':refresh()
