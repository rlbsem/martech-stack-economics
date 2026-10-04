"""Render the executed synthetic optimizer result; no dashboard or vendor claims."""
import hashlib
import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source = ROOT / 'docs/evidence/planning-proof.json'
proof = json.loads(source.read_text(encoding='utf-8'))
robust = proof['robust_plan']
assert robust['assessment']['feasible'] and proof['independent_exhaustive_oracle']['best']['cost_cents'] == robust['assessment']['worst_cost_cents']
parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="650" viewBox="0 0 1000 650" role="img" aria-labelledby="title desc">','<title id="title">Executed integration configuration optimum and capacity tradeoffs</title>','<desc id="desc">Synthetic four-hour planning result. The constrained optimum costs 782 cents versus 1340 cents for the feasible all-premium reference. Three workflows use streaming and two use bulk. Independent enumeration checks 3125 configurations. Reduced capacity changes the optimum and can make the problem infeasible.</desc>','<rect width="1000" height="650" fill="#f8fafc"/>','<style>text{font-family:Arial,Helvetica,sans-serif;fill:#172b43}.small{font-size:17px}.label{font-size:20px}.value{font-size:28px;font-weight:bold}</style>']

def text(x,y,value,cls='label'):
    parts.append(f'<text x="{x}" y="{y}" class="{cls}">{escape(str(value))}</text>')

text(36,42,'CONSTRAINED STACK ECONOMICS / EXECUTED RESULT','small')
text(36,84,'One configuration must survive normal demand and a launch surge.','value')
text(36,116,'Synthetic prices, demand and service envelopes · four-hour horizon · no realized savings','small')
maximum = proof['premium_reference']['assessment']['worst_cost_cents']
for i,(label,amount,color) in enumerate([('Constrained optimum',robust['assessment']['worst_cost_cents'],'#2563eb'),('Feasible all-premium reference',maximum,'#64748b')]):
    y=163+i*89
    text(36,y,label)
    parts.append(f'<rect x="36" y="{y+12}" width="{360*amount/maximum:.1f}" height="25" rx="4" fill="{color}"/>')
    text(36+360*amount/maximum+12,y+32,f'{amount:,} cents','small')
text(540,164,'Selected configuration')
for i,(workload,route) in enumerate(robust['selection'].items()):
    text(540,201+i*29,f'{workload} → {route}','small')
text(36,365,f"Independent enumeration: {proof['independent_exhaustive_oracle']['configurations_checked']:,} configurations; same optimum.")
text(36,410,'CRM requests/hour: capacity changes the decision, not just the speed.')
for i,row in enumerate(proof['capacity_tradeoffs']):
    x=36+i*187
    result=row['plan']
    status=result['status']
    cost=(result.get('assessment') or {}).get('worst_cost_cents')
    parts.append(f'<rect x="{x}" y="432" width="172" height="99" rx="6" fill="#ffffff" stroke="#cbd5e1"/>')
    text(x+16,463,f"{row['crm_requests_per_slot']} / hour",'label')
    text(x+16,499, f'{cost:,} cents' if cost is not None else status.upper(),'small')
text(36,574,f"Budget {proof['below_optimum_budget']['input']['budget_cents']:,} cents: no feasible recommendation. Cheap lossy routes are also rejected.",'small')
text(36,606,'Capability, region, freshness and quota constraints remain binding. Declared latency is not measured.', 'small')
parts.append('<metadata>'+escape(json.dumps({'source':'docs/evidence/planning-proof.json','sha256':hashlib.sha256(source.read_bytes()).hexdigest()}))+'</metadata>')
parts.append('</svg>')
Path(__file__).with_name('optimization-result.svg').write_text('\n'.join(parts)+'\n',encoding='utf-8')
print('Rendered actual optimization evidence.')
