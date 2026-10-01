"""Explicit, versioned, fail-closed contracts; no remote model dependencies."""
import copy
import hashlib
import json
import re
from pathlib import Path

MEASUREMENTS = ('height','bust','waist','hip','shoulder','neck','back_waist_length',
                'front_waist_length','arm_length','upper_arm','wrist','waist_to_knee','head')

def canonical_hash(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def validate_profile(p):
    if p.get('units') != 'mm': raise ValueError('All profile measurements must be in mm')
    if p.get('synthetic') is not True or p.get('age_years',0) < 19:
        raise ValueError('MVP accepts only explicitly synthetic adult test profiles')
    for key in MEASUREMENTS:
        value=p.get(key)
        if not isinstance(value,(int,float)) or isinstance(value,bool) or not 0 < value < 3000:
            raise ValueError('Invalid measurement: '+key)
    if not p['waist'] < p['hip']+150: raise ValueError('Review waist/hip input')
    if not p['wrist'] < p['upper_arm'] < p['bust']: raise ValueError('Review arm measurements')
    return p

def validate_analysis(spec):
    if spec.get('schema_version') != '1.0': raise ValueError('Unsupported CostumeSpec version')
    if spec.get('mode') not in ('authored_reference_replay','synthetic_contract_fixture'): raise ValueError('Expected explicitly labelled analysis mode')
    refs=spec.get('references',[])
    if not refs or any(not r.get('url') or not r.get('sha256') for r in refs):
        raise ValueError('Reference URL and inspected-image hash required')
    ref_ids=[r.get('id') for r in refs]
    if len(set(ref_ids)) != len(ref_ids) or None in ref_ids: raise ValueError('Unique reference IDs required')
    if any(not re.fullmatch(r'[0-9a-f]{64}',r['sha256']) for r in refs): raise ValueError('Invalid SHA256')
    ids=[c.get('id') for c in spec.get('components',[])]
    if not ids or None in ids or len(set(ids)) != len(ids): raise ValueError('Unique component IDs required')
    for c in spec['components']:
        if any(not isinstance(c.get(k),str) or not c[k] for k in ('id','label','material')): raise ValueError('Component label, material and id required')
        if any(o.get('reference_id') not in ref_ids for o in c.get('observations',[])): raise ValueError('Unknown observation reference')
        if c.get('status') not in ('generate','purchase','manual','deferred'):
            raise ValueError('Component production status required')
        if not c.get('observations') or not c.get('construction_hypotheses'):
            raise ValueError('Separate observations and construction hypotheses required')
    if not spec.get('unknowns'): raise ValueError('Hidden-geometry uncertainty must remain explicit')
    return spec

def analyze_images(images, backend='live', replay_path=None):
    """Replay can ONLY accept the exact inspected reference bytes. No visual inference here."""
    paths=[Path(p) for p in images]
    if not paths or any(not p.is_file() for p in paths): raise ValueError('Readable image inputs required')
    if backend != 'replay':
        raise RuntimeError('VISION_BACKEND_NOT_CONFIGURED: no image-analysis model is installed; use explicit reference replay only')
    if replay_path is None: raise ValueError('Replay path required')
    spec=validate_analysis(json.loads(Path(replay_path).read_text()))
    if spec['mode'] != 'authored_reference_replay': raise ValueError('Synthetic fixtures are not image analysis')
    accepted={r['sha256'] for r in spec['references']}
    if {hashlib.sha256(p.read_bytes()).hexdigest() for p in paths} != accepted:
        raise ValueError('Reference checksum mismatch; this replay does not analyze arbitrary images')
    return copy.deepcopy(spec)

def apply_override(spec, component_id, key, value):
    result=copy.deepcopy(spec)
    component=next((c for c in result['components'] if c['id']==component_id),None)
    if component is None: raise ValueError('Unknown component')
    if key not in ('material','closure','construction_hypotheses'): raise ValueError('Unsupported editable field')
    component[key]=value
    result.setdefault('user_overrides',[]).append({'component':component_id,'field':key,'value':value})
    result['revision']=canonical_hash(result)
    result['outputs_invalidated']=True
    return result
