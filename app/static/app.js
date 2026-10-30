const $ = id => document.getElementById(id);
const result = $('result'), error = $('error');
$('hour').value = new Date().getHours();
let activePanel = 'manual';
function clearResult(){ result.hidden = true; error.hidden = true; }
function showPanel(name){
  activePanel = name;
  document.querySelectorAll('.tab').forEach(tab => {const active=tab.dataset.panel===name;tab.classList.toggle('active',active);tab.setAttribute('aria-selected',String(active));$(tab.dataset.panel).hidden=!active;});
  clearResult();
  if(name==='history-panel') loadHistory();
  if(name==='stats-panel') loadStats();
}
document.querySelectorAll('.tab').forEach(button => button.addEventListener('click', () => showPanel(button.dataset.panel)));
async function request(url, options){const response = await fetch(url, options); const body = await response.json(); if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : '입력값을 확인해 주세요.'); return body;}
function reasonLabels(reasons){return (reasons || []).map(reason=>reason==='paysim'?'거래 패턴 모델':reason==='time_location'?'시간·거리 모델':reason);}
function show(data){
  result.className=`result ${data.decision}`;result.replaceChildren();
  const title=document.createElement('h2');title.textContent=data.decision==='block'?'이체가 차단되었습니다':'이체가 승인되었습니다';result.append(title);
  const summary=document.createElement('p');summary.className='result-reason';
  const reasons=reasonLabels(data.reasons);
  summary.textContent=reasons.length?`${reasons.join(' · ')} 기준 초과`:'두 모델 모두 기준 미만';result.append(summary);
  for(const [label,score,threshold] of [['거래 패턴 모델',data.risk_score,data.threshold],['시간·거리 모델',data.context_score,data.context_threshold]]){
    if(score===undefined)continue;
    const detail=document.createElement('p');detail.textContent=`${label} ${(score*100).toFixed(1)}점 / 기준 ${(threshold*100).toFixed(1)}점`;result.append(detail);
  }
  if(data.id){const id=document.createElement('p');id.textContent=`거래 ID ${data.id}`;result.append(id);}
  const back=document.createElement('button');back.className='secondary result-back';back.textContent='돌아가기';back.addEventListener('click',()=>showPanel(activePanel));result.append(back);document.querySelectorAll('.panel').forEach(panel=>panel.hidden=true);result.hidden=false;
}
function fail(e){error.textContent=e.message||'서버에 연결할 수 없습니다.';error.hidden=false;}
const scenarios={normal:{amount:10000,balance:100000,hour:12,distance:5},transaction:{amount:100000,balance:100000,hour:12,distance:5},context:{amount:10000,balance:100000,hour:2,distance:1000}};
function fillScenario(scenario){
  $('bank').value='가상은행';$('account').value='1234567890';$('recipient').value='김민수';
  $('amount').value=scenario.amount;$('oldbalance').value=scenario.balance;$('hour').value=scenario.hour;$('distance').value=scenario.distance;clearResult();
}
document.querySelectorAll('[data-scenario]').forEach(button=>button.addEventListener('click',()=>fillScenario(scenarios[button.dataset.scenario])));
$('random-fill').addEventListener('click', () => {
  const pick = values => values[Math.floor(Math.random() * values.length)];
  // Vary both low- and high-risk-looking examples; the models decide the outcome.
  const scenario = pick([
    {amount: 10000, balance: 100000, hour: 12, distance: 5},
    {amount: 100000, balance: 100000, hour: 12, distance: 5},
    {amount: 10000, balance: 100000, hour: 2, distance: 1000},
    {amount: pick([30000, 50000, 200000, 500000]), balance: pick([100000, 500000, 1000000]), hour: Math.floor(Math.random()*24), distance: pick([0, 10, 100, 500, 1500])}
  ]);
  $('bank').value = pick(['가상은행', '테스트은행', '모의저축은행']);
  $('account').value = String(Math.floor(1000000000 + Math.random() * 9000000000));
  $('recipient').value = pick(['김민수', '이서연', '박지훈', '최지우']);
  $('amount').value = scenario.amount; $('oldbalance').value = scenario.balance;
  $('hour').value = scenario.hour; $('distance').value = scenario.distance;
  clearResult();
});
$('form').addEventListener('submit',event=>{event.preventDefault();clearResult();$('confirm-recipient').textContent=$('recipient').value;$('confirm-account').textContent=`${$('bank').value} ${$('account').value}`;$('confirm-amount').textContent=`${Number($('amount').value).toLocaleString()}원`;$('confirm-balance').textContent=`${Number($('oldbalance').value).toLocaleString()}원`;$('confirm-hour').textContent=`${$('hour').value}시`;$('confirm-distance').textContent=`${Number($('distance').value).toLocaleString()} km`;$('form').hidden=true;$('confirm').hidden=false;$('manual-title').textContent='이체 확인';});
$('edit').addEventListener('click',()=>{$('confirm').hidden=true;$('form').hidden=false;$('manual-title').textContent='어디로 보낼까요?';});
$('send').addEventListener('click',async()=>{clearResult();const button=$('send');button.disabled=true;try{const data={amount:Number($('amount').value),oldbalance:Number($('oldbalance').value),transaction_type:'TRANSFER',hour:Number($('hour').value),distance_from_last_km:Number($('distance').value)};show(await request('/transactions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}));$('confirm').hidden=true;$('form').hidden=false;$('manual-title').textContent='어디로 보낼까요?';}catch(e){fail(e);}finally{button.disabled=false;}});
async function loadHistory(){
  try{const rows=await request('/transactions');const container=$('history');container.replaceChildren();
    if(!rows.length){container.textContent='거래 내역이 없습니다.';return;}
    rows.forEach(row=>{
      const item=document.createElement('div');item.className='history-row';const info=document.createElement('div');
      const amount=document.createElement('strong');amount.textContent=`${row.request.amount.toLocaleString()}원`;
      const meta=document.createElement('small');meta.textContent=new Date(row.created_at).toLocaleString('ko-KR');
      const reason=document.createElement('small');const reasons=reasonLabels(row.reasons);reason.textContent=reasons.length?`차단 원인: ${reasons.join(' · ')}`:row.decision==='block'?'차단 원인 기록 없음':'두 모델 기준 미만';
      const id=document.createElement('small');id.textContent=`거래 ID ${row.id}`;info.append(amount,meta,reason,id);
      const status=document.createElement('strong');status.textContent=row.decision==='block'?'차단':'승인';status.className=row.decision;item.append(info,status);container.append(item);
    });
  }catch(e){fail(e);}
}
$('refresh').addEventListener('click',loadHistory);

let seenAlertIds = null;
let unreadAlerts = 0;
let checkingAlerts = false;
function renderAlerts(items){
  const list = $('alerts'); list.replaceChildren();
  if (!items.length) { list.textContent='차단 알림이 없습니다.'; return; }
  for (const alert of items) {
    const row=document.createElement('div'); row.className='alert-row';
    const title=document.createElement('strong'); title.textContent='이상 거래 차단';
    const meta=document.createElement('small');
    const reasons=reasonLabels(alert.reasons);
    const amount=document.createElement('p');amount.textContent=alert.amount == null ? '금액 정보 없음' : `${Number(alert.amount).toLocaleString()}원`;
    meta.textContent=`${new Date(alert.created_at).toLocaleString('ko-KR')} · ${reasons.join(' · ') || '차단 원인 기록 없음'} · 거래 ID ${alert.transaction_id}`;
    row.append(title,amount,meta); list.append(row);
  }
}
async function checkAlerts(){
  if(checkingAlerts) return;
  checkingAlerts=true;
  try {
    const items=await request('/security/alerts');
    $('security-status').textContent='연결됨';
    const current=new Set(items.map(item=>item.event_id));
    if(seenAlertIds!==null){
      const fresh=items.filter(item=>!seenAlertIds.has(item.event_id));
      if(fresh.length && activePanel!=='security-panel'){
        unreadAlerts+=fresh.length;
        $('alert-banner').textContent=`이상 거래 ${fresh.length}건이 차단되었습니다. 보안 알림에서 확인하세요.`;
        $('alert-banner').hidden=false;
      }
    }
    seenAlertIds=current;
    if(activePanel==='security-panel'){unreadAlerts=0;renderAlerts(items);}
    $('alert-badge').hidden=unreadAlerts===0;
    $('alert-badge').textContent=unreadAlerts>99?'99+':String(unreadAlerts);
  } catch(e){$('security-status').textContent='연결 안 됨 · 재시도 중';}
  finally{checkingAlerts=false;}
}
$('refresh-alerts').addEventListener('click',checkAlerts);
document.querySelector('[data-panel="security-panel"]').addEventListener('click',()=>{
  unreadAlerts=0; $('alert-badge').hidden=true; $('alert-banner').hidden=true; checkAlerts();
});
checkAlerts();
setInterval(checkAlerts,2000);

async function loadStats(){
  const content=$('stats-content');
  try {
    const data=await request('/statistics'); content.replaceChildren();
    const total=data.total_approved+data.total_blocked;
    const summary=document.createElement('div'); summary.className='stats-summary';
    for(const [label,value] of [['전체',total],['승인',data.total_approved],['차단',data.total_blocked]]){
      const item=document.createElement('div');const name=document.createElement('span');name.textContent=label;
      const count=document.createElement('strong');count.textContent=`${value.toLocaleString()}건`;item.append(name,count);summary.append(item);
    }
    content.append(summary);
    const title=document.createElement('h2');title.textContent='일별 거래';title.className='stats-title';content.append(title);
    if(total===0){const empty=document.createElement('p');empty.className='note';empty.textContent='최근 7일 동안 거래가 없습니다.';content.append(empty);return;}
    const legend=document.createElement('p');legend.className='stats-legend';legend.innerHTML='<span class="dot approved"></span> 승인 <span class="dot blocked"></span> 차단';content.append(legend);
    const chart=document.createElement('div');chart.className='stats-chart';
    const maximum=Math.max(...data.days.map(day=>day.approve+day.block),1);
    for(const day of data.days){
      const row=document.createElement('div');row.className='chart-row';
      const label=document.createElement('span');label.className='chart-date';label.textContent=day.date.slice(5).replace('-','.');
      const track=document.createElement('div');track.className='chart-track';
      for(const [kind,value] of [['approved',day.approve],['blocked',day.block]]){const bar=document.createElement('span');bar.className=`chart-bar ${kind}`;bar.style.width=`${value/maximum*100}%`;track.append(bar);}
      const count=document.createElement('span');count.className='chart-count';count.textContent=String(day.approve+day.block);
      row.setAttribute('aria-label',`${day.date} 승인 ${day.approve}건, 차단 ${day.block}건`);row.append(label,track,count);chart.append(row);
    }
    content.append(chart);
  }catch(e){content.textContent='거래 통계를 불러올 수 없습니다.';}
}
$('refresh-stats').addEventListener('click',loadStats);
