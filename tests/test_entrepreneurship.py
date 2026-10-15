#!/usr/bin/env python3
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'atlas/data/entrepreneurship-aggregate.json').read_text(encoding='utf-8'))
assert data['type']=='AggregateEntrepreneurshipProfile'
assert data['privacy']['contains_personal_data'] is False
assert data['kpis']['unique_profiles']==2374
assert data['kpis']['providencia_profiles']==1735
assert data['kpis']['multi_program_profiles']==213
assert sum(x['profiles'] for x in data['participation'])==2374
assert sum(x['profiles'] for x in data['age_bands'])==2374
assert sum(x['profiles'] for x in data['education'])==2374
assert sum(x['unique_profiles'] for x in data['programs'])==2613

forbidden={'rut','email','correo','telefono','teléfono','celular','domicilio','direccion','dirección','fecha_de_nacimiento','fecha de nacimiento','nombre_completo'}
def walk(obj):
    if isinstance(obj,dict):
        for k,v in obj.items():
            # Privacy metadata may name excluded source fields, but no row-level personal columns may exist.
            if k.lower() in forbidden:
                raise AssertionError(f'personal field published: {k}')
            walk(v)
    elif isinstance(obj,list):
        for v in obj: walk(v)
walk(data)

index=(ROOT/'atlas/index.html').read_text(encoding='utf-8')
app=(ROOT/'atlas/app.mjs').read_text(encoding='utf-8')
module=(ROOT/'atlas/entrepreneurship.mjs').read_text(encoding='utf-8')
core=(ROOT/'atlas/core.mjs').read_text(encoding='utf-8')
assert 'id="entrepreneurNav"' in index
assert 'installEntrepreneurship' in app
assert 'contains_personal_data!==false' in module
assert "VERSION='0.6.1'" in core
print('entrepreneurship aggregate/privacy checks: PASS')
