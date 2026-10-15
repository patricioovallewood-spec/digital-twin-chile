"""Validate an authorized, minimized CSV before any municipal integration.
This tool does NOT connect to a municipality or upload data. No row values are
printed on errors. Unknown fields are rejected to avoid accidental personal data.
"""
import argparse,csv,datetime as dt,json,math,pathlib
SCHEMAS={
 'pedestrians':{'segment_id','longitude','latitude','interval_start','interval_end','count','method','source','observed_at'},
 'assets':{'asset_id','longitude','latitude','asset_type','status','source','observed_at'},
 'licenses':{'establishment_id','trade_name','longitude','latitude','business_category','license_status','valid_from','valid_until','source','observed_at'}
}
def timestamp(value):
 value=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
 if value.tzinfo is None:raise ValueError('Timestamp must include timezone')
 return value

def validate(path,kind):
 errors=[];n=0;seen=set()
 with pathlib.Path(path).open(encoding='utf-8-sig',newline='') as stream:
  reader=csv.DictReader(stream);fields=set(reader.fieldnames or [])
  if fields!=SCHEMAS[kind]:raise ValueError('Columns must exactly match the approved schema for '+kind)
  for i,row in enumerate(reader,2):
   n+=1
   try:
    lon=float(row['longitude']);lat=float(row['latitude'])
    if not math.isfinite(lon) or not math.isfinite(lat) or not (-180<=lon<=180 and -90<=lat<=90):raise ValueError('Coordinates out of range')
    timestamp(row['observed_at'])
    if not row['source'].strip():raise ValueError('Source required')
    if kind=='pedestrians':
     start=timestamp(row['interval_start']);end=timestamp(row['interval_end'])
     if start>=end:raise ValueError('Invalid observation interval')
     if not row['count'].isdigit() or not row['method'].strip():raise ValueError('Integer count and documented method required')
     key=(row['segment_id'],row['interval_start'],row['interval_end'])
    elif kind=='licenses':
     key=row['establishment_id']
     start=dt.date.fromisoformat(row['valid_from']);end=dt.date.fromisoformat(row['valid_until']) if row['valid_until'] else None
     if end and end<start:raise ValueError('Invalid license dates')
    else:key=row['asset_id']
    if not key or key in seen:raise ValueError('Missing or duplicate record identifier')
    seen.add(key)
   except (ValueError,TypeError):errors.append({'row':i,'error':'Record violates contract; review locally. Values omitted.'})
 return {'kind':kind,'rows':n,'valid':not errors,'errors':errors,'connected':False,'published':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('kind',choices=SCHEMAS);p.add_argument('csv_path');p.add_argument('--authorized',action='store_true',help='Confirm authority and minimization for local validation only');a=p.parse_args()
 if not a.authorized:p.error('Explicit authorization confirmation is required')
 r=validate(a.csv_path,a.kind);print(json.dumps(r));raise SystemExit(0 if r['valid'] else 1)
