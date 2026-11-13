// Read-only: run as a function through your browser tool, after motion reaches idle.
() => {
  const slide = document.querySelector('.slide:not([hidden])');
  if (!slide) return {error:'No active slide'};
  const rect = slide.getBoundingClientRect();
  const footer = slide.querySelector('.slide-foot').getBoundingClientRect();
  const elements = [...slide.querySelectorAll('h1,h2,h3,p,.metric-value,.ratio-value,.time-label,.media,.dot-matrix,.items,.chapter-index,.chapter-title')];
  const overflow = elements.filter(el=>{
    if (el.closest('.chart-wrap')) return false;
    const r=el.getBoundingClientRect();
    return r.width>0 && r.height>0 && (r.left<rect.left-1 || r.right>rect.right+1 || r.bottom>footer.top-5);
  }).map(el=>({tag:el.tagName,class:el.className,text:el.textContent.slice(0,100)}));
  return {
    slide:Number(slide.dataset.index)+1,
    viewport:{width:innerWidth,height:innerHeight},
    rect:{x:rect.x,y:rect.y,width:rect.width,height:rect.height},
    motion:slide.dataset.motion,state:slide.dataset.motionState,overflow,
    pageOverflow:document.documentElement.scrollWidth>innerWidth,
    images:[...slide.querySelectorAll('img')].map(img=>({alt:img.alt,loaded:img.complete&&img.naturalWidth>0}))
  };
}
