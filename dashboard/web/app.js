const byId=(id)=>document.getElementById(id);
const all=(selector)=>[...document.querySelectorAll(selector)];
let latest={};
let activePeriod="day";
let activeFilter="all";
let refreshTimer=null;
let autoRefresh=true;

const actionMap=[
  ["up","Start range","Start the training targets","▶"],
  ["down","Stop range","Stop the lab stack","■"],
  ["scan","Run scan","Nmap and Nuclei","⌁"],
  ["defend","Defense","Run defensive pipeline","◆"],
  ["review","Review","Repository review","⌘"],
  ["report","Report","Generate evidence","▤"]
];

function esc(value){
  return String(value??"").replace(/[&<>"']/g,(char)=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[char]);
}

function toast(message){
  const node=byId("toast");
  node.textContent=message;
  node.classList.add("show");
  window.setTimeout(()=>node.classList.remove("show"),2400);
}

function stateClass(state){
  const value=String(state||"").toLowerCase();
  if(["succeeded","success","online","running","healthy","ready","authorized"].includes(value))return "ok";
  if(["failed","failure","offline","unhealthy","error"].includes(value))return "bad";
  return "warn";
}

function parsePercent(value){
  const parsed=Number.parseFloat(String(value||"0").replace("%",""));
  return Number.isFinite(parsed)?Math.max(0,Math.min(100,parsed)):0;
}

function formatNumber(value){
  return new Intl.NumberFormat().format(Number(value||0));
}

function formatDate(value){
  const date=value instanceof Date?value:new Date(value);
  return Number.isNaN(date.getTime())?"Unknown":new Intl.DateTimeFormat(undefined,{month:"short",day:"numeric",hour:"numeric",minute:"2-digit"}).format(date);
}

function formatDuration(ms){
  if(!Number.isFinite(ms)||ms<=0)return "0m";
  const minutes=Math.floor(ms/60000);
  const hours=Math.floor(minutes/60);
  const mins=minutes%60;
  if(hours>=24){const days=Math.floor(hours/24);return `${days}d ${hours%24}h`;}
  return hours?`${hours}h ${mins}m`:`${Math.max(1,mins)}m`;
}

async function post(url,payload){
  const response=await fetch(url,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(payload)});
  const data=await response.json();
  if(!response.ok)throw new Error(data.error||"Request rejected");
  return data;
}

async function platformAction(operation,payload={}){
  try{
    const data=await post("/api/platform/action",{operation,...payload});
    toast(`${data.action||operation} queued`);
    window.setTimeout(refresh,1000);
  }catch(error){toast(error.message);}
}

async function securityAction(action,button){
  if(button)button.disabled=true;
  try{
    await post("/api/action",{action});
    toast(`${action} queued`);
    window.setTimeout(refresh,1000);
  }catch(error){toast(error.message);}
  finally{if(button)window.setTimeout(()=>button.disabled=false,700);}
}

function setPage(page){
  all(".page").forEach((node)=>node.classList.toggle("active",node.id===`page-${page}`));
  all("[data-page]").forEach((node)=>node.classList.toggle("active",node.dataset.page===page||(page==="detail"&&node.dataset.page==="systems")));
  window.scrollTo({top:0,behavior:"smooth"});
}

function openSheet(){
  byId("project-sheet").classList.add("open");
  document.body.style.overflow="hidden";
  window.setTimeout(()=>byId("project-name").focus(),100);
}

function closeSheet(){
  byId("project-sheet").classList.remove("open");
  document.body.style.overflow="";
}

function totalFindings(data){
  return Object.values(data.findings||{}).reduce((sum,value)=>sum+Number(value||0),0);
}

function targetStatus(data){
  const keys=["juice-shop","dvwa","webgoat"];
  const online=keys.filter((key)=>data.services?.[key]?.running).length;
  return {online,total:keys.length};
}

function controlPlaneStatus(data){
  const rows=Object.values(data.control_plane||{});
  return {online:rows.filter((row)=>row.running).length,total:rows.length};
}

function activeJobs(data){
  const jobs=data.platform?.jobs||[];
  return jobs.filter((job)=>["running","queued","submitted"].includes(String(job.state||"").toLowerCase())).length;
}

function averageCpu(data){
  const values=Object.values(data.services||{}).map((service)=>parsePercent(service.stats?.cpu)).filter((value)=>Number.isFinite(value));
  return values.length?Math.round(values.reduce((sum,value)=>sum+value,0)/values.length):0;
}

function renderHome(data){
  const platform=data.platform||{};
  const projects=platform.projects||[];
  const profiles=platform.profiles||[];
  const findings=totalFindings(data);
  const targets=targetStatus(data);
  const plane=controlPlaneStatus(data);
  const runningJobs=activeJobs(data);
  const cpu=averageCpu(data);
  const cards=[
    {key:"lab",icon:"◈",accent:"#438dff",title:"Cloud Lab",status:data.lab||"offline",metric:`${targets.online}/${targets.total}`,label:"targets online",foot:`Live CPU avg ${cpu}%`,value:targets.total?Math.round(targets.online/targets.total*100):0,go:"detail"},
    {key:"dev",icon:"</>",accent:"#61db8d",title:"Development",status:platform.error?"degraded":"ready",metric:formatNumber(projects.length),label:"projects",foot:`${runningJobs} active jobs · ${profiles.length} profiles`,value:projects.length?Math.min(100,projects.length*10):0,go:"systems",filter:"projects"},
    {key:"security",icon:"⬡",accent:"#9a7cff",title:"Security Lab",status:data.lab==="online"?"healthy":data.lab||"offline",metric:formatNumber(findings),label:"findings",foot:`${data.cases||0} research cases`,value:findings?Math.min(100,findings*8):0,go:"detail"},
    {key:"infra",icon:"▤",accent:"#ff9c42",title:"Infrastructure",status:plane.total&&plane.online===plane.total?"online":plane.online?"partial":"offline",metric:`${plane.online}/${plane.total||0}`,label:"control services",foot:`${platform.runners?.local?.length||0} local runners`,value:plane.total?Math.round(plane.online/plane.total*100):0,go:"systems",filter:"infrastructure"}
  ];
  byId("home-grid").innerHTML=cards.map((card)=>`<button class="hero-card" style="--card-accent:${card.accent}" data-home-go="${card.go}" data-home-filter="${card.filter||""}"><div class="hero-icon">${card.icon}</div><h3>${esc(card.title)}</h3><span class="status-pill ${stateClass(card.status)}">${esc(card.status)}</span><div class="hero-metric">${esc(card.metric)}</div><div class="hero-label">${esc(card.label)}</div><div class="hero-foot"><span>${esc(card.foot)}</span><span>›</span></div></button>`).join("");
  all("[data-home-go]").forEach((button)=>button.onclick=()=>{
    if(button.dataset.homeFilter){activeFilter=button.dataset.homeFilter;renderSystems(latest);}
    if(button.dataset.homeGo==="detail")openDetail("lab","main");else setPage(button.dataset.homeGo);
  });
  const platformHealthy=!platform.error&&(!plane.total||plane.online===plane.total);
  byId("system-state").textContent=platformHealthy?"All core systems operational":"System attention required";
  byId("system-state").className=platformHealthy?"ok":"warn";
  byId("system-detail").textContent=`${plane.online}/${plane.total||0} control services · ${runningJobs} active jobs · ${targets.online}/${targets.total} lab targets`;
}

function projectCard(project){
  const commands=(project.commands||[]).slice(0,5).map((command)=>`<button data-run-project="${esc(project.name)}" data-command="${esc(command)}">${esc(command)}</button>`).join("");
  const publish=project.repository?"":`<button data-publish-project="${esc(project.name)}">Publish private</button>`;
  return `<div class="resource-card" data-kind="projects"><div class="resource-icon">⌘</div><div class="resource-main"><div class="resource-title">${esc(project.name)}</div><div class="resource-meta"><span>${esc(project.profile)}</span><span>${esc(project.runner||"local")}</span>${project.repository?`<span class="ok">${esc(project.repository)}</span>`:"<span>Local only</span>"}</div><div class="project-actions">${commands}${publish}</div></div><div class="resource-side"><strong>Project</strong><small>${esc(project.branch||"")}</small></div></div>`;
}

function serviceResource(key,service){
  const cpu=parsePercent(service.stats?.cpu);
  return `<button class="resource-card" data-kind="services" data-detail-kind="service" data-detail-name="${esc(key)}"><div class="resource-icon">▣</div><div class="resource-main"><div class="resource-title">${esc(service.label||key)}</div><div class="resource-meta"><span class="${service.running?"ok":"bad"}">● ${service.running?"Online":"Offline"}</span><span>CPU ${esc(service.stats?.cpu||"0%")}</span><span>${esc(service.health||"n/a")}</span></div><div class="progress" style="margin-top:9px;--value:${cpu}%;--bar:${service.running?"var(--green)":"var(--red)"}"><span></span></div></div><div class="resource-side"><strong>${cpu}%</strong><small>CPU</small></div></button>`;
}

function profileCard(profile){
  const stack=(profile.stack||[]).slice(0,4).map((item)=>`<span>${esc(item)}</span>`).join("");
  return `<div class="resource-card" data-kind="profiles"><div class="resource-icon">◇</div><div class="resource-main"><div class="resource-title">${esc(profile.title||profile.name)}</div><div class="resource-meta"><span>${esc(profile.category||"profile")}</span><span>${esc(profile.runner||"")}</span>${stack}</div><div class="project-actions"><button data-create-profile="${esc(profile.name)}">Create project</button></div></div><div class="resource-side"><strong>${esc((profile.stack||[]).length)}</strong><small>stack items</small></div></div>`;
}

function infrastructureCard(name,row){
  return `<button class="resource-card" data-kind="infrastructure" data-detail-kind="control" data-detail-name="${esc(name)}"><div class="resource-icon">⌁</div><div class="resource-main"><div class="resource-title">${esc(name)}</div><div class="resource-meta"><span class="${row.running?"ok":"bad"}">● ${row.running?"Running":"Stopped"}</span><span>${esc(row.status||"unknown")}</span></div></div><div class="resource-side"><strong>${row.running?"UP":"DOWN"}</strong><small>control plane</small></div></button>`;
}

function wireResourceButtons(){
  all("[data-detail-kind]").forEach((button)=>button.onclick=()=>openDetail(button.dataset.detailKind,button.dataset.detailName));
  all("[data-run-project]").forEach((button)=>button.onclick=(event)=>{event.stopPropagation();platformAction("run-job",{project:button.dataset.runProject,command:button.dataset.command});});
  all("[data-publish-project]").forEach((button)=>button.onclick=(event)=>{event.stopPropagation();platformAction("publish-project",{project:button.dataset.publishProject});});
  all("[data-create-profile]").forEach((button)=>button.onclick=(event)=>{event.stopPropagation();byId("project-profile").value=button.dataset.createProfile;openSheet();});
}

function renderSystems(data){
  const platform=data.platform||{};
  const services=Object.entries(data.services||{}).map(([key,value])=>serviceResource(key,value));
  const projects=(platform.projects||[]).map(projectCard);
  const profiles=(platform.profiles||[]).map(profileCard);
  const infrastructure=Object.entries(data.control_plane||{}).map(([key,value])=>infrastructureCard(key,value));
  const groups={services,projects,profiles,infrastructure};
  const rows=activeFilter==="all"?[...services,...projects,...profiles,...infrastructure]:(groups[activeFilter]||[]);
  byId("resource-list").innerHTML=rows.join("")||'<div class="empty">No resources in this view.</div>';
  all("[data-filter]").forEach((button)=>button.classList.toggle("active",button.dataset.filter===activeFilter));
  byId("resource-count").textContent=`${rows.length} items`;
  wireResourceButtons();
}

function renderProjectProfileOptions(data){
  const profiles=data.platform?.profiles||[];
  const select=byId("project-profile");
  const selected=select.value;
  select.innerHTML=profiles.map((profile)=>`<option value="${esc(profile.name)}">${esc(profile.title||profile.name)}</option>`).join("");
  if(profiles.some((profile)=>profile.name===selected))select.value=selected;
}

function openDetail(kind,name){
  const data=latest;
  let title="Main Lab";
  let status=data.lab||"offline";
  let primary="Lab availability";
  let primaryValue=0;
  let cpu="0%";
  let memory="0B / 0B";
  let network="0B / 0B";
  let health="n/a";
  if(kind==="service"){
    const service=data.services?.[name]||{};
    title=service.label||name;
    status=service.running?"online":"offline";
    primary="Current state";
    primaryValue=service.running?100:0;
    cpu=service.stats?.cpu||"0%";
    memory=service.stats?.memory||"0B / 0B";
    network=service.stats?.net||"0B / 0B";
    health=service.health||"n/a";
  }else if(kind==="control"){
    const row=data.control_plane?.[name]||{};
    title=`${name} control`;
    status=row.running?"online":"offline";
    primary="Control service";
    primaryValue=row.running?100:0;
    health=row.status||"unknown";
    cpu="n/a";
    memory="n/a";
    network="n/a";
  }else{
    const targets=targetStatus(data);
    primaryValue=targets.total?Math.round(targets.online/targets.total*100):0;
    cpu=`${averageCpu(data)}% avg`;
    memory=`${Object.values(data.services||{}).filter((service)=>service.running).length} services online`;
    network=`${targets.online}/${targets.total} targets`;
    health=data.lab||"offline";
  }
  byId("detail-title").textContent=title;
  byId("detail-status").textContent=status;
  byId("detail-status").className=`status-pill ${stateClass(status)}`;
  byId("detail-primary-label").textContent=primary;
  byId("detail-primary-value").textContent=kind==="lab"?`${primaryValue}%`:status;
  byId("detail-progress").style.setProperty("--value",`${primaryValue}%`);
  byId("detail-quality").textContent=health;
  byId("detail-quality").className=`quality ${stateClass(status)}`;
  byId("detail-cpu").textContent=cpu;
  byId("detail-memory").textContent=memory;
  byId("detail-network").textContent=network;
  renderControlPlane(data);
  setPage("detail");
}

function renderControlPlane(data){
  byId("control-plane-list").innerHTML=Object.entries(data.control_plane||{}).map(([name,row])=>`<div class="scan-row"><div><b>${esc(name)}</b><small>${esc(row.status||"unknown")}</small></div><span class="${row.running?"ok":"bad"}">${row.running?"Running":"Stopped"}</span></div>`).join("")||'<div class="empty">No control plane status.</div>';
}

function renderControls(){
  byId("control-grid").replaceChildren(...actionMap.map(([action,title,detail,icon])=>{
    const button=document.createElement("button");
    button.className="control";
    button.title=detail;
    button.innerHTML=`<div class="control-icon">${icon}</div><span>${esc(title)}</span>`;
    button.onclick=()=>securityAction(action,button);
    return button;
  }));
}

function periodMs(period){
  return {day:86400000,week:604800000,month:2592000000,year:31536000000}[period]||86400000;
}

function eventCategory(job){
  const state=String(job.state||"").toLowerCase();
  const command=String(job.command||"").toLowerCase();
  if(["failed","failure","error"].includes(state))return "error";
  if(/scan|nmap|nuclei|review|validate|defend|security|audit/.test(command))return "security";
  if(/deploy|publish|release/.test(command))return "deploy";
  if(/test|lint|check/.test(command))return "test";
  return "build";
}

function categoryColor(category){
  return {build:"var(--green)",deploy:"var(--amber)",security:"var(--purple)",test:"var(--teal)",error:"var(--red)"}[category]||"var(--blue)";
}

function jobsInPeriod(data){
  const cutoff=Date.now()-periodMs(activePeriod);
  return (data.platform?.jobs||[]).filter((job)=>{
    const stamp=new Date(job.started_at||job.finished_at||0).getTime();
    return Number.isFinite(stamp)&&stamp>=cutoff;
  });
}

function totalJobDuration(jobs){
  const now=Date.now();
  return jobs.reduce((sum,job)=>{
    const start=new Date(job.started_at||0).getTime();
    if(!Number.isFinite(start)||!start)return sum;
    const finish=new Date(job.finished_at||0).getTime();
    const end=Number.isFinite(finish)&&finish?finish:(["running","queued","submitted"].includes(String(job.state||"").toLowerCase())?now:start);
    return sum+Math.max(0,end-start);
  },0);
}

function renderTimeline(jobs){
  const bucketCount=activePeriod==="day"?24:activePeriod==="week"?14:12;
  const range=periodMs(activePeriod);
  const start=Date.now()-range;
  const width=range/bucketCount;
  const buckets=Array.from({length:bucketCount},()=>[]);
  jobs.forEach((job)=>{
    const stamp=new Date(job.started_at||job.finished_at||0).getTime();
    if(!Number.isFinite(stamp))return;
    const index=Math.min(bucketCount-1,Math.max(0,Math.floor((stamp-start)/width)));
    buckets[index].push(eventCategory(job));
  });
  const max=Math.max(1,...buckets.map((bucket)=>bucket.length));
  if(!jobs.length){byId("timeline").innerHTML='<div class="timeline-empty">No job events in this period.</div>';return;}
  byId("timeline").innerHTML=buckets.map((bucket)=>{
    if(!bucket.length)return '<div class="timeline-bar" style="--h:5%;--bar:#18212b"></div>';
    const counts=bucket.reduce((map,key)=>({...map,[key]:(map[key]||0)+1}),{});
    const category=Object.entries(counts).sort((a,b)=>b[1]-a[1])[0][0];
    const height=Math.max(18,Math.round(bucket.length/max*100));
    return `<div class="timeline-bar" title="${bucket.length} events" style="--h:${height}%;--bar:${categoryColor(category)}"></div>`;
  }).join("");
}

function renderCpuBars(data){
  const rows=Object.values(data.services||{}).map((service)=>({label:service.label,value:parsePercent(service.stats?.cpu),raw:service.stats?.cpu||"0%"}));
  byId("cpu-bars").innerHTML=rows.map((row)=>`<div class="bar-row"><label>${esc(row.label)}</label><div class="bar-rail"><div class="bar-fill" style="--value:${row.value}%;--bar:var(--blue)"></div></div><b>${esc(row.raw)}</b></div>`).join("")||'<div class="empty">No live CPU telemetry.</div>';
}

function renderFindingBars(data){
  const colors={critical:"var(--red)",high:"var(--orange)",medium:"var(--amber)",low:"var(--teal)",info:"var(--blue)"};
  const rows=["critical","high","medium","low","info"].map((level)=>({level,value:Number(data.findings?.[level]||0)}));
  const max=Math.max(1,...rows.map((row)=>row.value));
  byId("finding-bars").innerHTML=rows.map((row)=>`<div class="bar-row"><label>${row.level}</label><div class="bar-rail"><div class="bar-fill" style="--value:${Math.round(row.value/max*100)}%;--bar:${colors[row.level]}"></div></div><b>${row.value}</b></div>`).join("");
}

function renderScanHistory(data){
  const cutoff=Date.now()-periodMs(activePeriod);
  const history=(data.history||[]).filter((run)=>Number(run.modified||0)*1000>=cutoff);
  byId("scan-history").innerHTML=history.map((run)=>`<div class="scan-row"><div><b>${esc(run.name)}</b><small>${formatNumber(run.files)} evidence files</small></div><time>${formatDate(Number(run.modified)*1000)}</time></div>`).join("")||'<div class="empty">No scan history in this period.</div>';
}

function renderActivity(data){
  const jobs=jobsInPeriod(data);
  const failed=jobs.filter((job)=>["failed","failure","error"].includes(String(job.state||"").toLowerCase())).length;
  byId("activity-time").textContent=formatDuration(totalJobDuration(jobs));
  byId("activity-count").textContent=`${jobs.length} jobs`;
  const stability=data.platform?.error?"Degraded":failed?"Attention":"Stable";
  byId("activity-stability").textContent=stability;
  byId("activity-stability").className=failed||data.platform?.error?"warn":"ok";
  byId("activity-date").textContent=`Last ${activePeriod}`;
  all("[data-period]").forEach((button)=>button.classList.toggle("active",button.dataset.period===activePeriod));
  renderTimeline(jobs);
  renderCpuBars(data);
  renderFindingBars(data);
  renderScanHistory(data);
  byId("activity-log").textContent=(data.activity||[]).join("\n")||"No activity recorded.";
}

function renderSettings(data){
  const platform=data.platform||{};
  const runners=platform.runners||{};
  const gha=runners.github_actions||{};
  byId("settings-projects").textContent=platform.projects?.length||0;
  byId("settings-profiles").textContent=platform.profiles?.length||0;
  byId("settings-services").textContent=Object.keys(data.services||{}).length;
  byId("runner-summary").innerHTML=`<div class="scan-row"><div><b>GitHub Actions</b><small>${esc((gha.scopes||[]).join(", ")||"No reported scopes")}</small></div><span class="${gha.safe?"ok":"warn"}">${gha.safe?"Authorized":"Unavailable"}</span></div><div class="scan-row"><div><b>Local runners</b><small>${esc((runners.local||[]).join(", ")||"None reported")}</small></div><span>${runners.local?.length||0}</span></div><div class="scan-row"><div><b>External runners</b><small>${esc((runners.external||[]).join(", ")||"None reported")}</small></div><span>${runners.external?.length||0}</span></div>`;
  byId("tool-list").innerHTML=Object.entries(data.tools||{}).map(([tool,present])=>`<span class="chip ${present?"ok":""}">${esc(tool)}</span>`).join("")||'<span class="chip">No tool inventory</span>';
  byId("last-updated").textContent=data.timestamp?formatDate(Number(data.timestamp)*1000):"Unknown";
}

function render(data){
  latest=data;
  const platform=data.platform||{};
  byId("platform-status").textContent=platform.error?"Degraded":"Online";
  byId("platform-status").className=`status-pill ${platform.error?"warn":"ok"}`;
  renderHome(data);
  renderSystems(data);
  renderProjectProfileOptions(data);
  renderControlPlane(data);
  renderActivity(data);
  renderSettings(data);
}

async function refresh(){
  try{
    const response=await fetch("/api/status",{cache:"no-store"});
    if(!response.ok)throw new Error("Status unavailable");
    render(await response.json());
  }catch(error){
    byId("platform-status").textContent="Unavailable";
    byId("platform-status").className="status-pill bad";
    toast(error.message);
  }
}

function scheduleRefresh(){
  if(refreshTimer)window.clearInterval(refreshTimer);
  refreshTimer=autoRefresh?window.setInterval(refresh,7000):null;
  byId("refresh-toggle").classList.toggle("on",autoRefresh);
}

all("[data-page]").forEach((button)=>button.onclick=()=>setPage(button.dataset.page));
all("[data-filter]").forEach((button)=>button.onclick=()=>{activeFilter=button.dataset.filter;renderSystems(latest);});
all("[data-period]").forEach((button)=>button.onclick=()=>{activePeriod=button.dataset.period;renderActivity(latest);});
byId("new-project").onclick=openSheet;
byId("new-project-home").onclick=openSheet;
byId("close-project-sheet").onclick=closeSheet;
byId("project-sheet").onclick=(event)=>{if(event.target===byId("project-sheet"))closeSheet();};
byId("create-project").onclick=()=>{
  const name=byId("project-name").value.trim().toLowerCase();
  const profile=byId("project-profile").value;
  if(!name){toast("Enter a project name");return;}
  platformAction("create-project",{name,profile});
  byId("project-name").value="";
  closeSheet();
};
byId("scan-home").onclick=(event)=>securityAction("scan",event.currentTarget);
byId("start-home").onclick=(event)=>securityAction("up",event.currentTarget);
byId("activity-home").onclick=()=>setPage("activity");
byId("system-card").onclick=()=>openDetail("lab","main");
byId("detail-back").onclick=()=>setPage("systems");
byId("refresh-now").onclick=refresh;
byId("refresh-toggle").onclick=()=>{autoRefresh=!autoRefresh;localStorage.setItem("apotheon-auto-refresh",autoRefresh?"1":"0");scheduleRefresh();};
byId("motion-toggle").onclick=()=>{
  const reduced=document.documentElement.classList.toggle("reduced-motion");
  byId("motion-toggle").classList.toggle("on",reduced);
  localStorage.setItem("apotheon-reduced-motion",reduced?"1":"0");
};

if(localStorage.getItem("apotheon-auto-refresh")==="0")autoRefresh=false;
if(localStorage.getItem("apotheon-reduced-motion")==="1"){
  document.documentElement.classList.add("reduced-motion");
  byId("motion-toggle").classList.add("on");
}
const reducedStyle=document.createElement("style");
reducedStyle.textContent=".reduced-motion *{scroll-behavior:auto!important;transition:none!important;animation:none!important}";
document.head.appendChild(reducedStyle);
renderControls();
scheduleRefresh();
refresh();
