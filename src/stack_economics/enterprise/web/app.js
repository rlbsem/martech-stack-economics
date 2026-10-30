'use strict';
const $ = id => document.getElementById(id);
const number = value => new Intl.NumberFormat('en-US').format(value);
let packet;
let money;
const labels = {reference:'Reference', optimized:'Cost optimized', resilient:'Capacity resilient'};
const text = (tag, value) => {const el=document.createElement(tag); el.textContent=value; return el;};
function row(target, values) {const tr=document.createElement('tr'); for(const value of values) tr.append(text('td',value)); $(target).append(tr);}
function sensitivity() {
  $('sensitivity-results').replaceChildren();
  for(const item of packet.decision.sensitivity.filter(r=>r.dimension===$('sensitivity').value)) {
    row('sensitivity-results',[number(item.value), item.plan.annual_cents===null?'—':money(item.plan.annual_cents),item.plan.selection?.tier || '—', item.plan.status]);
  }
}
function render() {
  const d=packet.decision, s=d.scenario;
  const name=$('architecture').value, item=d.alternatives[name], c=item.assessment.conditions.find(c=>c.id===$('condition').value);
  const m=c.months.find(m=>m.id===$('month').value);
  $('monthly').textContent=money(m.cost_cents);
  const reference=d.alternatives.reference.assessment.conditions.find(c=>c.id===cId()).months.find(x=>x.id===m.id);
  $('delta').textContent=`${money(m.cost_cents-reference.cost_cents)} vs same-month reference`;
  const violations=item.assessment.violations.filter(v=>!v.condition || v.condition===c.id);
  $('verdict').textContent=violations.length?'Requirements not met':'Meets declared envelope';
  $('attempts').textContent=number(m.lines.reduce((n,r)=>n+r.attempts,0));
  $('retries').textContent=`Includes ${number(m.lines.reduce((n,r)=>n+r.retry_requests,0))} modeled retry requests`;
  $('work-headroom').textContent=number(m.shared_work.headroom);
  $('crm-headroom').textContent=number(m.crm_quota.headroom);
  $('costs').replaceChildren();
  const max=Math.max(...Object.values(m.components_cents),1);
  for(const [key,value] of Object.entries(m.components_cents)) {
    const item=document.createElement('div'); item.className='cost-line';
    item.append(text('span',key.replaceAll('_',' ')),text('strong',money(value)));
    const meter=document.createElement('meter'); meter.min=0;meter.max=max;meter.value=value;meter.setAttribute('aria-label',key.replaceAll('_',' ')+' USD cents');item.append(meter);$('costs').append(item);
  }
  $('months').replaceChildren();
  for(const month of c.months) row('months',[month.id,number(month.lines.reduce((n,r)=>n+r.source_events,0)),money(month.cost_cents)]);
  $('routes').replaceChildren();
  for(const line of m.lines) {
    const w=s.workloads.find(w=>w.id===line.workload), route=w.options.find(o=>o.id===line.route);
    row('routes',[w.purpose,line.route,`${number(line.source_events)} → ${number(line.downstream_records)}`,`${number(line.batches)} + ${number(line.retry_requests)}`,`${route.lag_minutes} / ${w.max_lag_minutes} min`,money(line.fully_allocated_cents)]);
  }
  $('month-record').textContent=JSON.stringify({architecture:name,selection:item.selection,month:m,violations},null,2);
}
const cId=()=>$('condition').value;
async function start() {
  const response=await fetch('/api/enterprise'); if(!response.ok) throw new Error('Evidence unavailable'); packet=await response.json();
  const d=packet.decision, s=d.scenario;
  money=cents=>new Intl.NumberFormat('en-US',{style:'currency',currency:s.currency,maximumFractionDigits:2}).format(cents/100);
  const baseline=d.alternatives.reference.assessment.conditions.find(c=>c.id==='operating');
  $('source').textContent=number(baseline.months.reduce((n,m)=>n+m.lines.reduce((a,r)=>a+r.source_events,0),0));
  $('records').textContent=number(baseline.months.reduce((n,m)=>n+m.lines.reduce((a,r)=>a+r.downstream_records,0),0));
  $('customers').textContent=number(s.customer_population);
  const oracle=d.independent_oracles.optimized;
  $('oracle').textContent=`${number(oracle.configurations_assessed)} eligible choices / ${number(oracle.raw_space)} raw`;
  for(const [name,item] of Object.entries(d.alternatives)) {
    const normal=item.assessment.conditions.find(c=>c.id==='operating');
    const stress=item.assessment.conditions.find(c=>c.id==='campaign-disruption');
    row('comparison',[labels[name],money(normal.annual_cents),money(stress.annual_cents),item.selection.tier,item.assessment.feasible?'Both feasible':'See rejected constraints']);
  }
  for(const m of s.months) {const o=text('option',m.id);o.value=m.id;$('month').append(o);}
  $('month').value='2026-11';
  for(const id of ['architecture','condition','month']) $(id).addEventListener('change',render);
  $('sensitivity').addEventListener('change',sensitivity);
  $('provenance').textContent=JSON.stringify({verification:packet.verification,download_sha256:packet.download_sha256,scenario:s},null,2);
  $('checks').textContent=JSON.stringify({plans:d.plans,oracles:d.independent_oracles,budget_rejection:d.budget_rejection},null,2);
  render();sensitivity();$('content').hidden=false;$('load-status').textContent='Verified recorded model loaded · no execution or external writes available';
}
start().catch(error=>{$('load-status').textContent='Unable to load verified evidence: '+error.message;});
