function renderBarChart(canvas, items){
  try{
    const labels = items.map(i=>i.word||i[0]);
    const values = items.map(i=>i.count||i[1]);
    const ctx = canvas.getContext('2d');
    if(canvas._chart){ canvas._chart.destroy(); }
    canvas._chart = new Chart(ctx, {
      type: 'bar',
      data: { labels, datasets: [{ label: 'Top words', data: values, backgroundColor: 'rgba(91,79,230,0.9)' }] },
      options: { responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}} }
    });
  }catch(e){ console.warn('chart render failed', e); }
}

function renderGraph(container, nodes, edges, mode='structural', anchorId=null){
  // clear
  container.innerHTML = '';
  const width = container.clientWidth || 400;
  const height = container.clientHeight || 240;
  const svg = d3.select(container).append('svg').attr('width', '100%').attr('height', height).attr('viewBox', `0 0 ${width} ${height}`);

  // compute degree map
  const degree = {};
  nodes.forEach(n=>degree[n.id]=0);
  edges.forEach(e=>{ degree[e.source] = (degree[e.source]||0)+1; degree[e.target] = (degree[e.target]||0)+1; });

  // mode adjustments
  let displayNodes = nodes.slice();
  let displayEdges = edges.slice();

  if(mode==='ego'){
    // pick anchor: provided or highest-degree
    let anchor = anchorId || (nodes.slice().sort((a,b)=> (degree[b.id]||0)-(degree[a.id]||0))[0] && nodes.slice().sort((a,b)=> (degree[b.id]||0)-(degree[a.id]||0))[0].id);
    if(anchor){
      const neighborSet = new Set();
      displayEdges = edges.filter(e=>{ if(e.source===anchor){ neighborSet.add(e.target); return true } if(e.target===anchor){ neighborSet.add(e.source); return true } return false });
      displayNodes = nodes.filter(n=> n.id===anchor || neighborSet.has(n.id));
    }
  }

  // semantic grouping by first letter
  const groups = {};
  nodes.forEach(n=>{ const k=(n.label||n.id||'').toString().trim().slice(0,1).toLowerCase()||'#'; groups[k]=groups[k]||[]; groups[k].push(n.id); });

  // color scales
  const color = d3.scaleOrdinal(d3.schemeTableau10);
  const heat = d3.scaleLinear().domain([0, d3.max(Object.values(degree)||[1])||1]).range(['#ffd9d9','#e22b2b']);

  const sim = d3.forceSimulation()
    .force('link', d3.forceLink().id(d=>d.id).distance(40).strength(0.6))
    .force('charge', d3.forceManyBody().strength(-120))
    .force('center', d3.forceCenter(width/2, height/2));

  const link = svg.append('g').attr('stroke', '#999').attr('stroke-opacity', 0.6)
    .selectAll('line').data(displayEdges).enter().append('line').attr('stroke-width', d=>Math.sqrt(d.weight||1));

  const node = svg.append('g').attr('stroke', '#fff').attr('stroke-width', 1.2)
    .selectAll('g').data(displayNodes).enter().append('g').call(d3.drag()
      .on('start', (event,d)=>{ if(!event.active) sim.alphaTarget(0.3).restart(); d.fx=d.x; d.fy=d.y; })
      .on('drag', (event,d)=>{ d.fx=event.x; d.fy=event.y; })
      .on('end', (event,d)=>{ if(!event.active) sim.alphaTarget(0); d.fx=null; d.fy=null; }));

  node.append('circle').attr('r', d=>{
    const base = Math.max(4, d.size||6);
    if(mode==='structural') return Math.max(4, (degree[d.id]||0)+4);
    if(mode==='heatmap') return base+2;
    if(mode==='semantic') return base+2;
    return base;
  }).attr('fill', d=>{
    if(mode==='heatmap') return heat(degree[d.id]||0);
    if(mode==='semantic') return color((d.label||d.id||'').toString().trim().slice(0,1).toLowerCase());
    return '#5b4fe6';
  });

  node.append('text').text(d=>d.label).attr('x',8).attr('y',4).style('font-size','11px').style('fill','#222');

  sim.nodes(displayNodes).on('tick', ()=>{
    link.attr('x1', d=> (d.source.x||d.source[0]) )
        .attr('y1', d=> (d.source.y||d.source[1]) )
        .attr('x2', d=> (d.target.x||d.target[0]) )
        .attr('y2', d=> (d.target.y||d.target[1]) );
    node.attr('transform', d=>`translate(${d.x},${d.y})`);
  });
  // bind edges to simulation
  sim.force('link').links(displayEdges);
}
