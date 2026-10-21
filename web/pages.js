const PROVS=[
 ['anthropic','Claude (Anthropic)','sk-ant-...','https://console.anthropic.com/settings/keys','Best for teaching: strongest coding reviewer.'],
 ['xai','Grok (xAI)','xai-...','https://console.x.ai','Fast and strong at code. Uses the OpenAI-style API.'],
 ['openai','OpenAI','sk-...','https://platform.openai.com/api-keys','GPT-5 and Codex models (for example gpt-5-codex). Add a key and they appear in the model picker under the chat.'],
 ['gemini','Gemini (Google)','AIza...','https://aistudio.google.com/apikey',''],
 ['openrouter','OpenRouter','sk-or-...','https://openrouter.ai/keys','One key, hundreds of models.'],
 ['deepseek','DeepSeek','sk-...','https://platform.deepseek.com/api_keys',''],
 ['groq','Groq','gsk_...','https://console.groq.com/keys','Very fast hosted open models.'],
 ['mistral','Mistral','','https://console.mistral.ai/api-keys',''],
 ['together','Together AI','','https://api.together.ai/settings/api-keys','Many open models and FLUX images.'],
 ['fireworks','Fireworks AI','fw_...','https://fireworks.ai/account/api-keys',''],
 ['cerebras','Cerebras','csk-...','https://cloud.cerebras.ai','Extremely fast Llama.'],
 ['nvidia','NVIDIA NIM','nvapi-...','https://build.nvidia.com','Free credits for many open models.'],
 ['huggingface','Hugging Face','hf_...','https://huggingface.co/settings/tokens','Router to many hosted models.'],
 ['perplexity','Perplexity','pplx-...','https://www.perplexity.ai/settings/api','Search-grounded answers.'],
 ['cohere','Cohere','','https://dashboard.cohere.com/api-keys',''],
 ['github','GitHub Models','github_pat_...','https://github.com/settings/tokens','Free tier with a GitHub token.'],
 ['custom','Custom server','','','Any other OpenAI-compatible server. Example address: http://127.0.0.1:1234/v1']];
const LOCALS=[['lmstudio','LM Studio','http://127.0.0.1:1234/v1','In LM Studio open the Developer tab and start the Local Server.'],['jan','Jan','http://127.0.0.1:1337/v1','In Jan enable the Local API Server.'],['koboldcpp','KoboldCpp','http://127.0.0.1:5001/v1','Starts automatically with KoboldCpp.'],['textgen','text-generation-webui','http://127.0.0.1:5000/v1','Launch it with the --api option.'],['llamacpp','llama.cpp server','http://127.0.0.1:8080/v1','Run llama-server -m model.gguf'],['vllm','vLLM','http://127.0.0.1:8000/v1','Run vllm serve MODEL'],['gpt4all','GPT4All','http://127.0.0.1:4891/v1','Enable the API Server in GPT4All settings.'],['localai','LocalAI','http://127.0.0.1:8081/v1','Run LocalAI with its API enabled.']];
PAGES.models=renderModels;PAGES.teach=renderTeach;
let MD={sec:'library',filter:'all',q:''};
const SEC=(b,secs,cur,set)=>{const nav=el('div','pnav');secs.forEach(([k,l])=>{const d=el('div',cur===k?'on':'',l);d.onclick=()=>set(k);nav.appendChild(d)});return nav};
function sseJson(path,body,on){return fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})}).then(async r=>{const rd=r.body.getReader();const dec=new TextDecoder();let buf='';while(true){const {done,value}=await rd.read();if(done)break;buf+=dec.decode(value,{stream:true});let i;while((i=buf.indexOf('\n\n'))>=0){const l=buf.slice(0,i);buf=buf.slice(i+2);if(l.startsWith('data: '))on(JSON.parse(l.slice(6)))}}})}
function pullModel(name,bar,msg){return sseJson('/api/pull',{model:name},ev=>{if(ev.error){msg.textContent='Error: '+ev.error;return}msg.textContent=ev.status||'';if(ev.total)bar.style.width=Math.round(100*(ev.completed||0)/ev.total)+'%'}).then(async()=>{bar.style.width='100%';await loadModels()})}
function modal(title,html){$('#iTitle').textContent=title;$('#iBody').innerHTML=html;openModal('#mInfo')}

async function renderModels(){
  const root=$('#plug');root.innerHTML='';
  root.appendChild(SEC(root,[['library','Download models'],['installed','Installed'],['cloud','Cloud and local servers'],['apps','Apps on this PC'],['ollama','Ollama']],MD.sec,k=>{MD.sec=k;renderModels()}));
  const body=el('div','pbody');root.appendChild(body);
  await ({library:mLibrary,installed:mInstalled,cloud:mCloud,apps:mApps,ollama:mOllama})[MD.sec](body);
}
async function mLibrary(b){
  const cat=await api('/api/ollama/catalog');const hw=cat.hardware;
  b.appendChild(el('div','note','Your PC: '+(hw.ram_gb?hw.ram_gb+' GB RAM':'RAM unknown')+(hw.gpu?' - '+esc(hw.gpu)+' ('+hw.vram_gb+' GB video memory)':' - no supported graphics card detected (models run on the CPU, slower)')+'. Sizes are approximate downloads.'));
  if(hw.backend)b.appendChild(el('div','note','<b>Graphics:</b> '+esc(hw.backend)));
  const br=el('div','prow');br.appendChild(linkEl(cat.library||'https://ollama.com/search','Browse every model on ollama.com'));br.appendChild(linkEl(cat.gguf||'https://huggingface.co/models?library=gguf','Hugging Face GGUF models'));br.appendChild(linkEl('https://docs.ollama.com/gpu','Which GPUs Ollama supports'));b.appendChild(br);
  const bar=el('div','prow');['all','coding','general','vision','small','strata'].forEach(f=>{const p=el('span','pill',f==='strata'?'strata (big models)':f);p.dataset.filter=f;if(MD.filter===f){p.style.background='var(--accent)';p.style.color='#fff'};p.onclick=()=>{MD.filter=f;renderModels()};bar.appendChild(p)});
  const s=el('input');s.placeholder='Search...';s.value=MD.q;s.oninput=()=>{MD.q=s.value;draw()};s.style.maxWidth='220px';bar.appendChild(s);b.appendChild(bar);
  if(MD.filter==='strata'||MD.filter==='all'){const si=el('div','pcard');si.dataset.strataInfo='1';
    si.appendChild(el('h4',null,'Strata: very large models on a gaming PC'));
    si.appendChild(el('p',null,'Strata is a free program (MIT license, by Niko1221) that runs a 125-billion-parameter model on a normal PC and serves it to Marchand. '+(cat.strata&&cat.strata.installed?'<b style="color:var(--ok)">Strata is installed.</b> Press Download on a Strata model below: Strata downloads it, starts it and Marchand connects to it automatically (it appears in the model picker under Local).':'The Strata models below need the Strata program first. Install it, then press Download here.')));
    const sr=el('div','prow');if(!(cat.strata&&cat.strata.installed)){const gs=linkEl((cat.strata&&cat.strata.releases)||'https://github.com/Niko1221/Strata/releases/latest','Get Strata');gs.className='btn sm pri';gs.dataset.link='strata';sr.appendChild(gs)}
    sr.appendChild(linkEl((cat.strata&&cat.strata.home)||'https://github.com/Niko1221/Strata','Strata on GitHub'));si.appendChild(sr);b.appendChild(si)}
  const g=el('div','grid');b.appendChild(g);
  const have=new Set(((ST.groups||[]).find(x=>x.provider==='ollama')||{models:[]}).models.map(m=>m.id));
  function strataCard(m){const c=el('div','pcard');c.dataset.strataModel=m.id;const fitc={great:'var(--ok)',ok:'var(--accentText)','too big':'var(--bad)',unknown:'var(--dim)'}[m.fit];
    c.appendChild(el('h4',null,'<span style="flex:1">'+esc(m.name)+'</span><span class="meta" style="color:'+fitc+'">'+({great:'fits this PC',ok:'tight',"too big":'needs more memory',unknown:''}[m.fit])+'</span>'));
    c.appendChild(el('p',null,esc(m.desc)));c.appendChild(el('div','meta','needs ~'+m.mem_gb+' GB of RAM + video memory - download '+esc(m.dl)+' - runs on Strata'));
    const bar=el('div','bar','<i></i>');const msg=el('div','meta','');const inst=cat.strata&&cat.strata.installed;const serving=(ST.groups||[]).some(x=>x.provider==='strata');
    const bt=el('button','btn sm pri',inst?'Download with Strata':'Get Strata first');
    bt.onclick=async()=>{if(!inst){openLink((cat.strata&&cat.strata.releases)||'https://github.com/Niko1221/Strata/releases/latest');return}
      if(!confirm(m.name+' is a very large download ('+m.dl+') and needs about '+m.mem_gb+' GB of memory. Start now?'))return;
      bt.disabled=true;bt.textContent='Working...';let err=null,fin=false;bar.firstChild.style.width='4%';
      await sseJson('/api/strata/install',{model:m.id},ev=>{if(ev.error){err=ev.error;msg.textContent='Error: '+ev.error}else{if(ev.status)msg.textContent=ev.status;if(ev.done)fin=true}});
      if(fin){bar.firstChild.style.width='100%';bt.textContent='Serving';await loadModels(true)}else{bt.disabled=false;bt.textContent='Download with Strata'}};
    c.appendChild(bt);const pl=linkEl(m.url,'Strata page');pl.className='btn sm';pl.style.marginLeft='6px';c.appendChild(pl);c.appendChild(bar);c.appendChild(msg);return c}
  function draw(){g.innerHTML='';cat.models.filter(m=>(MD.filter==='all'||m.tags.includes(MD.filter))&&(!MD.q||m.name.toLowerCase().includes(MD.q.toLowerCase()))).forEach(m=>{
    if(m.engine==='strata'){g.appendChild(strataCard(m));return}
    const c=el('div','pcard');const fitc={great:'var(--ok)',ok:'var(--accentText)','too big':'var(--bad)',unknown:'var(--dim)'}[m.fit];
    c.appendChild(el('h4',null,'<span style="flex:1">'+esc(m.name)+'</span><span class="meta" style="color:'+fitc+'">'+({great:'runs great',ok:'runs (slower)','too big':'too big for this PC',unknown:''}[m.fit])+'</span>'));
    c.appendChild(el('p',null,esc(m.desc)));c.appendChild(el('div','meta','~'+m.gb+' GB - '+m.tags.join(', ')+(m.tools?' - can edit files':' - chat only')));
    const bar=el('div','bar','<i></i>');const msg=el('div','meta','');const bt=el('button','btn sm '+(have.has(m.name)?'':'pri'),have.has(m.name)?'Installed':'Download');bt.disabled=have.has(m.name);
    bt.onclick=async()=>{bt.disabled=true;bt.textContent='Downloading...';await pullModel(m.name,bar.firstChild,msg);bt.textContent='Installed'};
    c.appendChild(bt);const pl=linkEl(m.url,'ollama.com page');pl.className='btn sm';pl.style.marginLeft='6px';c.appendChild(pl);c.appendChild(bar);c.appendChild(msg);g.appendChild(c)})}
  draw();
  b.appendChild(el('div','psec','Any other model'));
  const f=el('div','pform','<label>Model name from ollama.com/library, or a Hugging Face model: hf.co/user/repo:Q4_K_M</label><div class="prow"><input id="mCustom" placeholder="llama3.3:70b"><button class="btn pri" id="mGo">Download</button></div><div class="bar"><i id="mBar"></i></div><div class="note" id="mMsg"></div>');b.appendChild(f);
  f.querySelector('#mGo').onclick=()=>{const n=f.querySelector('#mCustom').value.trim();if(n)pullModel(n,f.querySelector('#mBar'),f.querySelector('#mMsg')).then(()=>f.querySelector('#mMsg').textContent='Done: '+n)}
}
async function mInstalled(b){
  await loadModels();const g0=(ST.groups||[]).find(x=>x.provider==='ollama');const ms=g0?g0.models:[];
  if(!ms.length){b.appendChild(el('div','note','No local models yet. Open "Download models".'));return}
  const g=el('div','grid');ms.slice().sort((x,y)=>(y.mine?1:0)-(x.mine?1:0)).forEach(m=>{const c=el('div','pcard');c.appendChild(el('h4',null,'<span style="flex:1">'+esc(m.name)+'</span>'+(m.mine?'<span class="meta" style="color:var(--accentText)">My own AI</span>':'')));c.appendChild(el('div','meta',(m.size/1e9).toFixed(1)+' GB on disk'));
    const a=el('div','acts');const use=el('button','btn sm pri','Use');use.onclick=()=>{ST.model=m.id;$('#model').value=m.id;LS.set('model',m.id);showView('chat')};
    const info=el('button','btn sm','Info');info.onclick=async()=>{const r=await api('/api/model/show?name='+encodeURIComponent(m.id));const d=r.details||{};modal(m.name,'<div class="note">Family: '+esc(d.family||'?')+' - Parameters: '+esc(d.parameter_size||'?')+' - Quantization: '+esc(d.quantization_level||'?')+'</div><div class="note">Capabilities: '+esc((r.capabilities||['unknown']).join(', '))+'</div><div class="viewer">'+esc((r.parameters||'')+'\n\n'+(r.template||'').slice(0,1500))+'</div>')};
    const del=el('button','btn sm','Delete');del.onclick=async()=>{if(confirm('Delete '+m.name+' from this computer?')){await api('/api/model/delete',{name:m.id});renderModels();loadModels()}};
    a.appendChild(use);a.appendChild(info);a.appendChild(del);c.appendChild(a);g.appendChild(c)});b.appendChild(g)}
async function mCloud(b){
  const s=await api('/api/settings');const prov=s.providers||{};
  b.appendChild(el('div','note','Add a key to use that company\'s models in Marchand: as your coding model, as a teacher for your local model, or just to chat. Keys stay on this computer in ~/.marchand/settings.json and are only sent to that company. Cloud usage is billed by them.'));
  const g=el('div','grid');PROVS.forEach(([id,label,ph,url,desc])=>{const c=el('div','pcard');const cur=prov[id]||{};
    c.appendChild(el('h4',null,'<span style="flex:1">'+esc(label)+'</span>'+(cur.key?'<span class="meta" style="color:var(--ok)">key saved</span>':'')));if(desc)c.appendChild(el('p',null,esc(desc)));
    const k=el('input');k.type='password';k.placeholder=id==='custom'?'API key (optional)':ph||'API key';k.value=cur.key||'';c.appendChild(k);
    let base;if(id==='custom'){base=el('input');base.placeholder='http://127.0.0.1:1234/v1';base.value=cur.base||'';c.appendChild(base)}
    const out=el('div','meta','');const a=el('div','acts');const sv=el('button','btn sm pri','Save and test');
    sv.onclick=async()=>{out.textContent='Testing...';const np=Object.assign({},prov);np[id]={key:k.value,base:base?base.value:undefined};await api('/api/settings',{providers:np});const r=await api('/api/providers/test',{provider:id});out.textContent=r.ok?('Connected. '+r.models.length+' models found.'):'No models found. Check the key'+(id==='custom'?' and address':'')+'.';loadModels()};
    a.appendChild(sv);if(url){const l=el('a',null,'Get a key');l.href=url;l.target='_blank';l.style.fontSize='13px';a.appendChild(l)}
    if(cur.key){const rm=el('button','btn sm','Remove');rm.onclick=async()=>{const np=Object.assign({},prov);delete np[id];await api('/api/settings',{providers:np});renderModels();loadModels()};a.appendChild(rm)}
    c.appendChild(a);c.appendChild(out);g.appendChild(c)});b.appendChild(g);
  b.appendChild(el('div','psec','Local servers on this PC'));b.appendChild(el('div','note','Other programs that run models on your PC and offer an OpenAI-style address. Turn one on and its models appear in the picker. "Apps on this PC" can find them for you.'));
  const lg=el('div','grid');LOCALS.forEach(([id,label,base,tip])=>{const cur=prov[id]||{};const c=el('div','pcard');const t=el('h4',null,'<span style="flex:1">'+esc(label)+'</span>');t.appendChild(sw(!!cur.enabled,async()=>{const np=Object.assign({},prov);np[id]={enabled:!cur.enabled,base:cur.base||base,key:cur.key||''};await api('/api/settings',{providers:np});renderModels();loadModels(true)}));c.appendChild(t);c.appendChild(el('p',null,esc(tip)));
    const bi=el('input');bi.value=cur.base||base;c.appendChild(bi);const out=el('div','meta','');const a=el('div','acts');const tb=el('button','btn sm','Save and test');tb.onclick=async()=>{out.textContent='Testing...';const np=Object.assign({},prov);np[id]={enabled:true,base:bi.value,key:cur.key||''};await api('/api/settings',{providers:np});const r=await api('/api/providers/test',{provider:id});out.textContent=r.ok?('Connected. '+r.models.length+' models.'):'Not reachable. Is '+label+' running with its server on?';loadModels(true)};a.appendChild(tb);c.appendChild(a);c.appendChild(out);lg.appendChild(c)});b.appendChild(lg)}
async function mApps(b){
  b.appendChild(el('div','note','Scans this PC for AI programs that are running right now: other model runners (LM Studio, KoboldCpp, llama.cpp, vLLM, Jan...), and image generators (Forge, Automatic1111, SD.Next, ComfyUI, InvokeAI, Fooocus). Only addresses on your own computer are checked.'));
  const sc=el('button','btn pri','Scan now');b.appendChild(sc);const out=el('div');b.appendChild(out);
  async function run(){out.innerHTML='<div class="note">Scanning...</div>';const r=await api('/api/software/scan');out.innerHTML='';
    if(!r.found.length)out.appendChild(el('div','psec','Nothing found. Start the program first, then scan again.'));
    const g=el('div','grid');r.found.forEach(a=>{const c=el('div','pcard');c.appendChild(el('h4',null,'<span style="flex:1">'+esc(a.name)+'</span><span class="meta" style="color:'+(a.api?'var(--ok)':'var(--bad)')+'">'+(a.api?'running':'API off')+'</span>'));
      c.appendChild(el('div','meta',esc(a.url)+(a.detail?' - '+esc(a.detail):'')));if(a.hint)c.appendChild(el('p',null,esc(a.hint)));
      if(a.app==='ollama')c.appendChild(el('p',null,'This is the engine Marchand already uses.'));
      else if(a.kind==='llm-openai'||(a.image&&a.api)){const m=el('div','meta','');const bt=el('button','btn sm pri',a.image?'Use for images':'Add to Marchand');bt.onclick=async()=>{const x=await api('/api/software/apply',{app:a.app});m.textContent=x.message;loadModels(true)};c.appendChild(bt);c.appendChild(m)}
      else if(a.kind==='image-other')c.appendChild(el('p',null,'Detected. Marchand cannot drive this one directly yet; use Forge or ComfyUI for pictures.'));
      g.appendChild(c)});out.appendChild(g)}
  sc.onclick=run;run();
  agentSearch(b,null,false);
  await appLinksBox(b,null,'Missing a program? Download it here');
  b.appendChild(el('div','psec','Supported programs and how to turn their API on'));
  b.appendChild(el('div','htable-wrap',`<table class="htable"><tr><th>Program</th><th>Use</th><th>How to enable</th></tr>
<tr><td>Forge, Automatic1111, SD.Next</td><td>Pictures</td><td>Add <code>--api</code> to COMMANDLINE_ARGS in webui-user.bat, then start it (address http://127.0.0.1:7860).</td></tr>
<tr><td>ComfyUI</td><td>Pictures</td><td>Just start it (address http://127.0.0.1:8188). Put a checkpoint in models/checkpoints.</td></tr>
<tr><td>LM Studio</td><td>Chat models</td><td>Developer tab &gt; Start server (port 1234).</td></tr>
<tr><td>Jan</td><td>Chat models</td><td>Settings &gt; Local API Server &gt; Start (port 1337).</td></tr>
<tr><td>KoboldCpp, llama.cpp, vLLM, text-generation-webui (--api), GPT4All, LocalAI</td><td>Chat models</td><td>Start their server mode; Marchand finds it on its usual port.</td></tr>
<tr><td>OpenAI, Grok (xAI), Together</td><td>Chat and pictures</td><td>Add a key in Cloud and local servers.</td></tr></table>`))}
async function mOllama(b){
  b.appendChild(el('div','note','Checking...'));const r=await api('/api/ollama/check');b.innerHTML='';
  const c=el('div','pcard');c.appendChild(el('h4',null,'Ollama'));
  c.appendChild(el('div','prow','<span>Installed version: <b>'+esc(r.current||'not running')+'</b></span><span>Latest version: <b>'+esc(r.latest||'unknown (offline?)')+'</b></span>'));
  if(r.error)c.appendChild(el('div','err',esc(r.error)));
  if(!r.installed&&!r.current){const dl=linkEl('https://ollama.com/download','Download Ollama from ollama.com');dl.className='btn pri';c.appendChild(dl)}
  c.appendChild(el('div','note',r.update?'A newer Ollama is available. Newer versions support newer models and tool calling.':(r.current&&r.latest?'You are on the latest version.':'')));
  const bar=el('div','bar','<i></i>');const msg=el('div','note','');const a=el('div','acts');
  const up=el('button','btn '+(r.update?'pri':''),r.installed||r.current?'Update Ollama':'Install Ollama');
  up.onclick=async()=>{if(!confirm('Download and install the latest Ollama now? Models in use will stop for a moment.'))return;up.disabled=true;await sseJson('/api/ollama/update',{},ev=>{if(ev.error)msg.textContent='Error: '+ev.error;else{msg.textContent=ev.status||msg.textContent;if(ev.pct!=null)bar.firstChild.style.width=ev.pct+'%'}});up.disabled=false};
  const st=el('button','btn','Start Ollama');st.onclick=async()=>{const x=await api('/api/ollama/start',{});msg.textContent=x.error||'Starting... press Refresh in a few seconds.'};
  const rf=el('button','btn','Refresh');rf.onclick=()=>renderModels();a.appendChild(up);a.appendChild(st);a.appendChild(rf);c.appendChild(a);c.appendChild(bar);c.appendChild(msg);b.appendChild(c);
  const auto=el('div','prow','<input type="checkbox" id="chkUp" style="width:auto"><label for="chkUp">Check for Ollama updates when Marchand starts</label>');b.appendChild(auto);
  const s=await api('/api/settings');auto.querySelector('input').checked=s.check_updates!==false;auto.querySelector('input').onchange=e=>api('/api/settings',{check_updates:e.target.checked});
  b.appendChild(el('div','note','Ollama address: '+esc(s.host)+' (change it in Settings if Ollama runs on another computer).'))}
async function checkUpdateBanner(){
  const s=await api('/api/settings');if(s.check_updates===false)return;const r=await api('/api/ollama/check');if(!r.update)return;
  const d=$('#stat');d.innerHTML='Ollama '+esc(r.current)+' <a href="#" id="updLink" style="color:var(--accentText)">update to '+esc(r.latest)+'</a>';$('#updLink').onclick=e=>{e.preventDefault();MD.sec='ollama';showView('models')}}

// ---------- Teach ----------
let TC={sec:'setup'};
async function renderTeach(){
  const root=$('#plug');root.innerHTML='';
  root.appendChild(SEC(root,[['setup','Teacher'],['lessons','Lessons'],['examples','Examples and dataset'],['build','Create your AI']],TC.sec,k=>{TC.sec=k;renderTeach()}));
  const b=el('div','pbody');root.appendChild(b);await ({setup:tSetup,lessons:tLessons,examples:tExamples,build:tBuild})[TC.sec](b)}
function cloudOptions(sel,cur){sel.innerHTML='<option value="">(none)</option>';(ST.groups||[]).filter(g=>g.provider!=='ollama').forEach(g=>{const og=el('optgroup');og.label=g.label;g.models.forEach(m=>{const o=el('option',null,esc(m.name));o.value=m.id;og.appendChild(o)});sel.appendChild(og)});sel.value=cur||''}
async function tSetup(b){
  const s=await api('/api/settings');await loadModels();
  b.appendChild(el('div','note','Teaching works in four ways, all without needing a powerful PC:'));
  b.appendChild(el('div','pcard',`<p><b>1. Lessons.</b> After your local model finishes a task, press <b>Teach</b> under its answer. The teacher (Claude or Grok) reads the work, grades it, and writes short rules. They are added to every future prompt.</p>
  <p><b>2. Ask the teacher.</b> When a teacher is set, your local model gets an <code>ask_teacher</code> tool for when it is stuck. You approve each question.</p>
  <p><b>3. Examples.</b> Run a task with a Claude or Grok model as the coder, press the thumbs up, and Marchand stores the full transcript as a training example. Export them as a dataset to fine-tune your local model (needs an NVIDIA GPU), or let the review pass use the teacher.</p>
  <p><b>4. Create your AI.</b> Build a new Ollama model with your lessons, role and best examples built in, so it behaves better everywhere.</p>`));
  b.appendChild(el('div','psec','Teacher model'));
  const f=el('div','pform','<label>Which cloud model teaches?</label><select id="tM"></select><div class="prow" style="margin-top:12px"><input type="checkbox" id="tCrit" style="width:auto"><label for="tCrit">Also use the teacher for the automatic review pass before a task finishes</label></div><div class="prow"><button class="btn pri" id="tSave">Save</button><span class="note" id="tMsg"></span></div>');b.appendChild(f);
  cloudOptions(f.querySelector('#tM'),s.teacher_model);f.querySelector('#tCrit').checked=!!s.critic_with_teacher;
  if(!(ST.groups||[]).some(g=>g.provider!=='ollama'))b.insertBefore(el('div','err','No cloud model yet. Add a Claude or Grok key in Models > Cloud and local servers.'),f);
  f.querySelector('#tSave').onclick=async()=>{await api('/api/settings',{teacher_model:f.querySelector('#tM').value,critic_with_teacher:f.querySelector('#tCrit').checked});f.querySelector('#tMsg').textContent='Saved.'}}
async function tLessons(b){
  const ls=await api('/api/teach/lessons');
  b.appendChild(el('div','note','Rules your model follows in every code session. Turn off or edit any rule. Short, general rules work best.'));
  const add=el('div','prow','<input id="lNew" placeholder="Add your own rule, e.g. Always run the linter before finishing." style="flex:1"><button class="btn pri" id="lAdd">Add</button>');b.appendChild(add);
  add.querySelector('#lAdd').onclick=async()=>{const v=add.querySelector('#lNew').value.trim();if(v){await api('/api/teach/lesson',{add:v});renderTeach()}};
  const cta=el('button','btn pri','Create an AI with these lessons');cta.style.margin='6px 0';cta.onclick=()=>{TC.sec='build';renderTeach()};b.appendChild(cta);
  if(!ls.length)b.appendChild(el('div','psec','No lessons yet.'));
  ls.forEach(l=>{const r=el('div','pcard');r.style.marginBottom='8px';const t=el('div','prow','<span style="flex:1">'+esc(l.text)+'</span><span class="meta">'+esc((l.tags||[]).join(', '))+' - '+esc(l.source||'')+'</span>');
    t.appendChild(sw(l.enabled!==false,async()=>{await api('/api/teach/lesson',{id:l.id,enabled:l.enabled===false});renderTeach()}));
    const d=el('button','btn sm','Delete');d.onclick=async()=>{await api('/api/teach/lesson',{id:l.id,delete:true});renderTeach()};t.appendChild(d);r.appendChild(t);b.appendChild(r)})}
async function tExamples(b){
  const ex=await api('/api/teach/examples');
  b.appendChild(el('div','note','Press the thumbs up under a finished answer to save it here. Thumbs down saves a bad example (not exported).'));
  if(!ex.length)b.appendChild(el('div','psec','No examples yet.'));
  const g=el('div','grid');ex.forEach(e=>{const c=el('div','pcard');c.appendChild(el('h4',null,'<span style="flex:1">'+esc(e.title||'Untitled')+'</span><span>'+(e.rating>=4?'&#128077;':'&#128078;')+'</span>'));c.appendChild(el('div','meta',esc(e.model)+' - '+e.steps+' messages'));
    const d=el('button','btn sm','Delete');d.onclick=async()=>{await api('/api/teach/delete-example',{id:e.id});renderTeach()};c.appendChild(d);g.appendChild(c)});b.appendChild(g);
  b.appendChild(el('div','psec','Export for fine-tuning'));
  const f=el('div','pform','<div class="prow"><label>Minimum rating</label><select id="xMin" style="width:80px"><option>4</option><option>5</option><option>1</option></select><input type="checkbox" id="xCloud" style="width:auto"><label for="xCloud">Only examples made by Claude / Grok</label></div><div class="prow"><button class="btn pri" id="xGo">Export dataset</button></div><div class="note">Creates marchand_dataset.jsonl (chat format with tool calls) and train_lora_unsloth.py, a ready-to-edit LoRA training script. Fine-tuning needs an NVIDIA GPU and the unsloth package; the script is a template and has not been run on your hardware. Without a GPU, use "Lessons" and "Bake into a model" instead.</div>');b.appendChild(f);
  f.querySelector('#xGo').onclick=async()=>{const r=await api('/api/teach/export?min='+f.querySelector('#xMin').value+'&cloud='+(f.querySelector('#xCloud').checked?1:0));
    if(!r.count){alert('No examples match yet.');return}
    const dl=(name,text)=>{const a=el('a');a.href=URL.createObjectURL(new Blob([text],{type:'text/plain'}));a.download=name;a.click()};dl('marchand_dataset.jsonl',r.jsonl);setTimeout(()=>dl('train_lora_unsloth.py',r.train_script),400)}}
async function buildAi(body,bar,msg){
  msg.textContent='Creating...';bar.style.width='20%';let name=null,err=null;
  await sseJson('/api/teach/build-model',body,ev=>{if(ev.error){err=ev.error;msg.textContent='Error: '+ev.error}else{msg.textContent=ev.status||msg.textContent;if(ev.total)bar.style.width=Math.round(100*(ev.completed||0)/ev.total)+'%';if(ev.name)name=ev.name}});
  if(!err)bar.style.width='100%';await loadModels();return err?null:name}
async function tBuild(b){
  await loadModels();const g0=(ST.groups||[]).find(x=>x.provider==='ollama');const ms=g0?g0.models:[];
  const ais=await api('/api/ais');const ls=await api('/api/teach/lessons');const ex=await api('/api/teach/examples');
  const nL=ls.filter(l=>l.enabled!==false).length,nE=ex.filter(e=>e.rating>=4).length;
  b.appendChild(el('div','note','Turn everything you taught into a new AI of your own. It is a normal Ollama model, so it also works in any other app that uses Ollama. You can rebuild it any time after teaching it more.'));
  if(ais.length){b.appendChild(el('div','psec','My AIs'));const g=el('div','grid');
    ais.forEach(p=>{const c=el('div','pcard');c.appendChild(el('h4',null,'<span>&#129302;</span><span style="flex:1">'+esc(p.name)+'</span>'));
      c.appendChild(el('p',null,esc(p.persona?p.persona.slice(0,120):'General coding assistant')));
      c.appendChild(el('div','meta','Based on '+esc(p.base)+' - '+(p.include_lessons?p.lessons+' lessons':'no lessons')+' - '+p.examples+' examples - created '+new Date(p.created*1000).toLocaleDateString()));
      const bar=el('div','bar','<i></i>');const msg=el('div','meta','');const a=el('div','acts');
      const use=el('button','btn sm pri','Use');use.onclick=()=>{ST.model=p.name;$('#model').value=p.name;LS.set('model',p.name);showView('chat')};
      const rb=el('button','btn sm','Rebuild with latest lessons');rb.onclick=async()=>{rb.disabled=true;await buildAi({base:p.base,name:p.name,persona:p.persona,include_lessons:p.include_lessons,examples:p.examples,temperature:p.temperature,num_ctx:p.num_ctx},bar.firstChild,msg);renderTeach()};
      const del=el('button','btn sm','Delete');del.onclick=async()=>{if(confirm('Delete the AI '+p.name+' from this computer? Lessons and examples are kept.')){await api('/api/ais/delete',{name:p.name,remove_model:true});renderTeach();loadModels()}};
      a.append(use,rb,del);c.append(a,bar,msg);g.appendChild(c)});b.appendChild(g)}
  b.appendChild(el('div','psec','Create a new AI'));
  const f=el('div','pform','<label>1. Name (letters, numbers and dashes)</label><input id="bName" value="marchand-coder"><label>2. Start from which model?</label><select id="bBase"></select><div class="note">Pick the best coder you have. Your AI inherits its intelligence; teaching adds habits and knowledge.</div><label>3. What is this AI for? (optional, one or two sentences)</label><textarea id="bPersona" rows="3" placeholder="e.g. You are my assistant for a C++ game server. Be careful, explain risks, and always run the build."></textarea><div class="prow" style="margin-top:12px"><input type="checkbox" id="bLes" checked style="width:auto"><label for="bLes">Build in my lessons ('+nL+' active)</label></div><div class="prow"><label>Include my best examples</label><select id="bEx" style="width:90px"></select><span class="meta">('+nE+' saved with a thumbs up)</span></div><div class="prow"><label>Style</label><input type="range" id="bTemp" min="0" max="10" value="2" style="width:200px"><span class="meta" id="bTempL">Precise</span></div><div class="prow"><label>Memory</label><select id="bCtx" style="width:200px"><option value="8192">Small (8K, fastest)</option><option value="16384" selected>Normal (16K)</option><option value="32768">Large (32K, needs more RAM)</option></select></div><div class="prow"><button class="btn pri" id="bGo">Create my AI</button><button class="btn" id="bUse" style="display:none">Use it now</button></div><div class="bar"><i id="bBar"></i></div><div class="note" id="bMsg"></div>');
  b.appendChild(f);
  if(!ms.length)b.insertBefore(el('div','err','No local model yet. Download one in Models first.'),f);
  ms.forEach(m=>{const o=el('option',null,esc(m.name));o.value=m.id;f.querySelector('#bBase').appendChild(o)});
  for(let i=0;i<=Math.min(5,Math.max(nE,0));i++){const o=el('option',null,String(i));o.value=i;f.querySelector('#bEx').appendChild(o)}
  const tl=['Precise','Precise','Precise','Balanced','Balanced','Balanced','Creative','Creative','Creative','Very creative','Very creative'];
  f.querySelector('#bTemp').oninput=e=>f.querySelector('#bTempL').textContent=tl[e.target.value];
  f.querySelector('#bGo').onclick=async()=>{const name=await buildAi({base:f.querySelector('#bBase').value,name:f.querySelector('#bName').value,persona:f.querySelector('#bPersona').value,include_lessons:f.querySelector('#bLes').checked,examples:+f.querySelector('#bEx').value,temperature:f.querySelector('#bTemp').value/10,num_ctx:+f.querySelector('#bCtx').value},f.querySelector('#bBar'),f.querySelector('#bMsg'));
    if(name){f.querySelector('#bMsg').textContent='Your AI "'+name+'" is ready. It is in the model picker (top right).';const u=f.querySelector('#bUse');u.style.display='';u.onclick=()=>{ST.model=name;$('#model').value=name;LS.set('model',name);showView('chat')}}}}

// ---------- chat extras ----------
const _addRetry=addRetry;
addRetry=function(msgEl){_addRetry(msgEl);const c=ST.convo;if(!msgEl||ST.mode!=='code'||!c.history.length)return;
  const row=el('span');row.style.marginLeft='8px';
  const up=el('button','btn sm','&#128077;');up.title='Save as a good training example';up.onclick=async()=>{await api('/api/teach/save-example',{convo:c,rating:5});up.textContent='Saved'};
  const dn=el('button','btn sm','&#128078;');dn.title='Save as a bad example';dn.style.marginLeft='4px';dn.onclick=async()=>{await api('/api/teach/save-example',{convo:c,rating:1});dn.textContent='Saved'};
  const te=el('button','btn sm','Teach');te.title='Ask the teacher model to grade this work and write lessons';te.style.marginLeft='4px';
  te.onclick=async()=>{te.disabled=true;te.textContent='Teacher is reading...';const r=await api('/api/teach/evaluate',{history:c.history,project:ST.project});te.disabled=false;te.textContent='Teach';
    if(r.error){modal('Teacher',esc(r.error));return}
    modal('Teacher feedback','<div class="note"><b>Score: '+esc(r.score)+'/10</b> - '+esc(r.verdict||'')+'</div>'+(r.mistakes||[]).map(x=>'<div>&#8226; '+esc(x)+'</div>').join('')+'<div class="psec">Better approach</div><div>'+esc(r.better_approach||'')+'</div><div class="psec">'+r.added+' new lesson(s) saved</div>'+(r.lessons||[]).map(x=>'<div>&#10003; '+esc(x.text||x)+'</div>').join(''))};
  row.append(up,dn,te);msgEl.appendChild(row)};

async function appLinksBox(parent,ids,title){
  const r=await api('/api/links');const box=el('div','pcard');box.dataset.links=ids?ids.join(','):'all';
  box.appendChild(el('h4',null,esc(title||'Get the programs')));
  const hw=r.hardware||{};
  if(hw.vendor==='amd')box.appendChild(el('div','note','AMD graphics card detected ('+esc(hw.gpu)+'). Links marked <b>AMD</b> point to builds made for Radeon cards.'));
  (r.links||[]).filter(l=>!ids||ids.includes(l.id)).forEach(l=>{
    const row=el('div','prow');const have=r.have&&r.have[l.id];
    row.appendChild(el('span',null,'<b>'+esc(l.name)+'</b> <span class="meta">'+esc(l.what)+(have?' &middot; <span style="color:var(--ok)">installed</span>':'')+'</span>'));
    row.lastChild.style.flex='1';const a=linkEl(l.url,(l.note?'AMD: ':'')+'Download');a.dataset.link=l.id;a.className='btn sm '+(have?'':'pri');row.appendChild(a);
    if(l.nvidia_url){const o=linkEl(l.nvidia_url,'NVIDIA / standard');o.className='btn sm';row.appendChild(o)}
    box.appendChild(row)});
  parent.appendChild(box);return box}

function agentSearch(parent,after,auto){
  const box=el('div','agentbox');box.dataset.agents='1';const bt=el('button','btn sm pri','Search this PC for AI agents');const out=el('div','agentout');box.append(bt,out);parent.appendChild(box);
  async function run(){bt.disabled=true;out.innerHTML='<div class="note">Searching (up to 10 seconds)...</div>';let r;try{r=await api('/api/agents/scan')}catch(e){out.innerHTML='<div class="err">Search failed.</div>';bt.disabled=false;return}
    out.innerHTML='';bt.disabled=false;bt.textContent='Search again';
    (r.agents||[]).forEach(a=>{const row=el('div','prow');row.dataset.agent=a.id;row.dataset.found=a.found?'1':'0';
      row.appendChild(el('span',null,'<b>'+esc(a.name)+'</b> <span class="meta">'+(a.found?'<span style="color:var(--ok)">found</span> '+esc(a.path)+(a.version?' ('+esc(a.version)+')':''):'not found')+'</span><br><span class="meta">'+esc(a.what)+'</span>'));row.firstChild.style.flex='1';
      if(a.found&&a.usable){const u=el('button','btn sm'+(a.active?'':' pri'),a.active?'In use':'Use this one');u.disabled=a.active;u.dataset.use=a.path;u.onclick=async()=>{u.disabled=true;const x=await api('/api/agents/use',{path:a.path});if(x.error){alert(x.error);return}await loadModels(true);u.textContent='In use';if(after)after(a)};row.appendChild(u)}
      else if(!a.found){const l=linkEl(a.url,'Install');l.className='btn sm';row.appendChild(l)}
      out.appendChild(row)});
    const cl=(r.agents||[]).find(a=>a.id==='claude');if(cl&&cl.found&&!cl.active&&auto){await api('/api/agents/use',{path:cl.path});await loadModels(true);if(after)after(cl)}}
  bt.onclick=run;if(auto)run();return box}
