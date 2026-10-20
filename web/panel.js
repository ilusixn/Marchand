const PANEL={open:LS.get('panel')!=='0',cc:null,git:null,sec:JSON.parse(LS.get('panelSecs')||'{}')};
function fmtLeft(ts){if(!ts)return '';const s=ts-Date.now()/1000;if(s<=0)return 'resets now';const h=Math.floor(s/3600),m=Math.floor(s%3600/60);if(h>=24){const d=new Date(ts*1000);return 'resets '+d.toLocaleDateString(undefined,{weekday:'short'})+' '+d.toLocaleTimeString(undefined,{hour:'2-digit',minute:'2-digit'})}return 'resets in '+(h?h+'h ':'')+m+'m'}
function meter(pct){const p=Math.max(0,Math.min(100,Math.round(pct)));const col=p>=90?'var(--bad)':p>=75?'#d9a441':'var(--accent)';return '<div class="meter"><i style="width:'+p+'%;background:'+col+'"></i></div><span class="mpct">'+p+'%</span>'}
function psec(id,title,right,body){const open=PANEL.sec[id]!==false;const d=el('div','psbox');const h=el('div','pshead','<span>'+esc(title)+' <span class="chev">'+(open?'&#9662;':'&#9656;')+'</span></span><span class="psright">'+(right||'')+'</span>');
  h.onclick=e=>{if(e.target.closest('button'))return;PANEL.sec[id]=!open;LS.set('panelSecs',JSON.stringify(PANEL.sec));renderPanel()};d.appendChild(h);if(open&&body){const b=el('div','psbody');if(typeof body==='string')b.innerHTML=body;else b.appendChild(body);d.appendChild(b)}return d}
function convoOutputs(){const c=ST.convo,out=[],seen=new Set();if(!c)return out;
  (c.blocks||[]).forEach(b=>(b.parts||[]).forEach(p=>{
    if(p.t==='tool'&&p.status==='ok'){let a=p.args;if(typeof a==='string'){try{a=JSON.parse(a)}catch(e){a={}}}a=a||{};
      const path=(['write_file','generate_image'].includes(p.name)&&(a.path||(p.result||'').match(/to (\S+) \(/)?.[1]))||(p.name==='Write'&&a.file_path);
      if(path&&!seen.has(path)){seen.add(path);out.push({kind:'file',path,label:path.split(/[\\/]/).pop()})}}
    if(p.t==='img'&&!seen.has(p.name)){seen.add(p.name);out.push({kind:'img',name:p.name,label:(p.prompt||p.name).slice(0,40)})}}));
  return out}
function convoChanges(){let add=0,del=0,files=new Set(),diffs=[];const c=ST.convo;if(!c)return {add,del,files:0,diffs};
  (c.blocks||[]).forEach(b=>(b.parts||[]).forEach(p=>{if(p.t==='tool'&&p.diff&&p.status==='ok'){diffs.push(p.diff);p.diff.split('\n').forEach(l=>{if(l.startsWith('+++')){files.add(l.slice(6))}else if(l.startsWith('+')&&!l.startsWith('+++'))add++;else if(l.startsWith('-')&&!l.startsWith('---'))del++})}}));
  return {add,del,files:files.size,diffs}}
function contextPct(){const c=ST.convo;if(!c)return 0;const m=ST.model||'';
  if(m.startsWith('claude-code::')&&c.lastCC&&c.lastCC.usage){const u=c.lastCC.usage;const used=(u.input_tokens||0)+(u.cache_read_input_tokens||0)+(u.cache_creation_input_tokens||0)+(u.output_tokens||0);const w=(PANEL.cc&&PANEL.cc.usage&&PANEL.cc.usage.window)||200000;return 100*used/w}
  const chars=JSON.stringify(c.history||[]).length;return 100*chars/4/((ST.settings&&ST.settings.num_ctx)||16384)}
async function refreshPanelData(){try{PANEL.cc=await api('/api/cc/status')}catch(e){}if(ST.project){try{PANEL.git=await api('/api/git?root='+encodeURIComponent(ST.project))}catch(e){}}renderPanel()}
async function renderPanel(){
  const box=$('#files');if(!box)return;box.classList.toggle('on',PANEL.open&&$('#body').style.display!=='none');if(!PANEL.open)return;
  box.innerHTML='';const c=ST.convo||{};
  const env=el('div');
  env.appendChild(el('div','prow2','<span class="ico">&#9729;</span><span>'+esc((ST.model||'no model').replace('claude-code::','Claude ').replace('::',' / '))+(ST.model&&ST.model.startsWith('claude-code::')?' &middot; '+esc(($('#effort')||{}).value||'high'):'')+'</span>'));
  const pr=el('div','prow2 click','<span class="ico">&#128193;</span><span>'+esc(ST.project?ST.project.split(/[\\/]/).filter(Boolean).pop():'choose a project folder')+'</span><span class="plus">+</span>');pr.onclick=chooseDir;env.appendChild(pr);
  if(PANEL.git&&PANEL.git.git)env.appendChild(el('div','prow2','<span class="ico">&#5833;</span><span>'+esc(PANEL.git.branch)+'</span>'+(PANEL.git.changed?'<span class="meta">'+PANEL.git.changed+' changed</span>':'')));
  box.appendChild(psec('env','Environment','',env));
  const cp=contextPct();box.appendChild(psec('ctx','Context','<span class="mini">'+Math.round(cp)+'%</span>','<div class="mrow">'+meter(cp)+'</div><div class="meta">'+(ST.model&&ST.model.startsWith('claude-code::')?'Measured from the last Claude reply.':'Estimated from this conversation and your context size.')+'</div>'));
  const cc=PANEL.cc;
  if(cc&&cc.installed){const u=cc.usage||{},r=u.rate||{},w=r.unifiedWindows||{};const b=el('div');
    if(w.five_hour||w.seven_day){
      b.innerHTML='<div class="ulabel">Session (5 hours)</div><div class="mrow">'+meter(100*((w.five_hour||{}).utilization||0))+'</div><div class="meta">'+fmtLeft((w.five_hour||{}).resetsAt)+'</div>'+
        '<div class="ulabel">Weekly (7 days)</div><div class="mrow">'+meter(100*((w.seven_day||{}).utilization||0))+'</div><div class="meta">'+fmtLeft((w.seven_day||{}).resetsAt)+'</div>'+
        '<div class="ulabel">Extra usage</div><div class="meta">'+(r.isUsingOverage?'in use now':(r.overageStatus==='allowed'?'available':'off'+(r.overageDisabledReason?' ('+esc(String(r.overageDisabledReason).replace(/_/g,' '))+')':'')))+'</div>'+
        (u.today_cost!=null?'<div class="ulabel">Today in Marchand</div><div class="meta">'+(u.today_runs||0)+' requests, ~$'+Number(u.today_cost).toFixed(2)+' API-equivalent (your plan is not charged per request)</div>':'')+
        '<div class="meta">Updated '+(u.rate_time?new Date(u.rate_time*1000).toLocaleTimeString():'never')+'</div>'}
    else b.innerHTML='<div class="meta">No usage data yet. It appears after your first Claude request, or press Refresh.</div>';
    const rf=el('button','btn sm','Refresh');rf.title='Sends one tiny Haiku request to read your current limits';rf.onclick=async()=>{rf.disabled=true;rf.textContent='Checking...';const x=await api('/api/cc/refresh',{});if(x.error)alert(x.error);await refreshPanelData()};
    b.appendChild(rf);box.appendChild(psec('usage','Claude plan usage','',b))}
  const outs=convoOutputs();const ol=el('div');
  if(!outs.length)ol.appendChild(el('div','meta','Files the AI creates appear here.'));
  outs.slice(0,30).forEach(o=>{const r=el('div','prow2 click','<span class="ico">'+(o.kind==='img'?'&#128444;':'&#128196;')+'</span><span class="ell">'+esc(o.label)+'</span>');
    r.onclick=async()=>{if(o.kind==='img'){const all=await api('/api/images');const rec=all.find(x=>x.name===o.name);if(rec)viewImage(rec,all,()=>{})}else if(ST.project){const x=await api('/api/file?root='+encodeURIComponent(ST.project)+'&path='+encodeURIComponent(o.path));$('#fName').textContent=o.path;$('#fText').textContent=x.missing?'(file no longer exists)':(x.text||'(binary or empty file)');openModal('#mFile')}};ol.appendChild(r)});
  box.appendChild(psec('out','Outputs','',ol));
  const ch=convoChanges();const cb=el('div');
  cb.appendChild(el('div','prow2','<span class="ico">&#128221;</span><span class="add">+'+ch.add+'</span><span class="del">-'+ch.del+'</span><span class="meta">'+ch.files+' file'+(ch.files===1?'':'s')+'</span>'));
  const acts=el('div','prow');const vd=el('button','btn sm','View diff');vd.onclick=async()=>{let d=ch.diffs.join('\n\n');if(PANEL.git&&PANEL.git.git){const g=await api('/api/git/diff?root='+encodeURIComponent(ST.project));if(g.diff)d=g.diff}$('#iTitle').textContent='Changes';$('#iBody').innerHTML='<div class="diff" style="max-height:65vh">'+diffHtml(d||'(no changes)')+'</div>';openModal('#mInfo')};
  acts.appendChild(vd);if(PANEL.git&&PANEL.git.git){const cm=el('button','btn sm pri','Commit');cm.onclick=async()=>{const msg=prompt('Commit message for all changes in '+PANEL.git.branch+':','Update via Marchand');if(!msg)return;const r=await api('/api/git/commit',{root:ST.project,message:msg});alert(r.ok?'Committed.\n'+r.output:'Commit failed:\n'+(r.output||r.error));refreshPanelData()};acts.appendChild(cm)}
  cb.appendChild(acts);box.appendChild(psec('chg','Changes','',cb));
  const fb=el('div');const up=el('button','btn sm','Upload files');const fi=el('input');fi.type='file';fi.multiple=true;fi.hidden=true;up.onclick=()=>fi.click();fi.onchange=async()=>{await storeFiles(fi.files,false);fi.value='';renderPanel()};
  fb.append(up,fi);const list=el('div');fb.appendChild(list);box.appendChild(psec('files','Files','',fb));
  if(c.id){api('/api/files?convo='+encodeURIComponent(c.id)).then(items=>{if(!items.length){list.appendChild(el('div','meta','Files you attach or upload are kept here for this conversation. Click one to attach it again.'));return}
    items.forEach(f=>{const r=el('div','prow2 click','<span class="ico">'+(f.type.startsWith('image/')?'&#128444;':f.type.startsWith('video/')?'&#127916;':'&#128206;')+'</span><span class="ell">'+esc(f.name)+'</span><span class="meta">'+(f.size>1048576?(f.size/1048576).toFixed(1)+' MB':Math.ceil(f.size/1024)+' KB')+'</span><span class="x">&#10005;</span>');
      r.querySelector('.x').onclick=async e=>{e.stopPropagation();await api('/api/files/delete',{convo:c.id,name:f.name});renderPanel()};r.onclick=()=>attachStored(f);list.appendChild(r)})})}
  if(ST.mode==='code'&&ST.project){const tb=el('div');const t=el('div');t.id='tree';tb.appendChild(t);box.appendChild(psec('tree','Project files','',tb));loadTree()}
}
async function uploadFile(f){const c=ST.convo;const r=await fetch('/api/upload?convo='+encodeURIComponent(c.id)+'&name='+encodeURIComponent(f.name),{method:'POST',body:f});return r.json()}
async function videoFrames(name){return api('/api/video/frames',{convo:ST.convo.id,name,count:6})}
async function storeFiles(files,attach){for(const f of [...files]){const up=await uploadFile(f);if(up.error){alert(up.error);continue}if(attach)await attachStored({name:up.name,type:f.type||'',size:f.size},f)}renderChips();renderPanel()}
async function attachStored(f,fileObj){
  const t=f.type||'';
  if(t.startsWith('video/')||/\.(mp4|mov|webm|mkv|avi|m4v|gif)$/i.test(f.name)){const r=await videoFrames(f.name);if(r.error){alert(r.error);return}
    r.frames.forEach(fr=>ST.attach.push({name:f.name+' @ '+fr.t+'s',image:fr.b64}));ST.attach.push({name:f.name+' (video info)',text:'Video '+f.name+', '+r.duration+' seconds long. The images are '+r.frames.length+' frames taken at '+r.frames.map(x=>x.t+'s').join(', ')+'.'});renderChips();return}
  const blob=fileObj||await (await fetch('/api/stored?convo='+encodeURIComponent(ST.convo.id)+'&name='+encodeURIComponent(f.name))).blob();
  if(/\.(docx|pptx|xlsx|odt|ods|odp|pdf|zip|jar|apk)$/i.test(f.name)){const x=await api('/api/extract?convo='+encodeURIComponent(ST.convo.id)+'&name='+encodeURIComponent(f.name));if(x.text){ST.attach.push({name:f.name,text:'[Text extracted from '+f.name+']\n'+x.text});renderChips();return}}
  if(t.startsWith('image/')||/\.(png|jpe?g|webp|bmp)$/i.test(f.name)){const b64=await new Promise(res=>{const rd=new FileReader();rd.onload=()=>res(rd.result.split(',')[1]);rd.readAsDataURL(blob)});ST.attach.push({name:f.name,image:b64})}
  else if(t.startsWith('text/')||/\.(txt|md|py|js|ts|json|csv|log|html|css|c|cpp|h|hpp|java|cs|go|rs|lua|sql|xml|yml|yaml|ini|toml|sh|bat|ps1)$/i.test(f.name)||blob.size<200000&&!/\.(pdf|zip|exe|dll|bin|7z|rar)$/i.test(f.name)){ST.attach.push({name:f.name,text:(await blob.text()).slice(0,60000)})}
  else ST.attach.push({name:f.name,text:'[A file named '+f.name+' ('+Math.ceil(blob.size/1024)+' KB) is stored with this conversation; its content is binary and cannot be shown to the model.]'});
  renderChips()}
