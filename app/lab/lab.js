import {SCENARIOS,createLabState,resetLab,runScenario,replayForgotten,viewMemory,getScenario} from "./engine.js";

const $=selector=>document.querySelector(selector);
const E=(tag,cls,txt)=>{const el=document.createElement(tag);if(cls)el.className=cls;if(txt!==undefined)el.textContent=txt;return el};
const state=createLabState();
let selected="add",actorView="owner",runNonce=0,busy=false;
const labels={ADD:"新增长期记忆",UPDATE:"更新当前事实",FORGET:"删除旧记忆",REJECT:"安全策略拒绝",CLARIFY:"请求澄清",IGNORE:"无需持久化"};
const glyphs={ADD:"+",UPDATE:"↻",FORGET:"−",REJECT:"×",CLARIFY:"?",IGNORE:"–"};
const stages=[...document.querySelectorAll(".stage")];

function renderScenarios(){
 const list=$("#scenario-list");list.replaceChildren();
 for(const sc of SCENARIOS){
  const btn=E("button","scenario"+(selected===sc.id?" selected":""),undefined);
  btn.type="button";btn.dataset.action=sc.action;btn.dataset.id=sc.id;
  btn.setAttribute("aria-pressed",String(selected===sc.id));
  btn.append(E("span","scenario-num",sc.num));
  const content=E("span","scenario-content");
  content.append(E("span","scenario-name",sc.title),E("span","scenario-desc",sc.subtitle));
  btn.append(content,E("span","action-mini",sc.action));
  btn.addEventListener("click",()=>selectScenario(sc.id));
  list.append(btn);
 }
}
function selectScenario(id){
 const sc=getScenario(id);if(!sc)return;
 selected=sc.id; actorView=sc.source==="visitor"?"visitor":"owner";
 $("#decision-result").classList.add("hidden");
 $("#decision-empty").classList.remove("hidden");
 ++runNonce;busy=false;$("#run").disabled=false;$("#run").textContent="运行决策 →";
 $("#message").value=sc.input;
 $("#actor-pill").classList.toggle("visitor",sc.source==="visitor");
 $("#actor-pill").textContent=sc.source==="visitor"?"◉ 未授权访客（模拟）":"◉ 已认证主人（模拟）";
 $("#pipeline-status").textContent="等待输入";stages.forEach(s=>s.className="stage");
 renderScenarios();renderMemory();renderViewTabs();
}
function renderViewTabs(){
 $("#owner-view").classList.toggle("active",actorView==="owner");
 $("#visitor-view").classList.toggle("active",actorView==="visitor");
}
function renderMemory(){
 const data=viewMemory(state,actorView),list=$("#memory-list");
 $("#role-label").textContent=actorView; list.replaceChildren();
 $("#memory-count").textContent=data?String(Object.keys(data).length):"—";
 if(!data){
  const blocked=E("div","memory-empty");
  blocked.append(E("strong","","角色权限隔离"),E("span","","访客无权读取主人私有记忆。本页不展示受保护的槽位及其值。"));
  list.append(blocked);
 }else{
  const entries=Object.entries(data);
  if(!entries.length){list.append(E("div","memory-empty","当前角色没有活动记忆")); }
  for(const [slot,value] of entries){
   const row=E("div","memory-item");
   row.append(E("span","slot-icon","◇"));
   const cell=E("div","memory-item-content");cell.append(E("small","",slot),E("strong","",value));
   row.append(cell);list.append(row);
  }
 }
 $("#tombstone-count").textContent=actorView==="owner"?String(state.tombstones.length):"—";
 const tomb=$("#tombstone-list");tomb.replaceChildren();
 if(actorView!=="owner"){tomb.append(E("span","no-data","该角色无权查看遗忘索引"));}
 else if(!state.tombstones.length){tomb.append(E("span","no-data","暂无遗忘记录"));}
 else for(const slot of state.tombstones) tomb.append(E("span","tombstone","⊘ "+slot));
 $("#replay").disabled=actorView!=="owner"||!state.tombstones.includes("长期目标／驾照");
 const audit=$("#audit-list");audit.replaceChildren();
 $("#audit-count").textContent=state.events.length+" EVENTS";
 const events=state.events.slice(0,6);
 if(!events.length){audit.append(E("p","no-data","当前尚无动作记录"));}
 for(const event of events){
  const row=E("div","audit-item");row.dataset.action=event.action;
  const head=E("div","audit-main");
  head.append(E("strong","","#"+String(event.step).padStart(2,"0")+" · "+event.action),
   E("span","",event.status));
  const desc=event.source!=="owner"?"未授权来源 / 不暴露目标记忆":
   [event.slot||"无目标槽位","原始输入不记录"].join(" · ");
  row.append(head,E("small","",desc));audit.append(row);
 }
}
function beforeAfter(result){
 const {event,before,after,hidden}=result;
 const slot=hidden?"[角色私有内容已屏蔽]":(event.slot||"未指定槽位");
 $("#before-slot").textContent=slot;
 $("#after-slot").textContent=slot;
 if(hidden){
  $("#before-value").textContent="无权查看";
  $("#after-value").textContent="拒绝访问";
  $("#diff-footnote").textContent="权限先行：无权读取旧值，也未执行任何写入。";
 }else if(event.status.includes("敏感")||event.slot?.includes("敏感")){
  $("#before-value").textContent="未读取";
  $("#after-value").textContent="没有写入";
  $("#diff-footnote").textContent="保护敏感内容：展示及审计均不回显原始输入。";
 }else if(event.mutated){
  $("#before-value").textContent=before===null?"（尚无此记忆）":before;
  $("#after-value").textContent=after===null?"（活动记忆已删除）":after;
  $("#diff-footnote").textContent=event.action==="FORGET"?
   "删除活动值；抑制标记只记录槽位，不保留被删除内容。":
   "仅模拟目标语义槽位变化，其他记忆保持不变。";
 }else{
  // Owner-facing view only; still do not show source or secret payload.
  const current=event.slot&&Object.hasOwn(state.owner,event.slot)?state.owner[event.slot]:null;
  $("#before-value").textContent=current??"（未读取或无此记忆）";
  $("#after-value").textContent=current??"（无状态变化）";
  $("#diff-footnote").textContent="策略没有批准写入；当前长期记忆不变。";
 }
 $("#diff-status").textContent=event.mutated?"已生成变更":"未发生变更";
}
function showResult(result){
 const event=result.event;
 $("#decision-empty").classList.add("hidden");
 const panel=$("#decision-result");
 panel.classList.remove("hidden");panel.dataset.action=event.action;
 $("#result-status").textContent=event.status;
 $("#result-action").textContent=event.action;
 $("#result-label").textContent=labels[event.action]||"受控演示动作";
 $("#action-glyph").textContent=glyphs[event.action]||"?";
 $("#result-reason").textContent=event.reason;
 $("#rule-reason").textContent=event.fact??"来源与状态检查";
 beforeAfter(result);
 renderMemory();
}
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function runTask(kind="scenario"){
 if(busy)return;
 const nonce=++runNonce;busy=true;
 $("#run").disabled=true;$("#pipeline-status").textContent="正在运行本地规则...";
 stages.forEach(s=>s.className="stage");
 const sc=getScenario(selected);const text=$("#message").value;
 const isVisitor=sc.source!=="owner";
 const isSensitive=/(?:密码|口令|验证码|令牌|密钥|api[_\s-]?key|bearer|password|secret)/i.test(text);
 const result=kind==="replay"?replayForgotten(state):runScenario(state,selected,text);
 // The engine already executed synchronously; animation illustrates policy stages.
 const stopIndex=kind==="replay"?3:(isVisitor?0:isSensitive?1:(result.event.action==="CLARIFY"?2:3));
 for(let i=0;i<stages.length;i++){
  if(nonce!==runNonce)return;
  stages[i].classList.add("active");
  await sleep(window.matchMedia("(prefers-reduced-motion:reduce)").matches?0:125);
  if(nonce!==runNonce)return;
  stages[i].classList.remove("active");
  stages[i].classList.add(i===stopIndex&&result.event.action==="REJECT"?"fail":(i>stopIndex?"":"done"));
  if(i>=stopIndex)break;
 }
 if(nonce!==runNonce)return;
 $("#pipeline-status").textContent=result.event.status;
 if(isSensitive&&sc.id!=="secret")$("#message").value="（敏感输入已清空，不留在演示记录中）";
 showResult(result);busy=false;$("#run").disabled=false;$("#run").textContent="再次运行 →";
}
function reset(){
 ++runNonce;busy=false;resetLab(state);
 $("#decision-result").classList.add("hidden");$("#decision-empty").classList.remove("hidden");
 stages.forEach(s=>s.className="stage");$("#pipeline-status").textContent="已重置";
 $("#run").disabled=false;$("#run").textContent="运行决策 →";
 selectScenario("add");
}
function attach(){
 $("#run").addEventListener("click",()=>runTask());
 $("#reset").addEventListener("click",reset);
 $("#replay").addEventListener("click",()=>runTask("replay"));
 $("#owner-view").addEventListener("click",()=>{actorView="owner";renderViewTabs();renderMemory()});
 $("#visitor-view").addEventListener("click",()=>{actorView="visitor";renderViewTabs();renderMemory()});
 // Only same-origin, precomputed aggregate stats. No raw conversation or model access.
 fetch("./lab/metrics.json",{cache:"no-store"}).then(r=>r.ok?r.json():null).then(data=>{
  if(!data)return;
  const count=data?.holdout?.total,correct=data?.holdout?.correct;
  if(Number.isInteger(count)&&Number.isInteger(correct)&&count>0)
   $("#metric-accuracy").textContent=correct+"/"+count;
  const tests=data?.tests;
  if(Number.isInteger(tests)&&tests>0)$("#metric-tests").textContent=tests+" PASS";
 }).catch(()=>{});
 const demo=new URLSearchParams(window.location.search).get("demo");
 if(demo&&getScenario(demo)){
  // Screenshot / presenter mode executes the SAME deterministic engine immediately;
  // it does not paint a fabricated outcome or contact any remote model.
  selectScenario(demo);
  const result=runScenario(state,demo,$("#message").value);
  stages.forEach(stage=>stage.classList.add("done"));
  $("#pipeline-status").textContent=result.event.status;
  showResult(result);
  $("#run").textContent="再次运行 →";
 }
 else selectScenario("add");
}
attach();
