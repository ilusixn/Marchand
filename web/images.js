PAGES.images=renderImages;
const SIZES=[['512x512','512 x 512 (SD 1.5)'],['768x768','768 x 768'],['1024x1024','1024 x 1024 (SDXL / FLUX)'],['1024x768','1024 x 768 landscape'],['768x1024','768 x 1024 portrait'],['1344x768','1344 x 768 wide'],['768x1344','768 x 1344 tall']];
const IM={st:null,backend:'auto',form:{prompt:'',negative:'',size:'1024x1024',steps:25,cfg:7,seed:-1,count:1,sampler:'',checkpoint:'',denoise:0.6},init:null,run:null,busy:false};
const _imgCache=new Map();
async function imgUrl(name){if(_imgCache.has(name))return _imgCache.get(name);const r=await fetch('/api/image?name='+encodeURIComponent(name));const u=URL.createObjectURL(await r.blob());_imgCache.set(name,u);return u}
function currentInfo(){const st=IM.st;if(!st)return null;const b=IM.backend==='auto'?(st.forge.ok?'forge':st.comfyui.ok?'comfyui':st.cloud.length?'cloud:'+st.cloud[0].provider:null):IM.backend;
  return b==='forge'?st.forge:b==='comfyui'?st.comfyui:null}
function resolvedBackend(){const st=IM.st;if(IM.backend!=='auto')return IM.backend;return st.forge.ok?'forge':st.comfyui.ok?'comfyui':st.cloud.length?'cloud:'+st.cloud[0].provider:null}

async function renderImages(){
  const root=$('#plug');root.innerHTML='<div class="pbody"><div class="note">Looking for image generators on this PC...</div></div>';
  IM.st=await api('/api/images/status');const gallery=await api('/api/images');
  root.innerHTML='';const st=IM.st;const be=resolvedBackend();
  const wrap=el('div','iwrap');root.appendChild(wrap);const side=el('div','iside');const main=el('div','imain');wrap.append(side,main);
  // backend row
  const opts=[['auto','Automatic'],['forge','Forge / A1111 '+(st.forge.ok?'(connected)':'(not found)')],['comfyui','ComfyUI '+(st.comfyui.ok?'(connected)':'(not found)')]].concat(st.cloud.map(c=>['cloud:'+c.provider,c.label+' (cloud)']));
  const brow=el('div','prow');const bs=el('select');bs.style.flex='1';opts.forEach(([v,l])=>{const o=el('option',null,esc(l));o.value=v;bs.appendChild(o)});bs.value=IM.backend;bs.onchange=()=>{IM.backend=bs.value;renderImages()};
  const setb=el('button','btn sm','Setup');setb.onclick=()=>imageSetup();brow.append(bs,setb);side.appendChild(brow);
  const info=currentInfo();
  if(!be){side.appendChild(el('div','err','No image generator found.'));
    side.appendChild(el('div','note','Start <b>Forge</b> (or Automatic1111) with the <code>--api</code> option, or start <b>ComfyUI</b>, then press Setup &gt; Scan. You can also add an OpenAI or Grok key in Models &gt; Cloud.'));
    appLinksBox(side,['forge','a1111','sdnext','comfyui','invokeai','fooocus'],'Not installed? Get one here');
    const sc=el('button','btn pri','Scan this PC');sc.onclick=()=>{MD.sec='apps';showView('models')};side.appendChild(sc);
    const gd=el('button','btn','Setup guide');gd.style.marginLeft='6px';gd.onclick=()=>{HS.id='images';showView('help')};side.appendChild(gd)}
  const F=IM.form;const inp=(id,label,html)=>{const d=el('div','irow','<label>'+label+'</label>'+html);side.appendChild(d);return d};
  const pr=inp('p','Prompt','<textarea id="iPrompt" rows="4" placeholder="A lighthouse on a cliff at sunset, dramatic clouds, oil painting"></textarea><div class="prow"><button class="btn sm" id="iEnh">Improve with AI</button><span class="meta" id="iEnhMsg"></span></div>');
  pr.querySelector('#iPrompt').value=F.prompt;pr.querySelector('#iPrompt').oninput=e=>F.prompt=e.target.value;
  pr.querySelector('#iEnh').onclick=async()=>{if(!F.prompt.trim())return;if(!ST.model){alert('Pick a chat model first (top right on the Chat tab).');return}const m=pr.querySelector('#iEnhMsg');m.textContent='Thinking...';const r=await api('/api/images/enhance',{model:ST.model,prompt:F.prompt});if(r.prompt){F.prompt=r.prompt;pr.querySelector('#iPrompt').value=r.prompt;m.textContent='Improved.'}else m.textContent=r.error||'Failed'};
  const cloud=be&&be.startsWith('cloud:');
  if(!cloud){const n=inp('n','Negative prompt','<textarea id="iNeg" rows="2" placeholder="blurry, low quality, extra fingers"></textarea>');n.querySelector('#iNeg').value=F.negative;n.querySelector('#iNeg').oninput=e=>F.negative=e.target.value}
  const sz=inp('s','Size','<select id="iSize"></select>');SIZES.forEach(([v,l])=>{const o=el('option',null,esc(l));o.value=v;sz.querySelector('select').appendChild(o)});sz.querySelector('select').value=F.size;sz.querySelector('select').onchange=e=>F.size=e.target.value;
  if(info&&info.ok){
    const ck=inp('c','Model / checkpoint','<select id="iCk"></select>');const cs=ck.querySelector('select');(info.models||[]).forEach(m=>{const o=el('option',null,esc(m));o.value=m;cs.appendChild(o)});if(!info.models.length)cs.innerHTML='<option value="">(default)</option>';
    cs.value=F.checkpoint&&info.models.includes(F.checkpoint)?F.checkpoint:(info.current||'');F.checkpoint=cs.value;cs.onchange=e=>F.checkpoint=e.target.value;
    const sm=inp('sa','Sampler','<select id="iSam"></select>');const ss=sm.querySelector('select');ss.innerHTML='<option value="">(default)</option>';(info.samplers||[]).forEach(m=>{const o=el('option',null,esc(m));o.value=m;ss.appendChild(o)});ss.value=F.sampler;ss.onchange=e=>F.sampler=e.target.value;
    const nums=inp('x','','<div class="prow"><label>Steps</label><input id="iSteps" type="number" min="1" max="150" style="width:70px"><label>CFG</label><input id="iCfg" type="number" step="0.5" style="width:70px"></div>');
    nums.querySelector('#iSteps').value=F.steps;nums.querySelector('#iSteps').oninput=e=>F.steps=+e.target.value;nums.querySelector('#iCfg').value=F.cfg;nums.querySelector('#iCfg').oninput=e=>F.cfg=+e.target.value}
  const sd=inp('sd','','<div class="prow"><label>Seed</label><input id="iSeed" type="number" style="width:110px"><span class="meta">-1 = random</span><label>Images</label><select id="iCount" style="width:60px"><option>1</option><option>2</option><option>3</option><option>4</option></select></div>');
  sd.querySelector('#iSeed').value=F.seed;sd.querySelector('#iSeed').oninput=e=>F.seed=+e.target.value;sd.querySelector('#iCount').value=F.count;sd.querySelector('#iCount').onchange=e=>F.count=+e.target.value;
  if(be==='forge'){const im=inp('i','Start from a picture (optional)','<input type="file" id="iInit" accept="image/*"><div class="prow"><label>Change amount</label><input type="range" id="iDen" min="0" max="100" value="'+Math.round(F.denoise*100)+'" style="width:150px"><span class="meta" id="iDenL">'+F.denoise+'</span></div>');
    im.querySelector('#iInit').onchange=e=>{const f=e.target.files[0];if(!f){IM.init=null;return}const r=new FileReader();r.onload=()=>IM.init=r.result.split(',')[1];r.readAsDataURL(f)};
    im.querySelector('#iDen').oninput=e=>{F.denoise=e.target.value/100;im.querySelector('#iDenL').textContent=F.denoise}}
  const go=el('div','prow');const gb=el('button','btn pri','Generate');const sb=el('button','btn','Stop');sb.style.display='none';go.append(gb,sb);side.appendChild(go);
  const bar=el('div','bar','<i></i>');const msg=el('div','note','');side.append(bar,msg);
  gb.onclick=async()=>{if(!F.prompt.trim()){msg.textContent='Write a prompt first.';return}if(!be){msg.textContent='No image generator is available.';return}
    IM.busy=true;gb.disabled=true;sb.style.display='';msg.textContent='Starting...';bar.firstChild.style.width='3%';const [w,h]=F.size.split('x').map(Number);
    const body={backend:be,prompt:F.prompt,negative:F.negative,width:w,height:h,steps:F.steps,cfg:F.cfg,seed:F.seed,count:F.count,sampler:F.sampler,checkpoint:F.checkpoint,init_image:be==='forge'?IM.init:'',denoise:F.denoise};
    let err=null;await sseJson('/api/images/generate',body,ev=>{if(ev.type==='start')IM.run=ev.run;else if(ev.type==='progress'){bar.firstChild.style.width=ev.pct+'%';msg.textContent=ev.text}else if(ev.type==='image'){gallery.unshift(ev.image);drawGallery()}else if(ev.type==='error'){err=ev.text}else if(ev.type==='done'&&ev.cancelled){msg.textContent='Stopped.'}});
    IM.busy=false;gb.disabled=false;sb.style.display='none';if(err){msg.textContent='Error: '+err}else if(msg.textContent!=='Stopped.'){msg.textContent='Done.';bar.firstChild.style.width='100%'}};
  sb.onclick=()=>{if(IM.run)api('/api/stop',{run:IM.run})};
  // gallery
  main.appendChild(el('h3',null,'Your pictures'));const g=el('div','igrid');main.appendChild(g);
  function drawGallery(){g.innerHTML='';if(!gallery.length){g.appendChild(el('div','note','Nothing yet. Write a prompt and press Generate. Pictures are saved in ~/.marchand/images.'));return}
    gallery.forEach(rec=>{const c=el('div','icard');const im=el('img');im.alt=rec.prompt;imgUrl(rec.name).then(u=>im.src=u);c.appendChild(im);c.appendChild(el('div','cap',esc(rec.prompt.slice(0,70))));c.onclick=()=>viewImage(rec,gallery,drawGallery);g.appendChild(c)})}
  drawGallery();
}
function viewImage(rec,gallery,redraw){
  const m=$('#mImg');const body=$('#imgBody');body.innerHTML='';const im=el('img');im.style.cssText='max-width:100%;max-height:60vh;border-radius:8px;display:block;margin:0 auto';imgUrl(rec.name).then(u=>im.src=u);body.appendChild(im);
  body.appendChild(el('div','note','<b>Prompt:</b> '+esc(rec.prompt)+(rec.negative?'<br><b>Negative:</b> '+esc(rec.negative):'')+'<br>'+esc(rec.backend)+' - '+esc(rec.model||'')+' - seed '+rec.seed+' - '+rec.width+'x'+rec.height+(rec.steps?' - '+rec.steps+' steps':'')));
  const a=el('div','prow');
  const dl=el('button','btn sm','Download');dl.onclick=async()=>{const u=await imgUrl(rec.name);const l=el('a');l.href=u;l.download=rec.name;l.click()};
  const use=el('button','btn sm','Use in chat');use.onclick=async()=>{const r=await fetch('/api/image?name='+encodeURIComponent(rec.name));const b=await r.blob();const rd=new FileReader();rd.onload=()=>{ST.attach.push({name:rec.name,image:rd.result.split(',')[1]});renderChips();m.classList.remove('on');setMode('chat')};rd.readAsDataURL(b)};
  const re=el('button','btn sm','Reuse settings');re.onclick=()=>{Object.assign(IM.form,{prompt:rec.prompt,negative:rec.negative||'',size:rec.width+'x'+rec.height,steps:rec.steps||25,cfg:rec.cfg||7,seed:rec.seed,sampler:rec.sampler||''});m.classList.remove('on');renderImages()};
  const del=el('button','btn sm','Delete');del.onclick=async()=>{if(!confirm('Delete this picture?'))return;await api('/api/images/delete',{name:rec.name});const i=gallery.indexOf(rec);if(i>=0)gallery.splice(i,1);m.classList.remove('on');redraw()};
  a.append(dl,use,re,del);body.appendChild(a);m.classList.add('on');
}
async function imageSetup(){
  const s=await api('/api/settings');const c=Object.assign({forge_url:'http://127.0.0.1:7860',comfy_url:'http://127.0.0.1:8188',default:'auto',cloud_provider:'openai',cloud_model:'gpt-image-1',comfy_workflow:''},s.images||{});
  const b=$('#imgBody');b.innerHTML='';
  b.appendChild(el('h3',null,'Image generator setup'));
  const f=el('div','pform','<label>Forge / Automatic1111 / SD.Next address (start it with the --api option)</label><div class="prow"><input id="sF" style="flex:1"><button class="btn sm" id="tF">Test</button></div><div class="note" id="rF"></div><label>ComfyUI address</label><div class="prow"><input id="sC" style="flex:1"><button class="btn sm" id="tC">Test</button></div><div class="note" id="rC"></div><label>Default generator</label><select id="sD"><option value="auto">Automatic (first one found)</option><option value="forge">Forge / A1111</option><option value="comfyui">ComfyUI</option><option value="cloud:openai">OpenAI (cloud)</option><option value="cloud:xai">Grok (cloud)</option></select><label>ComfyUI custom workflow (optional, API format JSON). Placeholders: %prompt% %negative% %seed% %steps% %cfg% %width% %height% %checkpoint% %sampler% %scheduler% %count%</label><textarea id="sW" rows="6" placeholder="Leave empty to use the built-in text-to-image workflow"></textarea><label>Cloud image model</label><input id="sM" placeholder="gpt-image-1 or grok-2-image"><div class="foot"><button class="btn" data-close>Cancel</button><button class="btn pri" id="sSaveI">Save</button></div>');
  b.appendChild(f);f.querySelector('#sF').value=c.forge_url;f.querySelector('#sC').value=c.comfy_url;f.querySelector('#sD').value=c.default;f.querySelector('#sW').value=c.comfy_workflow||'';f.querySelector('#sM').value=c.cloud_model;
  const testF=async()=>{await api('/api/settings',{images:Object.assign({},c,{forge_url:f.querySelector('#sF').value,comfy_url:f.querySelector('#sC').value})});const st=await api('/api/images/status');f.querySelector('#rF').textContent=st.forge.ok?'Connected. '+st.forge.models.length+' checkpoints.':'Not reachable: '+(st.forge.error||'');f.querySelector('#rC').textContent=st.comfyui.ok?'Connected. '+st.comfyui.models.length+' checkpoints.':'Not reachable: '+(st.comfyui.error||'')};
  f.querySelector('#tF').onclick=testF;f.querySelector('#tC').onclick=testF;
  f.querySelector('#sSaveI').onclick=async()=>{const wf=f.querySelector('#sW').value.trim();if(wf){try{JSON.parse(wf)}catch(e){alert('The workflow is not valid JSON: '+e.message);return}}
    const cp=f.querySelector('#sD').value.startsWith('cloud:')?f.querySelector('#sD').value.slice(6):c.cloud_provider;
    await api('/api/settings',{images:{forge_url:f.querySelector('#sF').value,comfy_url:f.querySelector('#sC').value,default:f.querySelector('#sD').value,comfy_workflow:wf,cloud_provider:cp,cloud_model:f.querySelector('#sM').value}});$('#mImg').classList.remove('on');renderImages()};
  $('#mImg').classList.add('on');
}
async function chatImage(prompt){
  const c=ST.convo;c.model=ST.model;c.mode=ST.mode;if(!c.blocks.length)c.title=('Image: '+prompt).slice(0,48);
  c.blocks.push({role:'user',text:'/image '+prompt});const ab={role:'assistant',parts:[{t:'note',text:'Generating...'}]};c.blocks.push(ab);renderAll();
  const msgEl=$('#list').lastElementChild;ST.running=true;setSend(true);let err=null,got=0;
  try{await sseJson('/api/images/generate',{prompt},ev=>{if(ev.type==='start')ST.run=ev.run;else if(ev.type==='progress'){msgEl.firstChild.textContent=ev.text+' '+ev.pct+'%'}else if(ev.type==='image'){got++;const p={t:'img',name:ev.image.name,prompt};ab.parts.push(p);msgEl.appendChild(renderPart(p));scrollDown(true)}else if(ev.type==='error')err=ev.text})}catch(e){err=String(e)}
  ab.parts=ab.parts.filter(p=>!(p.t==='note'&&p.text==='Generating...'));if(msgEl.firstChild&&msgEl.firstChild.classList&&msgEl.firstChild.classList.contains('note'))msgEl.firstChild.remove();
  if(err){ab.parts.push({t:'err',text:err});msgEl.appendChild(renderPart({t:'err',text:err}))}
  ST.running=false;ST.run=null;setSend(false);c.updated=Date.now();await api('/api/convo',c);loadConvos()}
