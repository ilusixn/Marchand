PAGES.training=renderTraining;
TC.sec='quick';
const LOCALP=['lmstudio','jan','koboldcpp','textgen','llamacpp','vllm','gpt4all','localai'];
const TRS={live:null,timer:null,view:null,sel:null,form:null};
renderTeach=renderTraining;
const TSECS=[['quick','Train with Claude'],['train','Advanced'],['results','Results'],['coder','Marchand Coder'],['mine','Add your model'],['re','Reverse engineering'],['tasks','Your tasks'],['setup','Teacher'],['lessons','Lessons'],['examples','Examples'],['build','My AIs'],['gpu','GPU']];
function modelOptions(sel,filter,cur,none){sel.innerHTML=none?'<option value="">'+esc(none)+'</option>':'';(ST.groups||[]).filter(g=>filter(g.provider)).forEach(g=>{if(!g.models.length)return;const og=el('optgroup');og.label=g.label;g.models.forEach(m=>{const o=el('option',null,esc(m.name));o.value=m.id;og.appendChild(o)});sel.appendChild(og)});if(cur!=null)sel.value=cur}
async function renderTraining(){
  clearInterval(TRS.timer);const root=$('#plug');root.innerHTML='';
  root.appendChild(SEC(root,TSECS,TC.sec,k=>{TC.sec=k;TRS.view=null;renderTraining()}));
  const b=el('div','pbody');root.appendChild(b);
  const fn={quick:trQuick,train:trTrain,results:trResults,coder:trCoder,mine:trMine,re:trRE,tasks:trTasks,setup:tSetup,lessons:tLessons,examples:tExamples,build:tBuild,gpu:trGpu}[TC.sec];
  await fn(b)}

function pickTasks(mode,allT,sel,quick){const av=allT.filter(t=>t.builtin&&t.available);
  if(mode==='quick')return quick;if(mode==='full')return av.map(t=>t.id);if(mode==='re')return av.filter(t=>t.lang==='reverse').map(t=>t.id);
  if(mode==='langs'){const seen={};return av.filter(t=>t.lang!=='reverse'&&!seen[t.lang]&&(seen[t.lang]=1)).map(t=>t.id)}
  return av.filter(t=>sel.has(t.lang)).map(t=>t.id)}
async function trQuick(b){
  await loadModels();const live=(await api('/api/training/sessions')).find(s=>s.status==='running');
  if(TRS.view||live)return trLive(b,TRS.view||live.id);
  const cloud=(ST.groups||[]).filter(g=>g.provider!=='ollama'&&!LOCALP.includes(g.provider));const cc=cloud.find(g=>g.provider==='claude-code');const local=(ST.groups||[]).find(g=>g.provider==='ollama');
  const s=await api('/api/settings');
  b.appendChild(el('div','hero','<h2>Train your AI with Claude</h2><p>Claude works through '+'real coding tasks with your local AI: your AI tries each one, the tests decide pass or fail, and Claude explains every mistake, writes the lessons and shows the right solution. Then your AI is tested again so you see the improvement. Press <b>Save AI</b> at the end to keep the result.</p>'));
  if(!(ST.groups||[]).some(g=>g.provider!=='claude-code'&&g.models.length)){b.appendChild(el('div','err','You have no local model yet. Add one in the "Add your model" tab, or install Marchand Coder.'));return}
  if(!cloud.length){b.appendChild(el('div','err','No teacher available. Install Claude Code and log in to use your Claude subscription, or add a key in Models &gt; Cloud and local servers.'));return}
  const f=el('div','pform quick','<div class="trgrid"><div><label>Your AI (the student)</label><select id="qStu"></select></div><div><label>Teacher</label><select id="qTea"></select></div></div>'+
    '<div class="trgrid"><div><label>Teacher effort</label><select id="qEff"><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="xhigh">Extra high</option><option value="max">Max (ultra)</option></select><div class="meta">For Claude on your subscription. Higher effort teaches better and uses more of your limits.</div></div>'+
    '<div><label>How long?</label><select id="qLen"><option value="quick">Quick: 6 Python tasks (10-20 min)</option><option value="langs">Every language: 1 task each (about 30 min)</option><option value="re">Reverse engineering: 9 tasks</option><option value="pick">Pick languages myself...</option><option value="full">Everything my PC can run (1-3 hours)</option></select></div></div><div id="qPick" style="display:none"></div>'+
    '<div class="prow" style="margin-top:16px"><button class="btn pri big" id="qGo">Start teaching</button><span class="err" id="qErr"></span></div>'+
    '<div class="meta">Uses the Advanced training defaults: 2 rounds, teacher demonstrations, lessons condensed at the end. Code runs in a sandbox folder on this PC.</div>');b.appendChild(f);
  modelOptions(f.querySelector('#qStu'),p=>p!=='claude-code',TRS.pre||(ST.model&&!ST.model.startsWith('claude-code::')?ST.model:''));TRS.pre=null;
  modelOptions(f.querySelector('#qTea'),p=>p!=='ollama'&&!LOCALP.includes(p),cc?((s.teacher_model||'').startsWith('claude-code::')?s.teacher_model:'claude-code::opus'):(s.teacher_model||cloud[0].models[0].id));
  f.querySelector('#qEff').value=s.cc_effort||'high';
  const langs=await api('/api/training/languages');const allT=await api('/api/training/tasks');const QS=new Set(['python']);
  const pickBox=f.querySelector('#qPick');
  const drawPick=()=>{pickBox.innerHTML='<div class="meta" style="margin:6px 0">Tick the languages to train. Greyed ones need a tool installed on this PC.</div><div class="langchips"></div>';const c=pickBox.querySelector('.langchips');
    Object.entries(langs).forEach(([k,v])=>{const ok=v.available>0;const chip=el('label','lchip'+(ok?'':' off')+(QS.has(k)?' on':''),'<input type="checkbox" '+(QS.has(k)?'checked ':'')+(ok?'':'disabled ')+'> '+esc(v.name)+' <span class="meta">'+v.available+(v.available<v.tasks?'/'+v.tasks:'')+'</span>');chip.title=ok?'':v.why;chip.querySelector('input').onchange=e=>{e.target.checked?QS.add(k):QS.delete(k);chip.classList.toggle('on',e.target.checked)};c.appendChild(chip)})};
  drawPick();f.querySelector('#qLen').onchange=e=>{pickBox.style.display=e.target.value==='pick'?'':'none'};
  const missing=Object.values(langs).filter(v=>v.available<v.tasks);if(missing.length)f.appendChild(el('div','meta','Some languages are locked because their tools are missing on this PC ('+missing.map(v=>esc(v.name)+': '+esc(v.why)).join('; ')+'). Install them to unlock more tasks.'));
  f.querySelector('#qGo').onclick=async()=>{const teacherId=f.querySelector('#qTea').value;await api('/api/settings',{teacher_model:teacherId,cc_effort:f.querySelector('#qEff').value});
    const quick=['pagination','mutable_default','csv_quotes','sql_injection','rename','dedupe_perf'];
    const r=await api('/api/training/start',{name:'Taught by '+teacherId.replace('claude-code::','Claude ').replace('::',' '),student:f.querySelector('#qStu').value,teacher:teacherId,demos:'teacher',rounds:2,max_steps:25,learn:true,keep_successes:true,persona:true,consolidate:true,tasks:pickTasks(f.querySelector('#qLen').value,allT,QS,quick)});
    if(r.error){f.querySelector('#qErr').textContent=r.error;return}TRS.view=r.id;renderTraining()}}
async function trTrain(b){
  await loadModels();const live=(await api('/api/training/sessions')).find(s=>s.status==='running');
  if(TRS.view||live){return trLive(b,TRS.view||live.id)}
  const tasks=await api('/api/training/tasks');const s=await api('/api/settings');
  b.appendChild(el('div','note','Train a local AI on real coding tasks. Each task has tests, so the score is measured, not guessed. A teacher (Claude, Grok or any model you added) reviews every failure, writes lessons, and shows the right solution. The last round re-tests your AI so you can see how much it improved.'));
  const F=TRS.form||(TRS.form={student:'',teacher:s.teacher_model||'',demos:'',rounds:2,max_steps:25,learn:true,keep_successes:true,persona:true,consolidate:true,save_as:'',tasks:null});
  const f=el('div','pform');b.appendChild(f);
  f.innerHTML='<div class="trgrid"><div><label>1. Student: the AI you want to train</label><select id="trStu"></select><div class="meta">Local models can be saved as a new AI at the end.</div></div><div><label>2. Teacher (optional)</label><select id="trTea"></select><div class="meta">Any cloud model, including Claude on your subscription.</div></div></div>'+
    '<label>3. How should it learn from mistakes?</label><select id="trDemo"><option value="teacher">Teacher reviews and shows the solution (best)</option><option value="both">Teacher, plus the built-in reference solution</option><option value="reference">Built-in reference solutions only (free, no teacher needed)</option><option value="none">No demonstrations (only lessons or a plain test)</option></select>'+
    '<div class="trgrid"><div><label>Rounds</label><select id="trRounds"><option value="1">1 (just measure)</option><option value="2">2 (learn, then re-test)</option><option value="3">3 (learn twice, then re-test)</option></select></div><div><label>Max steps per task</label><input id="trSteps" type="number" min="5" max="80"></div></div>'+
    '<div class="prow"><input type="checkbox" id="trLearn" style="width:auto"><label for="trLearn">Write lessons from mistakes</label><input type="checkbox" id="trKeep" style="width:auto;margin-left:14px"><label for="trKeep">Keep successful attempts as examples</label></div>'+
    '<div class="prow"><input type="checkbox" id="trPers" style="width:auto"><label for="trPers">Use the Marchand Coder persona</label><input type="checkbox" id="trCons" style="width:auto;margin-left:14px"><label for="trCons">Let the teacher condense lessons at the end</label></div>'+
    '<label>4. Tasks</label><div class="prow"><button class="btn sm" id="trAll">All</button><button class="btn sm" id="trNone">None</button><button class="btn sm" id="trQuick">Quick 6 (Python)</button><span class="meta" id="trCount"></span></div><div class="trtasks" id="trList"></div>'+
    '<label>5. Save the trained AI as (optional, local students only)</label><input id="trSave" placeholder="e.g. my-coder-v1">'+
    '<div class="hwarn">Training runs code written by the AIs on this PC, inside a sandbox folder in ~/.marchand/training. Destructive commands are blocked, but only train with models you trust. Teacher calls use your cloud credits or plan limits.</div>'+
    '<div class="prow"><button class="btn pri" id="trGo">Start training</button><span class="err" id="trErr"></span></div>';
  modelOptions(f.querySelector('#trStu'),p=>true,F.student||ST.model||'');
  modelOptions(f.querySelector('#trTea'),p=>p!=='ollama',F.teacher,'(no teacher)');
  f.querySelector('#trDemo').value=F.demos||(F.teacher?'teacher':'reference');f.querySelector('#trRounds').value=String(F.rounds);f.querySelector('#trSteps').value=F.max_steps;
  [['trLearn','learn'],['trKeep','keep_successes'],['trPers','persona'],['trCons','consolidate']].forEach(([id,k])=>{f.querySelector('#'+id).checked=!!F[k]});f.querySelector('#trSave').value=F.save_as;
  const sel=new Set(F.tasks||tasks.filter(t=>t.builtin&&t.available&&t.lang==='python').map(t=>t.id));const list=f.querySelector('#trList');
  const LN={python:'Python',javascript:'JavaScript',typescript:'TypeScript',c:'C',cpp:'C++',csharp:'C#',java:'Java',go:'Go',rust:'Rust',php:'PHP',ruby:'Ruby',perl:'Perl',lua:'Lua',bash:'Bash',sql:'SQL',reverse:'Reverse engineering',custom:'Your tasks'};
  const order=Object.keys(LN);const byLang={};tasks.forEach(t=>{(byLang[t.lang||'python']=byLang[t.lang||'python']||[]).push(t)});
  const draw=()=>{list.innerHTML='';order.filter(k=>byLang[k]).forEach(k=>{const ts=byLang[k];const av=ts.filter(t=>t.available!==false);const head=el('div','lhead','<b>'+esc(LN[k])+'</b> <span class="meta">'+av.length+'/'+ts.length+' can run</span>'+(av.length<ts.length?' <span class="del">'+esc(ts.find(t=>t.available===false).why)+'</span>':''));
      const tg=el('button','btn sm','Select all');tg.onclick=()=>{const all=av.every(t=>sel.has(t.id));av.forEach(t=>all?sel.delete(t.id):sel.add(t.id));draw()};head.appendChild(tg);list.appendChild(head);
      ts.forEach(t=>{const off=t.available===false;const lab=el('label','trtask'+(off?' off':''),'<input type="checkbox"'+(sel.has(t.id)?' checked':'')+(off?' disabled':'')+'> <span>'+esc(t.title)+'</span><span class="meta">'+'&#9733;'.repeat(t.level||1)+'</span>');lab.querySelector('input').onchange=e=>{e.target.checked?sel.add(t.id):sel.delete(t.id);count()};list.appendChild(lab)})});count()};
  const count=()=>f.querySelector('#trCount').textContent=sel.size+' of '+tasks.filter(t=>t.available!==false).length+' selected';
  f.querySelector('#trAll').onclick=()=>{tasks.filter(t=>t.available!==false).forEach(t=>sel.add(t.id));draw()};f.querySelector('#trNone').onclick=()=>{sel.clear();draw()};
  f.querySelector('#trQuick').onclick=()=>{sel.clear();['pagination','mutable_default','csv_quotes','sql_injection','rename','dedupe_perf'].forEach(x=>sel.add(x));draw()};draw();
  f.querySelector('#trGo').onclick=async()=>{
    Object.assign(F,{student:f.querySelector('#trStu').value,teacher:f.querySelector('#trTea').value,demos:f.querySelector('#trDemo').value,rounds:+f.querySelector('#trRounds').value,max_steps:+f.querySelector('#trSteps').value,
      learn:f.querySelector('#trLearn').checked,keep_successes:f.querySelector('#trKeep').checked,persona:f.querySelector('#trPers').checked,consolidate:f.querySelector('#trCons').checked,save_as:f.querySelector('#trSave').value.trim(),tasks:[...sel]});
    const r=await api('/api/training/start',F);if(r.error){f.querySelector('#trErr').textContent=r.error;return}TRS.view=r.id;renderTraining()};
}
function resultsTable(ses){
  const rounds=ses.rounds||[];if(!rounds.length)return el('div','meta','No results yet.');
  const tasks=[];rounds.forEach(r=>r.results.forEach(x=>{if(!tasks.find(t=>t.task===x.task))tasks.push({task:x.task,title:x.title})}));
  let h='<table class="htable trtable"><tr><th>Task</th>'+rounds.map(r=>'<th>Round '+r.round+'</th>').join('')+'</tr>';
  tasks.forEach(t=>{h+='<tr><td>'+esc(t.title)+'</td>'+rounds.map(r=>{const x=r.results.find(y=>y.task===t.task);if(!x)return '<td class="meta">-</td>';return '<td>'+(x.passed?'<span class="add">&#10004; pass</span>':'<span class="del">&#10008; fail</span>')+'<div class="meta">'+x.tools+' steps, '+x.seconds+'s'+(x.lessons?', '+x.lessons+' lessons':'')+(x.demo?', '+x.demo+' demo '+(x.demo_passed?'&#10004;':'&#10008;'):'')+'</div></td>'}).join('')+'</tr>'});
  h+='<tr><th>Pass rate</th>'+rounds.map(r=>{const n=r.results.length,p=r.results.filter(x=>x.passed).length;return '<th>'+(n?Math.round(100*p/n):0)+'% ('+p+'/'+n+')</th>'}).join('')+'</tr></table>';
  return el('div',null,h)}
function rateBars(ses){const d=el('div','trbars');(ses.rounds||[]).forEach(r=>{const n=r.results.length,p=r.results.filter(x=>x.passed).length,pct=n?Math.round(100*p/n):0;d.appendChild(el('div','trbar','<div class="trcol"><i style="height:'+pct+'%"></i></div><b>'+pct+'%</b><span class="meta">Round '+r.round+'</span>'))});return d}
async function trLive(b,id){
  TRS.view=id;const head=el('div');const body=el('div');b.append(head,body);
  async function tick(){const ses=await api('/api/training/session?id='+encodeURIComponent(id));if(ses.error){TRS.view=null;clearInterval(TRS.timer);renderTraining();return}
    const c=ses.counters||{},cur=ses.current||{},run=ses.status==='running';const done=(ses.rounds||[]).reduce((a,r)=>a+r.results.length,0),total=(ses.config.tasks||[]).length*(ses.config.rounds||1);
    head.innerHTML='';head.appendChild(el('h3',null,esc(ses.name)+' <span class="meta">'+esc(ses.status)+'</span>'));
    head.appendChild(el('div','note','Student <b>'+esc(ses.config.student)+'</b>'+(ses.config.teacher?' &middot; teacher <b>'+esc(ses.config.teacher)+'</b>':'')+' &middot; '+esc(ses.config.demos)+' demonstrations'));
    if(run){head.appendChild(el('div','bar','<i style="width:'+Math.round(100*done/Math.max(1,total))+'%"></i>'));head.appendChild(el('div','note','Round '+(cur.round||'-')+': '+esc(cur.title||'')+' &middot; '+esc(cur.phase||'')+' ('+done+'/'+total+' attempts done)'))}
    head.appendChild(el('div','trcount','<span>'+c.student_runs+' student runs</span><span>'+c.teacher_calls+' teacher calls</span><span>'+c.lessons+' new lessons</span><span>'+c.examples+' examples saved</span><span>~'+Math.round((c.tokens_est||0)/1000)+'k teacher tokens (estimate)</span>'));
    const a=el('div','prow');
    if(run){const st=el('button','btn','Stop');st.onclick=()=>api('/api/training/stop',{id});a.appendChild(st)}
    else{const nb=el('button','btn','New training');nb.onclick=()=>{TRS.view=null;renderTraining()};a.appendChild(nb);
      if(ses.saved_ai){a.appendChild(el('span','note','Saved as <b>'+esc(ses.saved_ai)+'</b> &middot; '));const u=el('button','btn sm pri','Use it');u.onclick=()=>{ST.model=ses.saved_ai;LS.set('model',ses.saved_ai);loadModels().then(()=>{$('#model').value=ses.saved_ai;setMode('code')})};a.appendChild(u)}
      else if((ses.config.student||'').indexOf('::')<0&&ses.status!=='error'){const nm=el('input');nm.id='trSaveName';nm.value=(ses.config.student.split(':')[0]+'-trained').replace(/[^a-z0-9.-]/gi,'-').toLowerCase();nm.style.maxWidth='220px';
        const sv=el('button','btn pri big','Save AI');sv.id='trSaveBtn';sv.onclick=async()=>{sv.disabled=true;sv.textContent='Saving...';const r=await api('/api/training/save-ai',{id,name:nm.value});if(r.error){alert(r.error);sv.disabled=false;sv.textContent='Save AI';return}
          a.innerHTML='';a.appendChild(el('span','note','&#10004; Saved as <b>'+esc(r.name)+'</b>. It is in the model picker.'));const u=el('button','btn sm pri','Use it now');u.onclick=()=>{ST.model=r.name;LS.set('model',r.name);loadModels().then(()=>{$('#model').value=r.name;setMode('code')})};a.appendChild(u);clearInterval(TRS.timer);await loadModels()};
        a.appendChild(el('span','note','Name:'));a.appendChild(nm);a.appendChild(sv)}}
    head.appendChild(a);
    body.innerHTML='';body.appendChild(rateBars(ses));body.appendChild(resultsTable(ses));
    const lg=el('details','card');lg.open=run;lg.innerHTML='<summary><span class="nm">Activity log</span></summary><div class="out" style="max-height:340px">'+esc((ses.log||[]).slice(-150).join('\n'))+'</div>';body.appendChild(lg);
    const o=lg.querySelector('.out');o.scrollTop=o.scrollHeight;
    if(!run)clearInterval(TRS.timer)}
  await tick();clearInterval(TRS.timer);TRS.timer=setInterval(()=>{if(!['train','quick'].includes(TC.sec)||$('#plug').style.display==='none'||!$('#tTraining').classList.contains('on')){clearInterval(TRS.timer);return}tick()},1200)}
async function trResults(b){
  const list=await api('/api/training/sessions');
  if(TRS.sel){const ses=await api('/api/training/session?id='+encodeURIComponent(TRS.sel));const back=el('button','btn sm','&larr; All results');back.onclick=()=>{TRS.sel=null;renderTraining()};b.appendChild(back);
    if(!ses.error){b.appendChild(el('h3',null,esc(ses.name)));b.appendChild(el('div','note',esc(ses.config.student)+(ses.config.teacher?' taught by '+esc(ses.config.teacher):'')+' &middot; '+new Date(ses.started*1000).toLocaleString()+' &middot; '+esc(ses.status)));b.appendChild(rateBars(ses));b.appendChild(resultsTable(ses))}return}
  if(!list.length){b.appendChild(el('div','psec','No training yet. Start one in Train.'));return}
  const g=el('div','grid');list.forEach(s=>{const c=el('div','pcard');c.appendChild(el('h4',null,'<span style="flex:1">'+esc(s.name)+'</span><span class="meta">'+esc(s.status)+'</span>'));
    c.appendChild(el('p',null,'Pass rate per round: <b>'+esc(s.summary||'-')+'</b>'));c.appendChild(el('div','meta',esc((s.config||{}).student||'')+' &middot; '+new Date(s.started*1000).toLocaleString()));
    const a=el('div','acts');const o=el('button','btn sm pri','Open');o.onclick=()=>{if(s.status==='running'){TC.sec='train';TRS.view=s.id}else TRS.sel=s.id;renderTraining()};
    const d=el('button','btn sm','Delete');d.onclick=async()=>{if(confirm('Delete this training report? Lessons and examples stay.')){await api('/api/training/delete',{id:s.id});renderTraining()}};a.append(o,d);c.appendChild(a);g.appendChild(c)});b.appendChild(g)}
async function trCoder(b){
  const rec=await api('/api/training/recommend');const ais=await api('/api/ais');const have=ais.find(a=>a.pack===true);
  b.appendChild(el('div','pcard',`<h4>&#129302; Marchand Coder</h4><p>A ready-made local coding AI that works the way I work: it reads before editing, makes small changes, runs the tests after every edit, fixes the root cause and never claims success it did not prove. It is built from:</p>
  <ul><li>the best Ollama coding model your PC runs well,</li><li>90 expert rules for 15 programming languages plus reverse engineering, and a careful engineering persona,</li><li>verified worked examples (solutions that really pass their tests),</li><li>plus every lesson you have taught it so far.</li></ul>
  <p class="meta">Honest note: this shapes the model's behaviour through its built-in instructions and examples; it does not change its weights, so it will not match a cloud model like Opus on hard problems. To go further, train it (Train tab) and, with an NVIDIA GPU, fine-tune it. AMD graphics cards (Radeon) run it through Ollama (ROCm or Vulkan) and work with every training feature except GPU fine-tuning, which needs NVIDIA.</p>`));
  const f=el('div','pform','<label>Base model (recommended for your PC: <b>'+esc(rec.base)+'</b>)</label><select id="cbBase"></select><label>Name</label><input id="cbName" value="marchand-coder"><div class="prow"><button class="btn pri" id="cbGo">'+(have?'Rebuild Marchand Coder':'Install Marchand Coder')+'</button><button class="btn" id="cbBench">Benchmark it</button></div><div class="bar"><i id="cbBar"></i></div><div class="note" id="cbMsg"></div>');b.appendChild(f);
  const bases=['qwen2.5-coder:32b','qwen3-coder:30b','qwen2.5-coder:14b','qwen2.5-coder:7b','qwen2.5-coder:3b','qwen2.5-coder:1.5b'];
  bases.forEach(x=>{const o=el('option',null,esc(x)+(x===rec.base?' (recommended)':''));o.value=x;f.querySelector('#cbBase').appendChild(o)});f.querySelector('#cbBase').value=rec.base;
  if(have)f.querySelector('#cbName').value=have.name;
  f.querySelector('#cbGo').onclick=async()=>{const bt=f.querySelector('#cbGo');bt.disabled=true;const msg=f.querySelector('#cbMsg'),bar=f.querySelector('#cbBar');let err=null,name=null;
    await sseJson('/api/training/coder',{base:f.querySelector('#cbBase').value,name:f.querySelector('#cbName').value},ev=>{if(ev.error){err=ev.error;msg.textContent='Error: '+ev.error}else{if(ev.status)msg.textContent=ev.status;if(ev.pct!=null)bar.style.width=ev.pct+'%';if(ev.name)name=ev.name}});
    bt.disabled=false;if(!err&&name){bar.style.width='100%';msg.innerHTML='Ready: <b>'+esc(name)+'</b> is in the model picker.';await loadModels();ST.model=name;LS.set('model',name);$('#model').value=name}};
  f.querySelector('#cbBench').onclick=async()=>{const name=f.querySelector('#cbName').value;await loadModels();if(!(ST.groups||[]).some(g=>g.models.some(m=>m.id===name))){alert('Install Marchand Coder first.');return}
    const r=await api('/api/training/start',{name:'Benchmark '+name,student:name,teacher:'',demos:'none',rounds:1,learn:false,keep_successes:false,persona:false,tasks:['pagination','slugify','mutable_default','csv_quotes','binary_search','sql_injection','rename','dedupe_perf','dates','word_freq']});
    if(r.error){alert(r.error);return}TC.sec='train';TRS.view=r.id;renderTraining()};
}
async function trTasks(b){
  const tasks=(await api('/api/training/tasks')).filter(t=>!t.builtin);
  b.appendChild(el('div','note','Train your AI on your own code. Marchand copies the folder into a sandbox for every attempt (your original is never touched) and runs your test command to decide pass or fail.'));
  const f=el('div','pform','<label>Title</label><input id="ctT" placeholder="Fix the save bug"><label>Project folder</label><div class="prow"><input id="ctF" style="flex:1"><button class="btn" id="ctB">Browse</button></div><label>What should the AI do?</label><textarea id="ctP" rows="3" placeholder="The test in tests/test_save.py fails. Fix the bug in save.py."></textarea><label>Test command (must exit with code 0 when the task is done)</label><input id="ctC" placeholder="python -m pytest -q tests/test_save.py"><div class="prow"><button class="btn pri" id="ctGo">Add task</button><span class="err" id="ctE"></span></div>');b.appendChild(f);
  f.querySelector('#ctB').onclick=async()=>{if(window.pywebview&&pywebview.api&&pywebview.api.pick_folder){const p=await pywebview.api.pick_folder('');if(p)f.querySelector('#ctF').value=p}else{f.querySelector('#ctF').value=ST.project||''}};
  f.querySelector('#ctGo').onclick=async()=>{const r=await api('/api/training/custom',{title:f.querySelector('#ctT').value,folder:f.querySelector('#ctF').value,prompt:f.querySelector('#ctP').value,test_cmd:f.querySelector('#ctC').value});if(r.error){f.querySelector('#ctE').textContent=r.error;return}renderTraining()};
  b.appendChild(el('div','psec','Your tasks'));if(!tasks.length)b.appendChild(el('div','meta','None yet.'));
  const g=el('div','grid');tasks.forEach(t=>{const c=el('div','pcard');c.appendChild(el('h4',null,esc(t.title)));c.appendChild(el('p',null,esc(t.prompt)));c.appendChild(el('div','meta',esc(t.folder)+'<br><code>'+esc(t.test_cmd)+'</code>'));
    const d=el('button','btn sm','Delete');d.onclick=async()=>{await api('/api/training/custom/delete',{id:t.id});renderTraining()};c.appendChild(d);g.appendChild(c)});b.appendChild(g)}
async function trGpu(b){
  b.appendChild(el('div','note','Checking your PC...'));const ck=await api('/api/finetune/check');b.innerHTML='';
  b.appendChild(el('div','pcard','<h4>Real fine-tuning (changes the model\'s weights)</h4><p>Uses your saved examples (from training and thumbs-up) to train a LoRA adapter with Unsloth, exports a GGUF file and adds it to Ollama as a new model. This is how you make a local model genuinely better, beyond instructions.</p>'+
    '<table class="htable"><tr><td>NVIDIA graphics card</td><td>'+(ck.nvidia?'<span class="add">&#10004; '+esc(ck.gpu)+' ('+ck.vram_gb+' GB)</span>':'<span class="del">&#10008; not found</span> (fine-tuning needs an NVIDIA GPU with 8 GB+)')+(ck.vendor==='amd'?'<br><b>AMD card detected ('+esc(ck.gpu)+').</b> Your AMD GPU runs models and makes pictures, but this fine-tuning step needs NVIDIA (CUDA). Everything else in Training (Train with Claude, Marchand Coder, lessons) works on any PC.':'')+'</td></tr>'+
    '<tr><td>Python packages</td><td>'+(ck.missing.length?'<span class="del">&#10008; missing: '+esc(ck.missing.join(', '))+'</span><br>Install with: <code>'+esc(ck.pip)+'</code>':'<span class="add">&#10004; ready</span>')+'</td></tr>'+
    '<tr><td>Good examples</td><td>'+(ck.examples>=10?'<span class="add">&#10004; '+ck.examples+'</span>':'<span class="del">'+ck.examples+'</span> (collect at least 10, ideally 100+, with Train)')+'</td></tr></table>'));
  const f=el('div','pform','<label>Base model</label><select id="ftB"></select><label>Or a Hugging Face model id (advanced)</label><input id="ftH" placeholder="unsloth/Qwen2.5-Coder-7B-Instruct-bnb-4bit"><div class="trgrid"><div><label>Epochs</label><input id="ftE" type="number" value="2" min="1" max="10"></div><div><label>Learning rate</label><input id="ftL" value="0.0002"></div></div><label>New model name</label><input id="ftN" value="marchand-tuned"><div class="prow"><button class="btn pri" id="ftGo">Start fine-tuning</button><button class="btn" id="ftStop" style="display:none">Stop</button><span class="err" id="ftE2"></span></div><div class="out" id="ftLog" style="display:none;max-height:360px;overflow:auto;white-space:pre-wrap;font:12px ui-monospace,monospace;background:var(--code);padding:10px;border-radius:8px"></div>');b.appendChild(f);
  ck.bases.forEach(x=>{const o=el('option',null,esc(x.name)+' (needs ~'+x.vram+' GB VRAM)');o.value=x.name;f.querySelector('#ftB').appendChild(o)});
  f.querySelector('#ftGo').onclick=async()=>{const r=await api('/api/finetune/start',{base:f.querySelector('#ftB').value,hf_base:f.querySelector('#ftH').value.trim(),epochs:+f.querySelector('#ftE').value,lr:+f.querySelector('#ftL').value,name:f.querySelector('#ftN').value});
    if(r.error){f.querySelector('#ftE2').textContent=r.error;return}const lg=f.querySelector('#ftLog');lg.style.display='';f.querySelector('#ftStop').style.display='';f.querySelector('#ftStop').onclick=()=>api('/api/finetune/stop',{id:r.id});
    const t=setInterval(async()=>{const j=await api('/api/finetune/job?id='+r.id);lg.textContent=(j.log||[]).join('\n')+'\n['+j.status+']';lg.scrollTop=lg.scrollHeight;if(j.status!=='running'){clearInterval(t);f.querySelector('#ftStop').style.display='none';loadModels()}},1500)};
}

async function trMine(b){
  await loadModels(true);
  b.appendChild(el('div','hero','<h2>Add your own AI model</h2><p>Bring any model you like and train it here: a model from Ollama or Hugging Face, a .gguf file you downloaded, or a model that runs in another program (LM Studio, Jan, KoboldCpp, llama.cpp, vLLM, text-generation-webui...). Once it is added it also appears in the model picker under the chat.</p>'));
  const s1=el('div','pform','<h4>1. From Ollama or Hugging Face</h4><label>Model name (ollama.com/library) or a Hugging Face model such as hf.co/user/repo:Q4_K_M</label><div class="prow"><input id="mnName" placeholder="qwen2.5-coder:7b"><button class="btn pri" id="mnGo">Download</button></div><div class="bar"><i id="mnBar"></i></div><div class="meta" id="mnMsg"></div>');
  const l1=el('div','prow');l1.appendChild(linkEl('https://ollama.com/search','Browse every Ollama model'));l1.appendChild(linkEl('https://huggingface.co/models?library=gguf&sort=trending','Hugging Face GGUF models'));s1.appendChild(l1);b.appendChild(s1);
  s1.querySelector('#mnGo').onclick=async()=>{const n=s1.querySelector('#mnName').value.trim();if(!n)return;await pullModel(n,s1.querySelector('#mnBar'),s1.querySelector('#mnMsg'));await loadModels(true);s1.querySelector('#mnMsg').textContent='Added: '+n;renderTraining()};
  const s2=el('div','pform','<h4>2. From a .gguf file on this PC</h4><label>Full path to the .gguf file</label><input id="mgPath" placeholder="C:\\Models\\my-model-Q4_K_M.gguf"><label>Name for it</label><input id="mgName" placeholder="my-model"><div class="prow"><button class="btn pri" id="mgGo">Import into Ollama</button><span class="meta" id="mgMsg"></span></div>');b.appendChild(s2);
  s2.querySelector('#mgGo').onclick=async()=>{const m=s2.querySelector('#mgMsg');m.textContent='Importing (large files take a while)...';const r=await api('/api/training/import-model',{path:s2.querySelector('#mgPath').value,name:s2.querySelector('#mgName').value});m.textContent=r.error?('Error: '+r.error):('Added: '+r.name);if(!r.error){await loadModels(true);renderTraining()}};
  const SRV=[['lmstudio','LM Studio','http://127.0.0.1:1234/v1'],['jan','Jan','http://127.0.0.1:1337/v1'],['koboldcpp','KoboldCpp','http://127.0.0.1:5001/v1'],['textgen','text-generation-webui','http://127.0.0.1:5000/v1'],['llamacpp','llama.cpp server','http://127.0.0.1:8080/v1'],['vllm','vLLM','http://127.0.0.1:8000/v1'],['gpt4all','GPT4All','http://127.0.0.1:4891/v1'],['localai','LocalAI','http://127.0.0.1:8081/v1'],['custom','Any other OpenAI-style server','']];
  const s3=el('div','pform','<h4>3. A model running in another program</h4><label>Program</label><select id="msType"></select><label>Address</label><input id="msBase"><label>Key (only if the server needs one)</label><input id="msKey" type="password"><div class="prow"><button class="btn pri" id="msGo">Connect and test</button><span class="meta" id="msMsg"></span></div>');b.appendChild(s3);
  SRV.forEach(([id,l])=>{const o=el('option',null,esc(l));o.value=id;s3.querySelector('#msType').appendChild(o)});
  const fill=()=>{const x=SRV.find(v=>v[0]===s3.querySelector('#msType').value);s3.querySelector('#msBase').value=x[2]};fill();s3.querySelector('#msType').onchange=fill;
  s3.querySelector('#msGo').onclick=async()=>{const m=s3.querySelector('#msMsg');const id=s3.querySelector('#msType').value;m.textContent='Testing...';const cur=await api('/api/settings');const np=Object.assign({},cur.providers||{});np[id]={enabled:true,key:s3.querySelector('#msKey').value,base:s3.querySelector('#msBase').value};
    await api('/api/settings',{providers:np});const r=await api('/api/providers/test',{provider:id});m.textContent=r.ok?('Connected. '+r.models.length+' model(s) found.'):'Nothing found. Is the program running with its server turned on?';await loadModels(true);if(r.ok)renderTraining()};
  b.appendChild(el('div','psec','Your models (pick one to train)'));
  const g=el('div','grid');b.appendChild(g);
  (ST.groups||[]).filter(x=>x.provider!=='claude-code'&&x.kind!=='claude').forEach(x=>x.models.forEach(m=>{const c=el('div','pcard');c.dataset.mine=m.id;c.appendChild(el('h4',null,'<span style="flex:1">'+esc(m.name)+'</span><span class="meta">'+esc(x.label)+'</span>'));
    c.appendChild(el('div','meta',x.provider==='ollama'?'Training works, and you can save the result as a new AI.':'Training works (it learns lessons and examples). Saving as a new AI needs the model to be in Ollama.'));
    const bt=el('button','btn sm pri','Train it');bt.onclick=()=>{TRS.pre=m.id;TC.sec='quick';TRS.view=null;renderTraining()};c.appendChild(bt);g.appendChild(c)}));
}
async function trRE(b){
  const rec=await api('/api/training/recommend');const ais=await api('/api/ais');const have=ais.find(a=>a.pack==='reverser');const allT=await api('/api/training/tasks');
  const re=allT.filter(t=>t.builtin&&t.lang==='reverse');await loadModels();
  b.appendChild(el('div','hero','<h2>&#128269; Reverse engineering school</h2><p>A tab only for this skill: understanding things nobody documented for you. File formats, network protocols, assembly listings, bytecode, obfuscated code and black-box programs. Your AI learns the method the way an analyst works: look at real samples, form a hypothesis, test it on every sample, then write a parser or re-implementation and prove it with tests.</p><p class="meta">Educational and defensive use only: your own files, interoperability, data recovery, CTF and sandboxed triage. It never teaches bypassing licences or writing malware.</p>'));
  b.appendChild(el('div','pcard','<h4>The method</h4><ol><li><b>Observe</b>: magic bytes, lengths, strings, what changes when one input changes.</li><li><b>Hypothesise</b>: write the guess down, then test it on <i>every</i> sample.</li><li><b>Peel layers</b>: hex, base64, zlib, XOR, one at a time.</li><li><b>Read by role</b>: find the loop, the exit condition, the shifts and masks in assembly.</li><li><b>Re-implement and compare</b>: a clean version must match the original on many inputs.</li></ol>'));
  b.appendChild(el('div','psec',re.length+' practice tasks with real tests'));
  const g=el('div','grid');re.forEach(t=>{const c=el('div','pcard');c.dataset.re=t.id;c.appendChild(el('h4',null,esc(t.title)));c.appendChild(el('p',null,esc((t.prompt||'').slice(0,220))+((t.prompt||'').length>220?'...':'')));c.appendChild(el('div','meta',t.available?'Ready':'Needs: '+esc(t.why||'a tool that is missing')));g.appendChild(c)});b.appendChild(g);
  const f=el('div','pform');f.innerHTML='<h4>Train an AI on reverse engineering</h4><div class="trgrid"><div><label>Your AI (the student)</label><select id="reStu"></select></div><div><label>Teacher</label><select id="reTea"></select></div></div><div class="prow"><button class="btn pri big" id="reGo">Start reverse-engineering training</button><span class="err" id="reErr"></span></div><div class="meta">2 rounds. The teacher reviews every failed task, explains the method and shows a worked solution. Results appear in Results.</div>';b.appendChild(f);
  const s=await api('/api/settings');const cloud=(ST.groups||[]).filter(x=>x.provider!=='ollama'&&!LOCALP.includes(x.provider));
  modelOptions(f.querySelector('#reStu'),p=>p!=='claude-code',ST.model&&!ST.model.startsWith('claude-code::')?ST.model:'');
  modelOptions(f.querySelector('#reTea'),p=>p!=='ollama'&&!LOCALP.includes(p),(s.teacher_model||(cloud[0]&&cloud[0].models[0]&&cloud[0].models[0].id)||''),'(no teacher: just measure)');
  f.querySelector('#reGo').onclick=async()=>{const tid=f.querySelector('#reTea').value;if(tid)await api('/api/settings',{teacher_model:tid});
    const r=await api('/api/training/start',{name:'Reverse engineering',student:f.querySelector('#reStu').value,teacher:tid,demos:tid?'teacher':'reference',rounds:tid?2:1,max_steps:25,learn:!!tid,keep_successes:true,persona:true,consolidate:!!tid,tasks:re.filter(t=>t.available).map(t=>t.id)});
    if(r.error){f.querySelector('#reErr').textContent=r.error;return}TC.sec='quick';TRS.view=r.id;renderTraining()};
  const k=el('div','pform');k.innerHTML='<h4>&#129302; Marchand Reverser</h4><p>A ready-made local AI that only does reverse engineering: the method above, the reverse-engineering lessons and verified worked examples (file formats, assembly, deobfuscation, protocols, bytecode).</p><label>Base model (recommended for your PC: <b>'+esc(rec.base)+'</b>)</label><select id="rvBase"></select><label>Name</label><input id="rvName" value="marchand-reverser"><div class="prow"><button class="btn pri" id="rvGo">'+(have?'Rebuild Marchand Reverser':'Install Marchand Reverser')+'</button></div><div class="bar"><i id="rvBar"></i></div><div class="meta" id="rvMsg"></div>';b.appendChild(k);
  ['qwen2.5-coder:32b','qwen3-coder:30b','qwen2.5-coder:14b','qwen2.5-coder:7b','qwen2.5-coder:3b','qwen2.5-coder:1.5b'].forEach(x=>{const o=el('option',null,esc(x)+(x===rec.base?' (recommended)':''));o.value=x;k.querySelector('#rvBase').appendChild(o)});k.querySelector('#rvBase').value=rec.base;if(have)k.querySelector('#rvName').value=have.name;
  k.querySelector('#rvGo').onclick=async()=>{const bt=k.querySelector('#rvGo');bt.disabled=true;const msg=k.querySelector('#rvMsg'),bar=k.querySelector('#rvBar');let err=null,name=null;
    await sseJson('/api/training/coder',{kind:'reverser',base:k.querySelector('#rvBase').value,name:k.querySelector('#rvName').value},ev=>{if(ev.error){err=ev.error;msg.textContent='Error: '+ev.error}else{if(ev.status)msg.textContent=ev.status;if(ev.pct!=null)bar.style.width=ev.pct+'%';if(ev.name)name=ev.name}});
    bt.disabled=false;if(!err&&name){bar.style.width='100%';msg.innerHTML='Ready: <b>'+esc(name)+'</b> is in the model picker.';await loadModels();ST.model=name;LS.set('model',name);$('#model').value=name}};
  b.appendChild(el('div','psec','What the reverse-engineering lessons say'));
  const les=(await api('/api/teach/lessons')).filter(l=>(l.tags||[])[0]==='reverse');const ul=el('ul');les.forEach(l=>ul.appendChild(el('li',null,esc(l.text))));b.appendChild(ul);
}
