(function(){
  const dataEl=document.getElementById('stats-chart-data');
  if(!dataEl)return;
  let payload={};
  try{payload=JSON.parse(dataEl.textContent||'{}')}catch(e){return}
  const rows=payload.series||[], meta=payload.metrics||{}, groups=payload.groups||{};
  const palette=['#38bdf8','#4ade80','#fbbf24','#c084fc','#fb7185','#22d3ee'];
  const ns='http://www.w3.org/2000/svg';
  const compact=n=>{n=Number(n||0);const a=Math.abs(n);if(a>=1e9)return (n/1e9).toFixed(1).replace('.0','')+'B';if(a>=1e6)return (n/1e6).toFixed(1).replace('.0','')+'M';if(a>=1e3)return (n/1e3).toFixed(1).replace('.0','')+'K';return Math.round(n).toLocaleString()};
  const bytes=n=>{n=Number(n||0);const u=['B','KB','MB','GB','TB'];let i=0;while(n>=1024&&i<u.length-1){n/=1024;i++}return (i? n.toFixed(n>=10?1:2):Math.round(n))+' '+u[i]};
  function el(name,attrs,text){const x=document.createElementNS(ns,name);Object.entries(attrs||{}).forEach(([k,v])=>x.setAttribute(k,v));if(text!=null)x.textContent=text;return x}
  function draw(host){
    const group=host.dataset.statGroup, keys=groups[group]||[];
    host.innerHTML='';
    if(!rows.length||!keys.length){host.innerHTML='<div class="chart-empty">No data for this period.</div>';return}
    const w=Math.max(520,host.clientWidth||520), h=260, pad={l:54,r:16,t:42,b:52};
    const svg=el('svg',{viewBox:`0 0 ${w} ${h}`,role:'img','aria-label':group+' chart'});
    svg.classList.add('stat-svg');host.appendChild(svg);
    const max=Math.max(1,...rows.flatMap(r=>keys.map(k=>Number(r[k]||0))));
    const x=i=>pad.l+(rows.length<=1?0:(i*(w-pad.l-pad.r)/(rows.length-1)));
    const y=v=>pad.t+(h-pad.t-pad.b)*(1-Number(v||0)/max);
    // grid + y labels
    for(let i=0;i<=4;i++){
      const yy=pad.t+(h-pad.t-pad.b)*i/4, val=max*(1-i/4);
      svg.appendChild(el('line',{x1:pad.l,y1:yy,x2:w-pad.r,y2:yy,class:'chart-grid'}));
      svg.appendChild(el('text',{x:pad.l-8,y:yy+3,'text-anchor':'end',class:'chart-axis-label'},host.dataset.statBytes==='1'?bytes(val):compact(val)));
    }
    // x labels, sampled if dense
    const step=Math.max(1,Math.ceil(rows.length/10));
    rows.forEach((r,i)=>{if(i%step===0||i===rows.length-1){svg.appendChild(el('text',{x:x(i),y:h-20,'text-anchor':'middle',class:'chart-axis-label'},r.bucket))}});
    keys.forEach((k,ki)=>{
      const color=palette[ki%palette.length];
      const points=rows.map((r,i)=>`${x(i)},${y(r[k])}`).join(' ');
      svg.appendChild(el('polyline',{points,fill:'none',stroke:color,'stroke-width':'2.2','stroke-linejoin':'round','stroke-linecap':'round'}));
      rows.forEach((r,i)=>{
        const c=el('circle',{cx:x(i),cy:y(r[k]),r:rows.length>20?2.2:3.2,fill:color,class:'chart-point'});
        c.appendChild(el('title',{},`${r.bucket} · ${(meta[k]||{}).label||k}: ${host.dataset.statBytes==='1'?bytes(r[k]):Number(r[k]||0).toLocaleString()}`));svg.appendChild(c)
      });
    });
    // legend
    let lx=pad.l;
    keys.forEach((k,ki)=>{
      const label=(meta[k]||{}).label||k, color=palette[ki%palette.length];
      svg.appendChild(el('line',{x1:lx,y1:18,x2:lx+16,y2:18,stroke:color,'stroke-width':'3'}));
      svg.appendChild(el('text',{x:lx+21,y:21,class:'chart-legend'},label));
      lx+=Math.max(105,label.length*6.3+42);
    });
  }
  const hosts=[...document.querySelectorAll('.stat-chart')];
  const redraw=()=>hosts.forEach(draw);
  redraw();
  let timer;window.addEventListener('resize',()=>{clearTimeout(timer);timer=setTimeout(redraw,120)});
})();
