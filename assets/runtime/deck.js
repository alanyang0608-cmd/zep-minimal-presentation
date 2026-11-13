(() => {
  'use strict';
  const $ = s => document.querySelector(s);
  const slides = [...document.querySelectorAll('.slide')];
  const reduce = matchMedia('(prefers-reduced-motion: reduce)');
  let current = -1, epoch = 0, animations = [], returnFocus = null, timer;
  function cancel() {
    epoch += 1;
    animations.forEach(a => a.cancel());
    animations = [];
    slides.forEach(s => s.dataset.motionState = 'idle');
  }
  function play(slide, direction = 1) {
    cancel();
    const ticket = epoch;
    const mode = slide.dataset.motion;
    $('#replay').disabled = mode === 'static' || reduce.matches;
    if (mode === 'static' || reduce.matches || !Element.prototype.animate) return;
    const add = (el, frames, delay = 0, duration = 650) => {
      const a = el.animate(frames, {duration, delay, easing:'cubic-bezier(.18,.72,.2,1)', fill:'backwards'});
      animations.push(a);
    };
    const targets = mode === 'words' ? [...slide.querySelectorAll('h1 .line,.subhead')]
      : [...slide.querySelectorAll('.animate-item')];
    targets.forEach((el, i) => {
      const move = mode === 'words' || mode === 'timeline' ? `translateX(${direction * 38}px)` : 'translateY(18px)';
      const frames = mode === 'metrics' ? [{opacity:0,transform:'translateY(22px)'},{opacity:1,transform:'translateY(-3px)',offset:.72},{opacity:1,transform:'none'}]
        : [{opacity:0,transform:move},{opacity:1,transform:'none'}];
      add(el, frames, i * Math.min(90, 450 / Math.max(targets.length,1)));
    });
    if (slide.querySelector('.ratio-value')) add(slide.querySelector('.ratio-value'), [{opacity:0,transform:'translateY(15px)'},{opacity:1,transform:'none'}]);
    slide.querySelectorAll('.matrix-dot').forEach((dot,i)=>add(dot,[{opacity:0,transform:'translateY(6px)'},{opacity:1,transform:'none'}],100+i*5,400));
    slide.querySelectorAll('.ratio-fill').forEach(el=>add(el,[{clipPath:'inset(0 100% 0 0)'},{clipPath:'inset(0 0 0 0)'}],100,800));
    if (mode === 'draw') slide.querySelectorAll('.chart-line').forEach(path => {
      const length=path.getTotalLength();
      add(path,[{strokeDasharray:`${length} ${length}`,strokeDashoffset:length},{strokeDasharray:`${length} ${length}`,strokeDashoffset:0}],0,1000);
    });
    if (!animations.length) return;
    slide.dataset.motionState = 'running';
    Promise.allSettled(animations.map(a => a.finished)).then(() => {
      if (ticket !== epoch) return;
      animations.forEach(a=>a.cancel()); animations=[];
      slide.dataset.motionState='idle';
    });
  }
  function navigate(index, direction = 1) {
    index=Math.max(0,Math.min(slides.length-1,index));
    if(index===current)return;
    cancel(); current=index;
    slides.forEach((s,i)=>s.hidden=i!==current);
    $('#counter').textContent=`${String(current+1).padStart(2,'0')} / ${String(slides.length).padStart(2,'0')}`;
    $('#prev').disabled=current===0; $('#next').disabled=current===slides.length-1;
    $('#progress').style.width=`${(current+1)/slides.length*100}%`;
    $('#stage').scrollTop=0;
    const hash=`#${current+1}`;
    if(location.hash!==hash)location.hash=hash;
    play(slides[current],direction);
  }
  function open(dialog) { returnFocus=document.activeElement; dialog.showModal(); }
  function close(dialog) {dialog.close();if(returnFocus?.isConnected)returnFocus.focus();}
  function notes() {$('#notes-body').innerHTML=slides[current].querySelector('.notes-template').innerHTML;open($('#notes'));}
  function toast(message){clearTimeout(timer);$('#toast').textContent=message;$('#toast').hidden=false;timer=setTimeout(()=>$('#toast').hidden=true,4000);}
  async function fullscreen(){try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}catch{toast('请使用浏览器全屏功能 / Use browser fullscreen.');}}
  $('#prev').onclick=()=>navigate(current-1,-1);$('#next').onclick=()=>navigate(current+1,1);
  $('#replay').onclick=()=>play(slides[current]);$('#overview-open').onclick=()=>open($('#overview'));
  $('#notes-open').onclick=notes;$('#fullscreen').onclick=fullscreen;
  document.querySelectorAll('[data-go]').forEach(button=>button.onclick=()=>{const dialog=button.closest('dialog');if(dialog)close(dialog);navigate(Number(button.dataset.go));$('#stage').focus({preventScroll:true});});
  document.querySelectorAll('[data-close]').forEach(button=>button.onclick=()=>close(button.closest('dialog')));
  document.querySelectorAll('dialog').forEach(dialog=>dialog.addEventListener('cancel',()=>{if(returnFocus?.isConnected)returnFocus.focus();}));
  document.addEventListener('keydown',event=>{
    if(event.ctrlKey||event.metaKey||event.altKey||event.isComposing||event.target.isContentEditable||event.target.closest('input,textarea,select,video,dialog[open]'))return;
    if(document.querySelector('dialog[open]'))return;
    if(event.key===' '&&event.target.closest('button,a'))return;
    const key=event.key.toLowerCase();
    if(['arrowright','arrowdown','pagedown',' '].includes(key)){event.preventDefault();navigate(current+1,1);}
    else if(['arrowleft','arrowup','pageup'].includes(key)){event.preventDefault();navigate(current-1,-1);}
    else if(key==='home'){event.preventDefault();navigate(0,-1);}
    else if(key==='end'){event.preventDefault();navigate(slides.length-1,1);}
    else if(key==='r'&&!$('#replay').disabled)play(slides[current]);
    else if(key==='o')open($('#overview'));else if(key==='n')notes();else if(key==='f')fullscreen();
  });
  const fromHash=()=>{const n=Number(location.hash.slice(1));navigate(Number.isInteger(n)&&n>0?n-1:0);};
  addEventListener('hashchange',fromHash);
  reduce.addEventListener('change',()=>{cancel();$('#replay').disabled=reduce.matches||slides[current].dataset.motion==='static';});
  addEventListener('beforeprint',cancel);
  fromHash();
})();
