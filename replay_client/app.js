(() => {
  'use strict';
  const $=id=>document.getElementById(id);
  const data=window.REPLAY_DATA;
  const canvas=$('village'), ctx=canvas.getContext('2d');
  const colors=['#296d55','#527ead','#a45e67','#ab862f','#7d64a2','#59978f'];
  const tileSize=48;
  let engine, focus=null, players=[], animations=new Map(), flashes=new Map(), noticeUntil=0;
  const images={}, base=document.createElement('canvas');base.width=960;base.height=720;
  const bg=base.getContext('2d');
  const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');
  const formatTime=stamp=>new Date(stamp).toLocaleString('ko-KR',{timeZone:'Asia/Seoul',hour12:false});
  const shortTime=stamp=>new Date(stamp).toLocaleTimeString('ko-KR',{timeZone:'Asia/Seoul',hour12:false});
  const color=id=>colors[players.indexOf(id)%colors.length]||colors[0];
  const pad=(x,y)=>[x*tileSize,y*tileSize];
  function text(node,value){node.textContent=value;}
  function formatGap(ms){if(ms>=86400000)return `${(ms/86400000).toFixed(1)}일`;if(ms>=3600000)return `${(ms/3600000).toFixed(1)}시간`;if(ms>=60000)return `${Math.floor(ms/60000)}분`;return `${Math.floor(ms/1000)}초`;}
  function sprite(c,name,x,y,size=tileSize){if(images[name])c.drawImage(images[name],x,y,size,size);}
  function makeMap(){
    bg.imageSmoothingEnabled=false;
    for(let y=0;y<15;y++)for(let x=0;x<20;x++){
      const [px,py]=pad(x,y),path=x===2||y===2;
      bg.fillStyle=path?'#d8ca9e':(x+y)%2?'#bdd29f':'#b7cd99';bg.fillRect(px,py,tileSize,tileSize);
      sprite(bg,path?'path':'grass',px,py);
    }
    for(const [x,y] of [[5,5],[6,8],[12,4],[16,5],[16,11],[9,12]])sprite(bg,'tree',x*tileSize,y*tileSize);
    for(const [x,y] of [[7,5],[13,9]]){
      bg.fillStyle='#a9624d';bg.beginPath();bg.moveTo(x*tileSize-8,y*tileSize);bg.lineTo(x*tileSize+24,y*tileSize-32);bg.lineTo(x*tileSize+57,y*tileSize);bg.fill();
      sprite(bg,'house',x*tileSize,y*tileSize);
    }
    const x=2*tileSize,y=2*tileSize;
    bg.fillStyle='#efd57c';bg.beginPath();bg.roundRect(x+7,y+7,34,34,10);bg.fill();
    bg.fillStyle='#99a65c';bg.beginPath();bg.ellipse(x+24,y+26,10,14,0,0,Math.PI*2);bg.fill();
    bg.fillStyle='#fff3be';bg.beginPath();bg.arc(x+24,y+18,7,0,Math.PI*2);bg.fill();
    bg.font='16px "Malgun Gothic",sans-serif';bg.fillStyle='#7d7f50';bg.fillText('채집 (2, 2)',x+57,y+30);
  }
  function draw(now){
    ctx.imageSmoothingEnabled=false;ctx.clearRect(0,0,960,720);ctx.drawImage(base,0,0);
    if(!engine)return;
    if($('trails').checked){
      for(const id of players){
        if(focus!==null && id!==focus)continue;
        const trail=engine.events.slice(0,engine.index).filter(e=>e.player_id===id).slice(-16);
        ctx.strokeStyle=color(id);ctx.lineWidth=3;ctx.globalAlpha=focus===id?.7:.28;ctx.setLineDash([4,5]);ctx.beginPath();
        let prev=null;
        for(const e of trail){const px=e.x*48+24,py=e.y*48+35;
          if(prev && e.version===prev.version+1 && Math.abs(e.x-prev.x)+Math.abs(e.y-prev.y)<=1)ctx.lineTo(px,py);else ctx.moveTo(px,py);prev=e;}
        ctx.stroke();ctx.setLineDash([]);ctx.globalAlpha=1;
      }
    }
    const occupants=new Map();
    const ordered=[...engine.states.values()].sort((a,b)=>a.y-b.y||a.player_id-b.player_id);
    for(const state of ordered){
      const id=state.player_id,anim=animations.get(id);
      let x=state.x*48,y=state.y*48;
      if(anim){const fraction=Math.min(1,(now-anim.start)/anim.duration);x=(anim.x+(state.x-anim.x)*fraction)*48;y=(anim.y+(state.y-anim.y)*fraction)*48;if(fraction>=1)animations.delete(id);}
      ctx.globalAlpha=focus===null||focus===id?1:.35;
      ctx.fillStyle='#3656373b';ctx.beginPath();ctx.ellipse(x+24,y+43,18,6,0,0,Math.PI*2);ctx.fill();
      if(images.hero)sprite(ctx,'hero',x,y);else{ctx.fillStyle=color(id);ctx.fillRect(x+12,y+16,24,26);ctx.fillStyle='#ffe6b7';ctx.beginPath();ctx.arc(x+24,y+12,10,0,Math.PI*2);ctx.fill();}
      ctx.strokeStyle=color(id);ctx.lineWidth=focus===id?4:2;ctx.beginPath();ctx.roundRect(x+3,y+3,42,43,8);ctx.stroke();
      if(flashes.has(id)){
        const age=now-flashes.get(id);if(age>900)flashes.delete(id);else{ctx.fillStyle='#fff4ba';ctx.beginPath();ctx.arc(x+37,y-8-age/65,8,0,Math.PI*2);ctx.fill();ctx.font='bold 14px "Malgun Gothic",sans-serif';ctx.fillStyle='#8d662b';ctx.fillText('채집',x+48,y-5-age/65);}
      }
      const key=`${state.x},${state.y}`;
      if(!occupants.has(key))occupants.set(key,{x,y,ids:[]});occupants.get(key).ids.push(id);
      ctx.globalAlpha=1;
    }
    for(const {x,y,ids} of occupants.values()){
      if(focus!==null && !ids.includes(focus))ctx.globalAlpha=.45;
      const label=ids.map(id=>`ID ${id}`).join(' · ');
      ctx.font='bold 15px "Malgun Gothic",sans-serif';const width=ctx.measureText(label).width+16;
      const lx=Math.max(5,Math.min(955-width,x+24-width/2)),ly=Math.max(5,y-28);
      ctx.fillStyle='#fffef2ef';ctx.beginPath();ctx.roundRect(lx,ly,width,24,6);ctx.fill();ctx.fillStyle='#284432';ctx.fillText(label,lx+8,ly+17);ctx.globalAlpha=1;
    }
    if(noticeUntil && now>noticeUntil){$('gapNotice').hidden=true;noticeUntil=0;}
  }
  function updatePlayers(){
    $('players').replaceChildren();
    for(const id of players){
      const state=engine.states.get(id),button=document.createElement('button');button.className='player-card'+(focus===id?' selected':'');button.setAttribute('aria-pressed',String(focus===id));button.setAttribute('aria-label',`플레이어 ${id} 경로 강조`);button.style.setProperty('--player-color',color(id));
      const avatar=document.createElement('span');avatar.className='avatar';const img=document.createElement('img');img.src='assets/hero.png';img.alt='';avatar.append(img);
      const content=document.createElement('span'),label=document.createElement('span'),detail=document.createElement('span'),name=document.createElement('span'),tag=document.createElement('small');label.className='player-label';detail.className='player-detail';text(name,`플레이어 ${id}`);text(tag,state?'마지막 기록':'등장 전');label.append(name,tag);
      text(detail,state?`(${state.x}, ${state.y}) · 동전 ${state.coins} · v${state.version}`:'첫 행동부터 위치를 표시합니다.');content.append(label,detail);button.append(avatar,content);
      button.addEventListener('click',()=>{focus=focus===id?null:id;updatePlayers();draw(performance.now());});$('players').append(button);
    }
    $('clearFocus').hidden=focus===null;
  }
  function updateLog(){
    $('eventLog').replaceChildren();$('noMoments').hidden=engine.index>0;
    for(let i=engine.index-1;i>=Math.max(0,engine.index-5);i--){
      const e=engine.events[i],li=document.createElement('li'),button=document.createElement('button');button.className='moment';button.title=`${i+1}번째 행동으로 이동`;
      const icon=document.createElement('span'),body=document.createElement('span'),title=document.createElement('strong'),time=document.createElement('small');icon.className='moment-icon';text(icon,e.event_type==='player.gathered'?'✦':'↗');
      text(title,`ID ${e.player_id} · ${e.event_type==='player.gathered'?'채집':'이동'} (${e.x}, ${e.y})`);text(time,`${shortTime(e.event_time)} · 행동 ${i+1}`);body.append(title,time);button.append(icon,body);button.addEventListener('click',()=>seek(i+1));li.append(button);$('eventLog').append(li);
    }
  }
  function updateControls(){
    const count=engine.events.length;
    text($('eventPosition'),`${engine.index.toLocaleString()} / ${count.toLocaleString()} 행동`);$('timeline').value=engine.index;
    text($('playText'),engine.playing?'일시정지':engine.index===count&&count?'다시 재생':'재생');text($('playIcon'),engine.playing?'Ⅱ':'▶');
    text($('playStatus'),engine.playing?'재생 중':engine.index===count&&count?'재생 완료':engine.index?'일시정지':'재생 준비');
    $('play').disabled=count===0;$('first').disabled=$('prev').disabled=engine.index===0;$('last').disabled=$('next').disabled=engine.index===count;
    const current=engine.events[engine.index-1];text($('clock'),current?formatTime(current.event_time):'첫 행동 대기');
    $('startHint').hidden=engine.index>0||engine.playing;
  }
  function sync(){updatePlayers();updateLog();updateControls();draw(performance.now());}
  function seek(index){engine.seek(index);animations.clear();flashes.clear();$('gapNotice').hidden=true;noticeUntil=0;sync();}
  function changeRoom(){
    engine.room($('room').value);focus=null;animations.clear();flashes.clear();players=[...new Set(engine.events.map(e=>e.player_id))].sort((a,b)=>a-b);
    text($('roomTitle'),$('room').value);text($('roomMeta'),`${engine.events.length.toLocaleString()}개의 행동 기록`);text($('playerCount'),`${players.length}명 기록`);
    $('timeline').max=engine.events.length;$('timeline').disabled=!engine.events.length;
    text($('timeSpan'),engine.events.length?`${engine.events[0].event_time.slice(0,10)} — ${engine.events.at(-1).event_time.slice(0,10)}`:'기록 없음');
    $('gapNotice').hidden=true;sync();
  }
  function toggle(){if(!engine.events.length)return;if(engine.index===engine.events.length)seek(0);engine.playing=!engine.playing;updateControls();}
  let previous=performance.now();
  function frame(now){
    if(engine){
      const before=engine.index;
      const applied=engine.advance(Math.min(250,now-previous));
      for(const {event,old,current} of applied){
        const id=event.player_id;
        if(current?.event_id!==event.event_id)continue;
        if(old && !reduced.matches && event.version===old.version+1 && Math.abs(event.x-old.x)+Math.abs(event.y-old.y)===1)animations.set(id,{x:old.x,y:old.y,start:now,duration:Math.max(40,110/engine.speed)});
        if(event.event_type==='player.gathered')flashes.set(id,now);
      }
      if(applied.length){
        for(let i=Math.max(1,before);i<engine.index;i++){
          const gap=(engine.events[i].timestamp_us-engine.events[i-1].timestamp_us)/1000;
          if(engine.compact && gap>10000){text($('gapNotice'),`${formatGap(gap)} 대기 구간을 건너뛰었습니다`);$('gapNotice').hidden=false;noticeUntil=now+2400;}
        }
        updatePlayers();updateLog();updateControls();
      }
      draw(now);
    }
    previous=now;requestAnimationFrame(frame);
  }
  async function init(){
    if(!data || !Array.isArray(data.events))throw new Error('데이터 파일이 없습니다. replay_client의 start.cmd를 실행해 주세요.');
    await Promise.all(['grass','path','tree','house','hero'].map(name=>new Promise(resolve=>{const img=new Image();img.onload=()=>{images[name]=img;resolve();};img.onerror=resolve;img.src=`assets/${name}.png`;})));
    makeMap();engine=new window.ReplayEngine(data.events);
    for(const room of data.rooms){const option=document.createElement('option');option.value=room;text(option,room);$('room').append(option);}
    $('room').disabled=!data.rooms.length;
    if(data.rooms.includes('room-01'))$('room').value='room-01';
    text($('sourceBadge'),`${data.events.length.toLocaleString()}개 행동 · ${data.rooms.length}개 방`);
    text($('sourceInfo'),`${data.source_name} · 중복 ${data.duplicate_count}건 제외${data.ignored_count?` · 재생 대상 외 ${data.ignored_count}건 제외`:''}`);
    if(!data.events.length){text($('error'),'재생할 이동·채집 기록이 없습니다. 원본 파일을 확인해 주세요.');$('error').hidden=false;}
    $('room').addEventListener('change',changeRoom);$('play').addEventListener('click',toggle);
    $('first').addEventListener('click',()=>seek(0));$('prev').addEventListener('click',()=>seek(engine.index-1));$('next').addEventListener('click',()=>seek(engine.index+1));$('last').addEventListener('click',()=>seek(engine.events.length));
    $('timeline').addEventListener('input',()=>seek(Number($('timeline').value)));
    $('speed').addEventListener('change',()=>{engine.speed=Number($('speed').value);});
    $('skipGaps').addEventListener('change',()=>{engine.compact=$('skipGaps').checked;engine.elapsed=0;});
    $('clearFocus').addEventListener('click',()=>{focus=null;updatePlayers();});
    document.addEventListener('keydown',event=>{if(['INPUT','SELECT','BUTTON','TEXTAREA'].includes(event.target.tagName))return;if(event.code==='Space'){event.preventDefault();toggle();}if(event.code==='ArrowLeft'){event.preventDefault();seek(engine.index-1);}if(event.code==='ArrowRight'){event.preventDefault();seek(engine.index+1);}});
    document.addEventListener('visibilitychange',()=>{if(document.hidden){engine.playing=false;updateControls();}});
    changeRoom();requestAnimationFrame(frame);
  }
  init().catch(error=>{text($('error'),error.message);$('error').hidden=false;text($('sourceBadge'),'파일 확인 필요');});
})();
