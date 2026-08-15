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

function renderGraph(container, nodes, edges){
  // clear
  container.innerHTML = '';
  const width = container.clientWidth || 400;
  const height = container.clientHeight || 240;
  const svg = d3.select(container).append('svg').attr('width', '100%').attr('height', height).attr('viewBox', `0 0 ${width} ${height}`);

  const sim = d3.forceSimulation()
    .force('link', d3.forceLink().id(d=>d.id).distance(40).strength(0.6))
    .force('charge', d3.forceManyBody().strength(-120))
    .force('center', d3.forceCenter(width/2, height/2));

  const link = svg.append('g').attr('stroke', '#999').attr('stroke-opacity', 0.6)
    .selectAll('line').data(edges).enter().append('line').attr('stroke-width', d=>Math.sqrt(d.weight||1));

  const node = svg.append('g').attr('stroke', '#fff').attr('stroke-width', 1.2)
    .selectAll('circle').data(nodes).enter().append('g');

  node.append('circle').attr('r', d=>Math.max(4, d.size||6)).attr('fill', '#5b4fe6');
  node.append('text').text(d=>d.label).attr('x',8).attr('y',4).style('font-size','11px').style('fill','#222');

  sim.nodes(nodes).on('tick', ()=>{
    link.attr('x1', d=>d.source.x)
        .attr('y1', d=>d.source.y)
        .attr('x2', d=>d.target.x)
        .attr('y2', d=>d.target.y);
    node.attr('transform', d=>`translate(${d.x},${d.y})`);
  });
  sim.force('link').links(edges);
}
