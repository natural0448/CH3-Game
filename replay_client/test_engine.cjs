const assert=require('node:assert/strict');
const {ReplayEngine}=require('./engine.js');
const events=[
  {event_id:'a',room_id:'A',player_id:1,x:1,y:0,coins:0,version:1,timestamp_us:0},
  {event_id:'b',room_id:'A',player_id:2,x:2,y:2,coins:3,version:4,timestamp_us:1_000_000},
  {event_id:'c',room_id:'A',player_id:1,x:2,y:0,coins:0,version:2,timestamp_us:86400_000_000},
  {event_id:'d',room_id:'B',player_id:3,x:9,y:2,coins:1,version:1,timestamp_us:86401_000_000},
  {event_id:'e',room_id:'A',player_id:1,x:0,y:0,coins:0,version:1,timestamp_us:86402_000_000},
];
const engine=new ReplayEngine(events);engine.room('A');
assert.equal(engine.states.size,0);
engine.playing=true;engine.advance(400);assert.equal(engine.index,1);assert.equal(engine.states.get(1).x,1);
engine.seek(3);assert.equal(engine.states.get(1).x,2);assert.equal(engine.states.get(2).coins,3);
engine.seek(1);assert.equal(engine.states.get(1).x,1);assert.equal(engine.states.has(2),false);
engine.seek(4);assert.equal(engine.states.get(1).version,2);
engine.room('B');assert.equal(engine.events.length,1);assert.equal(engine.states.size,0);
engine.playing=true;engine.advance(500);assert.equal(engine.playing,false);assert.equal(engine.states.get(3).x,9);
engine.room('A');engine.seek(2);assert.equal(engine.delay(),1200);engine.compact=false;assert.equal(engine.delay(),86399_000);
engine.seek(0);engine.speed=2;engine.playing=true;engine.advance(200);assert.equal(engine.index,1);
engine.playing=false;engine.advance(9999);assert.equal(engine.index,1);
engine.room('empty');assert.equal(engine.events.length,0);engine.playing=true;engine.advance(100);assert.equal(engine.playing,false);
console.log('PASS: seek/rewind, room isolation, coins, version guard, gaps, speed, pause and end.');
