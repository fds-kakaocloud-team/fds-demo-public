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
}
document.querySelectorAll('.tab').forEach(button => button.addEventListener('click', () => showPanel(button.dataset.panel)));
async function request(url, options){const response = await fetch(url, options); const body = await response.json(); if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : '입력값을 확인해 주세요.'); return body;}
function show(data){result.className = `result ${data.decision}`; result.replaceChildren(); const title=document.createElement('h2'); title.textContent=data.model_type==='public_credit_card'?(data.decision==='block'?'이상 거래 판정':'정상 거래 판정'):(data.decision==='block'?'이체가 차단되었습니다':'이체가 승인되었습니다'); result.append(title); const detail=document.createElement('p'); detail.textContent=`모델 점수 ${(data.risk_score*100).toFixed(1)} · 기준 ${(data.threshold*100).toFixed(1)}`; result.append(detail); if(data.context_score !== undefined){const context=document.createElement('p');context.textContent=`시간·위치 점수 ${(data.context_score*100).toFixed(1)} · 기준 ${(data.context_threshold*100).toFixed(1)}`;result.append(context);} if(data.actual_label){const actual=document.createElement('p'); actual.textContent=`데이터 정답: ${data.actual_label==='Abuse'?'사기':'정상'} · ${data.actual_label===data.status?'일치':'불일치'}`;result.append(actual);} if(data.id){const note=document.createElement('p');note.textContent='모의 거래 결과가 저장되었습니다.';result.append(note);} const back=document.createElement('button');back.className='secondary result-back';back.textContent='돌아가기';back.addEventListener('click',()=>showPanel(activePanel));result.append(back);document.querySelectorAll('.panel').forEach(panel=>panel.hidden=true);result.hidden=false;}
function fail(e){error.textContent=e.message||'서버에 연결할 수 없습니다.';error.hidden=false;}
async function loadExamples(){try{const items=await request('/public/examples');$('example').replaceChildren(...items.map(item=>new Option(`${item.label} 사례 ${item.id.split('-')[1]} · 금액 ${item.amount}`,item.id)));if(!items.length)throw new Error('사용할 사례가 없습니다.');}catch(e){$('example').replaceChildren(new Option('공개 데이터 준비 필요',''));$('run-public').disabled=true;}}
$('run-public').addEventListener('click',async()=>{clearResult();try{show(await request(`/public/examples/${encodeURIComponent($('example').value)}/predict`,{method:'POST'}));}catch(e){fail(e);}});
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
async function loadHistory(){try{const rows=await request('/transactions');const container=$('history');container.replaceChildren();if(!rows.length){container.textContent='거래 내역이 없습니다.';return;}rows.forEach(row=>{const item=document.createElement('div');item.className='history-row';const info=document.createElement('span');info.textContent=`${row.request.amount.toLocaleString()} · ${new Date(row.created_at).toLocaleString('ko-KR')}`;const status=document.createElement('strong');status.textContent=row.decision==='block'?'차단':'승인';status.className=row.decision;item.append(info,status);container.append(item);});}catch(e){fail(e);}}
$('refresh').addEventListener('click',loadHistory);loadExamples();
