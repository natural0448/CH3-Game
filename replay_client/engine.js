(function(root){
  'use strict';
  class ReplayEngine {
    constructor(events){ this.all=events; this.events=[]; this.states=new Map(); this.index=0; this.elapsed=0; this.playing=false; this.speed=1; this.compact=true; }
    room(name){this.events=this.all.filter(e=>e.room_id===name);this.seek(0);}
    delay(){
      if(this.index===0)return 400;
      if(this.index>=this.events.length)return 0;
      const gap=(this.events[this.index].timestamp_us-this.events[this.index-1].timestamp_us)/1000;
      return this.compact?Math.max(120,Math.min(1200,gap)):Math.max(1,gap);
    }
    apply(event){
      const previous=this.states.get(event.player_id);
      // Do not let an old re-delivery roll back a newer authoritative version.
      if(previous && event.version<=previous.version)return;
      this.states.set(event.player_id,{...event});
    }
    seek(index){
      this.index=Math.max(0,Math.min(this.events.length,Math.floor(index)));
      this.playing=false;this.elapsed=0;this.states=new Map();
      for(let i=0;i<this.index;i++)this.apply(this.events[i]);
    }
    advance(delta){
      const applied=[];
      if(!this.playing)return applied;
      this.elapsed+=Math.max(0,delta)*this.speed;
      while(this.index<this.events.length && this.elapsed>=this.delay()){
        this.elapsed-=this.delay();
        const event=this.events[this.index++];
        const old=this.states.get(event.player_id);
        this.apply(event);
        applied.push({event,old,current:this.states.get(event.player_id)});
      }
      if(this.index===this.events.length){this.playing=false;this.elapsed=0;}
      return applied;
    }
  }
  root.ReplayEngine=ReplayEngine;
  if(typeof module!=='undefined')module.exports={ReplayEngine};
})(typeof window!=='undefined'?window:globalThis);
