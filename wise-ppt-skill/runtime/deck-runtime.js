(function(global){
'use strict';
var root=document.documentElement,query=new URLSearchParams(global.location.search);
if(query.has('accent'))root.classList.add('accent');
if(query.get('print')==='1')root.classList.add('print-mode');
var tasks=new WeakMap();
var registeredTasks=new WeakMap();
function slides(){return Array.prototype.slice.call(document.querySelectorAll('#track>.slide'))}
function updateDeckReady(){
  var all=slides(),failed=all.some(function(slide){return slide.dataset.renderError}),ready=all.length>0&&all.every(function(slide){return slide.dataset.renderReady==='true'});
  document.documentElement.dataset.deckReady=ready&&!failed?'true':'false';
  if(failed)document.documentElement.dataset.deckError='true';else delete document.documentElement.dataset.deckError;
  if(ready&&!failed)document.dispatchEvent(new CustomEvent('wise-ppt:ready'));
  return ready&&!failed;
}
function markSlideError(slide,error){if(!slide)return;slide.dataset.renderError=error&&error.message?error.message:String(error||'unknown error');delete slide.dataset.renderReady;updateDeckReady()}
function registerSlideTask(slide,task){
  if(!slide||!slide.classList.contains('slide'))throw new Error('registerSlideTask 需要 .slide 节点');
  var items=registeredTasks.get(slide)||[];items.push(Promise.resolve(task));registeredTasks.set(slide,items);slide.dataset.renderPending='true';return task;
}
function emphasisColor(slide,contentRef,role,fallback){
  if(!slide||!root.classList.contains('accent'))return fallback;
  var roles=(slide.dataset.emphasisRoles||'').split(/\s+/).filter(Boolean);
  if(slide.dataset.emphasisMode!=='semantic-focus'||slide.dataset.emphasisRef!==contentRef||!roles.includes(role))return fallback;
  var color=getComputedStyle(root).getPropertyValue('--accent-red').trim();
  if(!color)throw new Error('主题缺少 --accent-red token');
  return color;
}
function markSlideReady(slide){
  if(!slide||!slide.classList.contains('slide'))throw new Error('markSlideReady 需要 .slide 节点');
  if(tasks.has(slide))return tasks.get(slide);
  var task=Promise.resolve().then(function(){
    var fonts=document.fonts&&document.fonts.ready?document.fonts.ready:Promise.resolve();
    var images=Array.prototype.map.call(slide.querySelectorAll('img'),function(img){
      if(img.complete&&img.naturalWidth>0)return Promise.resolve();
      return new Promise(function(resolve,reject){img.addEventListener('load',resolve,{once:true});img.addEventListener('error',function(){reject(new Error('图片加载失败: '+(img.currentSrc||img.src)))},{once:true})});
    });
    return Promise.all([fonts].concat(images,registeredTasks.get(slide)||[]));
  }).then(function(){slide.getBoundingClientRect();slide.dataset.renderReady='true';delete slide.dataset.renderPending;delete slide.dataset.renderError;updateDeckReady();return slide}).catch(function(error){markSlideError(slide,error);throw error});
  tasks.set(slide,task);return task;
}
function createEChart(slide,target,option){
  var rejectRender;
  try{
    if(!global.echarts)throw new Error('ECharts 未加载');var element=typeof target==='string'?slide.querySelector(target):target;if(!element)throw new Error('找不到 ECharts 容器');var chart=global.echarts.init(element,null,{renderer:'svg'}),settled=false;
    var rendered=new Promise(function(resolve,reject){var timer=setTimeout(function(){if(!settled){settled=true;reject(new Error('ECharts 渲染超时'))}},8000);rejectRender=function(error){if(!settled){settled=true;clearTimeout(timer);reject(error)}};chart.on('finished',function(){if(!settled){settled=true;clearTimeout(timer);resolve(chart)}})});
    registerSlideTask(slide,rendered);markSlideReady(slide);chart.setOption(option);return chart;
  }
  catch(error){if(rejectRender)rejectRender(error);markSlideError(slide,error);throw error}
}
global.WisePPT={markSlideReady:markSlideReady,markSlideError:markSlideError,registerSlideTask:registerSlideTask,createEChart:createEChart,emphasisColor:emphasisColor,updateDeckReady:updateDeckReady};

function initialize(){
  var body=document.body,track=document.getElementById('track'),board=document.getElementById('board-sections'),pager=document.getElementById('pager'),deckStage=document.getElementById('deck-stage'),current=0,touchStartX=null;
  if(!track||!board||!deckStage)return;
  function allSlides(){return Array.prototype.slice.call(track.querySelectorAll(':scope>.slide'))}
  function clamp(number){return Math.max(0,Math.min(allSlides().length-1,number))}
  function copyCanvasPixels(original,clone){
    var originals=original.querySelectorAll('canvas'),clones=clone.querySelectorAll('canvas');
    originals.forEach(function(canvas,index){var target=clones[index];if(!target)return;target.width=canvas.width;target.height=canvas.height;try{target.getContext('2d').drawImage(canvas,0,0);target.dataset.canvasCopied='true'}catch(error){target.dataset.canvasCopied='error'}});
  }
  function cloneSlide(slide){var clone=slide.cloneNode(true);clone.querySelectorAll('script').forEach(function(script){script.remove()});clone.removeAttribute('id');clone.querySelectorAll('[id]').forEach(function(node){node.removeAttribute('id')});clone.classList.add('board-clone');clone.setAttribute('aria-hidden','true');clone.inert=true;copyCanvasPixels(slide,clone);return clone}
  function makeCard(slide,index){var card=document.createElement('button');card.type='button';card.className='board-card';card.dataset.index=String(index);var preview=document.createElement('div');preview.className='board-preview';preview.appendChild(cloneSlide(slide));var title=document.createElement('div');title.className='board-title';title.textContent='S'+String(index+1).padStart(2,'0')+' · '+slide.dataset.pageTitle;var summary=document.createElement('div');summary.className='board-summary';summary.textContent=slide.dataset.pageSummary;card.append(preview,title,summary);card.addEventListener('click',function(){enterDeck(index)});return card}
  function syncScales(){board.querySelectorAll('.board-preview').forEach(function(preview){preview.style.setProperty('--board-scale',String(preview.clientWidth/1920))})}
  function rebuildBoard(){
    board.replaceChildren();var groups=new Map();
    allSlides().forEach(function(slide,index){var key=slide.dataset.sectionId||'section.default';if(!groups.has(key))groups.set(key,{title:slide.dataset.sectionTitle||'',items:[]});groups.get(key).items.push([slide,index])});
    groups.forEach(function(group){var label=document.createElement('div');label.className='section-label';label.textContent=group.title;var grid=document.createElement('div');grid.className='board-grid';group.items.forEach(function(item){grid.appendChild(makeCard(item[0],item[1]))});board.append(label,grid)});
    var deckTitle=document.getElementById('deck-title'),subtitle=document.getElementById('deck-subtitle');if(deckTitle)deckTitle.textContent=root.dataset.deckTitle||document.title;if(subtitle)subtitle.textContent=allSlides().length+' SLIDES · 点击任意页面进入横向放映';var active=board.querySelector('[data-index="'+current+'"]');if(active)active.classList.add('active');syncScales();requestAnimationFrame(syncScales);
  }
  function fit(){deckStage.style.transform='scale('+Math.min(innerWidth/1920,innerHeight/1080)+')'}
  function go(index,updateHash){current=clamp(index);track.style.transform='translate3d('+(-current*1920)+'px,0,0)';if(pager)pager.textContent=(current+1)+' / '+allSlides().length;if(updateHash!==false)history.replaceState(null,'','#'+(current+1))}
  function enterDeck(index,updateHash){body.className='mode-deck';fit();go(index,updateHash);scrollTo(0,0)}
  function exitDeck(){body.className='mode-board';history.replaceState(null,'',location.pathname+location.search);rebuildBoard();var card=board.querySelector('[data-index="'+current+'"]');if(card)card.scrollIntoView({block:'center'})}
  function fromHash(){var match=location.hash.match(/^#(\d+)$/);if(match)enterDeck(Number(match[1])-1,false);else if(!root.classList.contains('print-mode')){body.className='mode-board';rebuildBoard()}}
  function selfTest(){
    try{rebuildBoard();var all=allSlides(),cards=board.querySelectorAll('.board-card');if(cards.length!==all.length)throw new Error('画册卡片数量不一致');var canvasCount=track.querySelectorAll('canvas').length,copied=board.querySelectorAll('canvas[data-canvas-copied="true"]').length;if(copied!==canvasCount)throw new Error('Canvas 克隆像素未完整复制');if(query.has('accent')!==root.classList.contains('accent'))throw new Error('强调模式未按 URL 激活');all.filter(function(slide){return slide.dataset.emphasisMode==='semantic-focus'}).forEach(function(slide){var target=slide.querySelector('[data-emphasis-role]');if(!target)throw new Error('semantic-focus 页面缺少强调载体');var style=getComputedStyle(target),red='rgb(192, 57, 43)',isRed=style.color===red||style.borderColor===red||style.outlineColor===red;if(query.has('accent')&&!isRed)throw new Error('强调载体没有应用主题强调色');if(!query.has('accent')&&isRed)throw new Error('默认模式残留主题强调色')});history.replaceState(null,'','#'+all.length);fromHash();if(!body.classList.contains('mode-deck'))throw new Error('深链未进入放映');if(all.length>1)go(0,false);exitDeck();if(!body.classList.contains('mode-board')||location.hash)throw new Error('ESC 状态切换失败');if(document.fonts&&document.fonts.status!=='loaded')throw new Error('字体尚未加载完成');root.dataset.runtimeCheck='pass'}catch(error){root.dataset.runtimeCheck='fail';root.dataset.runtimeCheckError=error.message;console.error(error)}
  }
  addEventListener('resize',function(){fit();if(body.classList.contains('mode-board'))rebuildBoard()});addEventListener('hashchange',fromHash);
  addEventListener('keydown',function(event){if(!body.classList.contains('mode-deck'))return;if(['ArrowRight','ArrowDown',' ','PageDown'].includes(event.key)){event.preventDefault();go(current+1)}else if(['ArrowLeft','ArrowUp','PageUp'].includes(event.key)){event.preventDefault();go(current-1)}else if(event.key==='Home'){event.preventDefault();go(0)}else if(event.key==='End'){event.preventDefault();go(allSlides().length-1)}else if(event.key==='Escape'){event.preventDefault();exitDeck()}});
  var toggle=document.getElementById('board-toggle'),deck=document.getElementById('deck');if(toggle)toggle.addEventListener('click',exitDeck);if(deck){deck.addEventListener('touchstart',function(event){touchStartX=event.changedTouches[0].clientX},{passive:true});deck.addEventListener('touchend',function(event){if(touchStartX===null)return;var delta=event.changedTouches[0].clientX-touchStartX;if(Math.abs(delta)>48)go(current+(delta<0?1:-1));touchStartX=null},{passive:true})}
  document.addEventListener('wise-ppt:ready',function(){if(!root.classList.contains('print-mode'))rebuildBoard();if(query.get('selftest')==='1')selfTest()},{once:true});
  allSlides().forEach(function(slide){if(slide.dataset.renderPending!=='true'&&slide.dataset.renderReady!=='true')markSlideReady(slide)});updateDeckReady();fit();fromHash();global.WisePPTRuntime={rebuildBoard:rebuildBoard,enterDeck:enterDeck,exitDeck:exitDeck,go:go};
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',initialize,{once:true});else initialize();
})(window);
