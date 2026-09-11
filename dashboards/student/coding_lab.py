"""LangGraph-powered adaptive Python Coding Lab."""
from __future__ import annotations

import json
import base64
import html
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, TypedDict
from urllib.parse import quote_plus
from uuid import uuid4

import streamlit as st
import streamlit.components.v1 as components
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph

from ai.config import get_groq_api_key, get_groq_model
from ai.pyquest_events import outcome_events, validated_events
from database.connection import get_connection


JOURNEY_WORLDS = [
    ("Input & Output", "Airport Boarding", "Learn to receive and display information."),
    ("Variables", "Shopping Cart", "Store and update useful values."),
    ("Conditions", "Castle Gate", "Make decisions using if, elif, and else."),
    ("Loops", "Fuel Station", "Repeat a useful action safely."),
    ("Lists", "Treasure Chest", "Collect and organize items."),
    ("Functions", "Robot Repair", "Build reusable helpers."),
    ("OOP", "AI Lab", "Model objects and their behaviour."),
    ("Advanced Python", "Cyber Lock", "Combine ideas to solve larger missions."),
]

BEGINNER_STAGES = [
    ("Input & Output", "Shopping Cart", "Welcome a shopper by printing one short message."),
    ("Variables", "Shopping Cart", "Put one item name or price into a variable, then print it."),
    ("Input", "Airport Boarding", "Ask for one value with input(), then print a friendly response."),
    ("Conditions", "Castle Gate", "Use one simple if statement with one comparison."),
    ("Loops", "Fuel Station", "Repeat one short action with a small range()."),
]

PYQUEST_STAGES = [
    {"key": "print", "title": "Python Village · First Words", "concept": "print()", "scenario": "SHOPPING_CART", "world": "Shopping Cart", "need": 3},
    {"key": "input", "title": "Airport Check-in · Taking Input", "concept": "input()", "scenario": "LOCKED_DOOR", "world": "Locked Door", "need": 3},
    {"key": "variables", "title": "Mall Mission · Variables", "concept": "variables", "scenario": "FUEL_STATION", "world": "Fuel Station", "need": 3},
    {"key": "conditions", "title": "Castle Kingdom · Conditions", "concept": "if / else", "scenario": "CASTLE_GATE", "world": "Castle Gate", "need": 3},
    {"key": "loops", "title": "Loop Forest · Repetition", "concept": "for loops", "scenario": "TREASURE_COLLECTION", "world": "Treasure Collection", "need": 3},
    {"key": "functions", "title": "Function Factory · Reuse", "concept": "functions", "scenario": "ROBOT_REPAIR", "world": "Robot Repair", "need": 3},
]

SCENARIO_ART = {
    "Shopping Cart": "shopping-cart-quest.png",
    "Fuel Station": "fuel-station-quest.svg",
    "Castle Gate": "castle-gate-quest.png",
}


def _scenario_for(concept: str, level: str, completed: int) -> dict[str, str]:
    """Map a generated Python concept to a reusable story world."""
    text = concept.lower()
    matches = [
        (("nested loop",), "Multi-room Castle", "Explore rooms using a loop inside a loop."),
        (("loop", "range", "while", "iterate"), "Fuel Station", "Keep the station running one customer at a time."),
        (("condition", "if", "boolean", "comparison", "logical"), "Castle Gate", "Open the gate only when its rules are satisfied."),
        (("list", "tuple", "dictionary", "dict", "collection"), "Treasure Chest", "Organize the treasures you discover."),
        (("function", "parameter", "return"), "Robot Repair", "Teach a repair robot one reusable skill."),
        (("class", "object", "inheritance", "oop"), "AI Lab", "Program a helpful AI lab device."),
        (("input", "print", "string", "variable", "number"), "Airport Boarding", "Help travellers through a simple check-in."),
    ]
    for keywords, name, story in matches:
        if any(keyword in text for keyword in keywords):
            return {"name": name, "story": story, "difficulty": level, "stage": str(completed + 1)}
    return {"name": "Forest Path", "story": "Choose the next safe step on the learning trail.", "difficulty": level, "stage": str(completed + 1)}


def _next_scenario(level: str, completed: int) -> dict[str, str]:
    """Choose the next reusable world from durable learner progress."""
    if level == "Beginner":
        concept, name, story = BEGINNER_STAGES[min(len(BEGINNER_STAGES) - 1, completed)]
        return {"name": name, "story": story, "concept_focus": concept, "difficulty": level, "stage": str(completed + 1)}
    concept, name, story = JOURNEY_WORLDS[min(len(JOURNEY_WORLDS) - 1, completed // 3)]
    return {"name": name, "story": story, "concept_focus": concept, "difficulty": level, "stage": str(completed + 1)}


def _render_scenario_art(scenario: dict[str, str]) -> None:
    """Show actual quest artwork where an asset exists, not only a text label."""
    filename = SCENARIO_ART.get(scenario.get("name", ""))
    if not filename:
        return
    image_path = Path(__file__).resolve().parents[2] / "assets" / filename
    if image_path.exists():
        st.image(str(image_path), caption="Mission scene · {}".format(scenario["name"]), use_container_width=True)


def _render_game_hud(completed: int, coins: int) -> None:
    """Render the original Python Quest HUD above the playable map."""
    level = max(1, completed // 6 + 1)
    xp = min(100, (completed % 6) * 16 + 8)
    st.markdown(
        f"""<style>
        .pyquest-hud {{background:linear-gradient(115deg,#042c5a,#075e9b 55%,#073d70);border:2px solid #50cfff;border-radius:22px;padding:1rem 1.25rem;color:#fff;box-shadow:0 10px 22px #001c3a55;margin:.2rem 0 .8rem}}
        .pyquest-title {{font-size:1.65rem;font-weight:900;letter-spacing:.04em;color:#ffd44d;text-shadow:2px 2px #092148}} .pyquest-tag {{font-size:.82rem;color:#c9efff}}
        .hud-stat {{background:#082244;border:1px solid #3fc7ff;border-radius:14px;padding:.45rem .75rem;font-weight:800;text-align:center;color:#fff}} .hud-stat b {{color:#ffd548;font-size:1.15rem}}
        .xp-track {{height:9px;background:#081f3b;border-radius:8px;overflow:hidden;margin-top:.35rem}} .xp-fill {{height:100%;width:{xp}%;background:linear-gradient(90deg,#9cf52f,#ffe34a);border-radius:8px}}
        </style><div class='pyquest-hud'><div style='display:flex;justify-content:space-between;align-items:center;gap:1rem;flex-wrap:wrap'><div><div class='pyquest-title'>🐍 PYQUEST</div><div class='pyquest-tag'>Code. Solve. Level Up.</div></div><div style='min-width:210px'><b>Level {level}</b> · {completed} verified quests<div class='xp-track'><div class='xp-fill'></div></div><small>{xp}/100 XP to the next level</small></div><div style='display:flex;gap:.5rem'><div class='hud-stat'>🪙 <b>{coins}</b><br><small>coins</small></div><div class='hud-stat'>⚡ <b>5/5</b><br><small>focus</small></div></div></div></div>""",
        unsafe_allow_html=True,
    )


def _render_journey(completed: int) -> None:
    """Render an illustrated map with interactive-looking, progress-aware worlds."""
    unlocked = min(len(JOURNEY_WORLDS), completed // 3 + 1)
    cards = []
    for index, (concept, world, description) in enumerate(JOURNEY_WORLDS):
        status = "unlocked" if index < unlocked else "locked"
        icon = "✅" if index < unlocked - 1 else ("🗺️" if status == "unlocked" else "🔒")
        cards.append(f"<div class='quest-world {status}'><div class='quest-icon'>{icon}</div><strong>{index + 1}. {concept}</strong><span>{world}</span><small>{description}</small></div>")
    map_path = Path(__file__).resolve().parents[2] / "assets" / "python-quest-map.png"
    backdrop = ""
    if map_path.exists():
        backdrop = "data:image/png;base64," + base64.b64encode(map_path.read_bytes()).decode("ascii")
    st.markdown(
        """<style>
        .quest-map-shell {background-image:linear-gradient(#00376633,#00376633),url('""" + backdrop + """');background-size:cover;background-position:center;border-radius:22px;min-height:350px;padding:1rem;box-shadow:inset 0 0 0 2px #5ee4ff,0 12px 22px #02234b66;display:flex;align-items:flex-end}
        .quest-map {display:grid;grid-template-columns:repeat(4,minmax(130px,1fr));gap:.7rem;width:100%;}.quest-world {min-height:90px;padding:.6rem;border-radius:14px;display:flex;flex-direction:column;gap:.1rem;border:2px solid #9ceaff;background:linear-gradient(160deg,#074579ee,#032851ee);color:#fff;box-shadow:0 5px 10px #001e42aa;text-shadow:1px 1px #001b38}.quest-world.unlocked:hover{transform:translateY(-3px);border-color:#ffe95a}.quest-world.locked{filter:saturate(.1);opacity:.76;background:#20384ddd}.quest-world span{color:#ffe769;font-size:.76rem;font-weight:800}.quest-world small{color:#d7f4ff;font-size:.67rem;line-height:1.15}.quest-icon{font-size:1rem}@media(max-width:800px){.quest-map{grid-template-columns:repeat(2,minmax(120px,1fr))}.quest-map-shell{min-height:440px}}
        </style><div class='quest-map-shell'><div class='quest-map'>""" + "".join(cards) + "</div></div>",
        unsafe_allow_html=True,
    )


def _asset_data(filename: str) -> str:
    path = Path(__file__).resolve().parents[2] / "assets" / filename
    if not path.exists():
        return ""
    mime = "image/svg+xml" if path.suffix.lower() == ".svg" else "image/png"
    return "data:{};base64,".format(mime) + base64.b64encode(path.read_bytes()).decode("ascii")


def _render_game_event_scene(scenario_id: str, events: list[str], coins: int) -> None:
    """Render only fixed HTML/CSS/JS animation handlers for allowlisted Python events."""
    events = validated_events(events)
    if not events:
        return
    image = {"CASTLE_GATE": "castle-gate-quest.png", "FUEL_STATION": "fuel-station-quest.svg"}.get(scenario_id, "shopping-cart-quest.png")
    event_json = json.dumps(events)
    scene_html = """<html><style>
      body{margin:0;font-family:Arial,sans-serif;background:#f7ead9}.scene{position:relative;overflow:hidden;height:390px;border:3px solid #9a6948;border-radius:18px;background:url('{IMAGE}') center/cover;box-shadow:0 10px 20px #4b2e2444}.veil{position:absolute;inset:0;background:#311a0a55}.gate{position:absolute;left:36%;bottom:0;width:28%;height:62%;display:flex;z-index:2}.door{width:50%;background:linear-gradient(90deg,#3c2012,#704124);border:3px solid #d3a46b;transition:transform .7s ease}.door:first-child{border-radius:11px 0 0 0}.door:last-child{border-radius:0 11px 0 0}.gate.shake{animation:shake .4s}.gate.open .door:first-child{transform:translateX(-105%) rotateY(55deg)}.gate.open .door:last-child{transform:translateX(105%) rotateY(-55deg)}.key{position:absolute;right:18%;bottom:26%;font-size:52px;filter:drop-shadow(0 0 10px #ffe8a0);z-index:4}.hero{position:absolute;bottom:7%;left:22%;font-size:48px;z-index:4;transition:transform .7s}.hero.move{transform:translateX(210px) scale(1.15)}.banner{position:absolute;top:18px;left:50%;transform:translateX(-50%);z-index:5;padding:10px 18px;border-radius:20px;background:#4b2e24e8;border:1px solid #f1cd95;color:#fff5e5;font-weight:800}.wallet{position:absolute;top:18px;right:18px;z-index:6;background:#342016e8;border:1px solid #efc57f;border-radius:12px;padding:9px 13px;color:#ffe49a;font-weight:900}.coin{position:absolute;z-index:7;font-size:34px;transition:all .8s cubic-bezier(.2,.8,.2,1)}.glow{position:absolute;inset:0;opacity:0;background:#ffe6a455;transition:opacity .5s}.glow.on{opacity:1}@keyframes shake{25%{translate:-9px 0}50%{translate:9px 0}75%{translate:-5px 0}}
    </style><body><div class='scene'><div id='glow' class='glow'></div><div class='veil'></div><div id='banner' class='banner'>Quest event</div><div id='wallet' class='wallet'>🪙 {COINS}</div><div id='gate' class='gate'><div class='door'></div><div class='door'></div></div><div id='hero' class='hero'>🧑‍💻</div><div class='key'>🔑</div></div><script>
      const events={EVENTS};const gate=document.getElementById('gate'),hero=document.getElementById('hero'),banner=document.getElementById('banner'),wallet=document.getElementById('wallet'),glow=document.getElementById('glow');let gained=0;
      function coin(){const c=document.createElement('div');c.className='coin';c.textContent='🪙';c.style.left='48%';c.style.top='55%';document.querySelector('.scene').appendChild(c);requestAnimationFrame(()=>{c.style.left='88%';c.style.top='8%';c.style.transform='scale(.45) rotate(540deg)';c.style.opacity='0'});setTimeout(()=>{gained+=10;wallet.textContent='🪙 '+({COINS}+gained);c.remove()},850)}
      function handleGameEvent(event){if(event==='CASTLE_GATE_SHAKE'||event==='WRONG_CODE'){banner.textContent='Not quite — the gate is still locked. Ask for a hint and try again.';gate.classList.add('shake');setTimeout(()=>gate.classList.remove('shake'),450)}if(event==='CASTLE_GATE_UNLOCKED'){banner.textContent='The key fits! Unlocking the gate…'}if(event==='CASTLE_GATE_OPEN'||event==='DOOR_OPEN'){banner.textContent='Gate open! You solved the quest.';gate.classList.add('open');hero.classList.add('move');glow.classList.add('on')}if(event==='COIN_COLLECTED'||event==='TREASURE_REVEALED'){coin()}if(event==='MISSION_COMPLETE'){banner.textContent='Mission complete! Your XP and coin reward are saved.'}if(event==='LEVEL_UP'){banner.textContent='✨ CHECKPOINT UNLOCKED — a new world is ready!'}}
      events.forEach((event,index)=>setTimeout(()=>handleGameEvent(event),index*720));
    </script></body></html>""".replace("{IMAGE}", _asset_data(image)).replace("{EVENTS}", event_json).replace("{COINS}", str(coins))
    components.html(scene_html, height=400, scrolling=False)


def _render_interactive_game(completed: int, coins: int) -> None:
    """Client-side quest navigation: a game view, not a static collection of cards."""
    game_html = """<!doctype html><html><head><meta charset='utf-8'><style>
      *{box-sizing:border-box}body{margin:0;background:#e9f5ff;font-family:Inter,Arial,sans-serif;color:#fff}.game{min-height:620px;border-radius:20px;overflow:hidden;background:#042b56;box-shadow:0 14px 28px #002c5844}.hud{height:74px;padding:12px 18px;display:flex;align-items:center;gap:20px;background:linear-gradient(100deg,#03234a,#0873b8);border-bottom:2px solid #56dcff}.brand{font-size:25px;font-weight:900;color:#ffd84a;letter-spacing:1px;text-shadow:2px 2px #001b3b}.sub{font-size:11px;color:#c5efff}.nav{margin-left:auto;display:flex;gap:8px}.nav button,.primary{border:1px solid #6ee9ff;border-radius:10px;color:#fff;background:#083a6c;padding:8px 13px;font-weight:800;cursor:pointer}.nav button:hover,.nav button.active,.primary{background:#118ed6;transform:translateY(-1px)}.coins{background:#061f42;border:1px solid #46c8ff;padding:7px 11px;border-radius:12px;font-weight:800;color:#ffdf51}.screen{display:none;min-height:546px;padding:20px}.screen.active{display:block}.home{background:linear-gradient(#002c5777,#002c5777),url('{MAP}') center/cover}.home-card{max-width:530px;margin:80px auto;padding:28px;border-radius:22px;background:#062c59e8;border:2px solid #7cefff;text-align:center;box-shadow:0 12px 22px #001a38}.home-card h1{margin:0;color:#ffe45d;font-size:32px}.map{position:relative;background:linear-gradient(#00345c38,#00345c38),url('{MAP}') center/cover;min-height:546px}.tip{position:absolute;top:18px;left:18px;background:#fff2a5;color:#5a3900;border-radius:18px;padding:10px 14px;font-size:12px;font-weight:800}.node{position:absolute;width:142px;border:2px solid #b9f6ff;border-radius:16px;background:linear-gradient(#0a5c8fee,#032a55ee);padding:9px;color:#fff;box-shadow:0 6px 12px #001b3a;cursor:pointer;text-align:left;animation:float 2.7s ease-in-out infinite}.node:hover{border-color:#ffe457;transform:scale(1.06)}.node.lock{filter:grayscale(1);opacity:.74;cursor:not-allowed}.node b{display:block;font-size:13px}.node small{color:#ffe468;font-size:10px}@keyframes float{50%{translate:0 -7px}}.n1{left:6%;bottom:20%}.n2{left:24%;bottom:39%;animation-delay:.2s}.n3{left:43%;bottom:26%;animation-delay:.5s}.n4{left:61%;bottom:43%;animation-delay:.8s}.n5{left:78%;bottom:25%;animation-delay:1.1s}.levels{background:linear-gradient(135deg,#063561,#0a7abb)}.levels h2{margin-top:0}.level-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.level{padding:16px;border:1px solid #6feaff;border-radius:16px;background:#043366;cursor:pointer}.level:hover{background:#07518f}.level.lock{opacity:.55;filter:grayscale(1)}.lesson{background:linear-gradient(135deg,#072e59,#075c95);position:relative}.back{position:absolute;top:18px;right:18px}.lesson-grid{display:grid;grid-template-columns:1fr 1fr;gap:22px;max-width:960px;margin:50px auto}.scene{width:100%;border-radius:18px;border:2px solid #68eaff}.panel{padding:22px;border-radius:18px;background:#032852e8;border:1px solid #65eaff}.panel h2{color:#ffe66b;margin-top:0}.code{font-family:monospace;background:#001a35;color:#a7f4ff;padding:13px;border-radius:10px}.practice{width:100%;min-height:86px;background:#001a35;color:#c8f7ff;border:1px solid #51dfff;border-radius:10px;padding:10px}.result{min-height:24px;color:#ffec7b;font-weight:700}@media(max-width:720px){.hud{height:auto;flex-wrap:wrap}.nav{margin-left:0}.level-grid,.lesson-grid{grid-template-columns:1fr}.node{width:112px}.n1{left:3%}.n2{left:25%}.n3{left:47%}.n4{left:65%}.n5{left:43%;bottom:7%}}</style></head><body><div class='game'><div class='hud'><div><div class='brand'>🐍 PYQUEST</div><div class='sub'>Code · Solve · Level Up</div></div><div class='coins'>🪙 {COINS} coins · ⭐ {COMPLETED} quests</div><div class='nav'><button onclick="show('home')">⌂ Home</button><button onclick="show('map')">🗺 Map</button><button onclick="show('levels')">☰ Levels</button></div></div>
      <section id='home' class='screen home active'><div class='home-card'><h1>Welcome, Explorer!</h1><p>You do not need to know code yet. Start with a tiny mission, learn one idea, then try it safely.</p><button class='primary' onclick="show('map')">Start Level 1 →</button></div></section>
      <section id='map' class='screen map'><div class='tip'>Click the glowing level nodes to enter a world.</div><button class='node n1' onclick='openLevel(1)'>✅ <b>1. First Words</b><small>Shopping Cart</small></button><button class='node n2' onclick='openLevel(2)'>🛍️ <b>2. Variables</b><small>Mall Mission</small></button><button class='node n3' onclick='openLevel(3)'>🏰 <b>3. Conditions</b><small>Castle Gate</small></button><button class='node n4 lock' onclick='locked()'>🔒 <b>4. Loops</b><small>Fuel Station</small></button><button class='node n5 lock' onclick='locked()'>🔒 <b>5. Lists</b><small>Treasure Chest</small></button></section>
      <section id='levels' class='screen levels'><h2>Choose a learning world</h2><p>Levels unlock after you complete the small missions below this game screen.</p><div class='level-grid'><div class='level' onclick='openLevel(1)'><b>🛒 Level 1 · First Words</b><p>Learn what <code>print()</code> does.</p></div><div class='level' onclick='openLevel(2)'><b>🛍️ Level 2 · Mall Variables</b><p>Store an item name.</p></div><div class='level' onclick='openLevel(3)'><b>🏰 Level 3 · Castle Gate</b><p>Make one decision.</p></div><div class='level lock' onclick='locked()'><b>🔒 Fuel Station</b><p>Unlock after Level 3.</p></div><div class='level lock' onclick='locked()'><b>🔒 Treasure Chest</b><p>Unlock later.</p></div></div></section>
      <section id='lesson' class='screen lesson'><button class='nav back' onclick="show('map')">← Back to map</button><div class='lesson-grid'><img id='scene' class='scene' src='{CART}'/><div class='panel'><h2 id='lessonTitle'>Level 1 · First Words</h2><p id='lessonText'>A computer cannot guess what you want to say. <code>print()</code> tells it to display a message.</p><div class='code' id='example'>print("Hello, explorer!")</div><p id='lessonStep'>Try typing a print message below. It is okay to make mistakes.</p><textarea id='practice' class='practice' placeholder='Type: print("Hello")'></textarea><button class='primary' onclick='checkPractice()'>Try my first line</button><div id='result' class='result'></div><p style='font-size:11px;color:#bfeeff'>When ready, continue with the AI mission and code workspace underneath this game.</p></div></div></section></div><script>
      const lessons={1:{title:'Level 1 · First Words',text:'A computer cannot guess what you want to say. print() tells it to display a message.',example:'print("Hello, explorer!")',step:'Type one print message. You are only learning to show text.'},2:{title:'Level 2 · Mall Variables',text:'A variable is a labeled box. Put an item name into it, then show it to the shopper.',example:'item = "apple"\nprint(item)',step:'Try storing one item in a variable. No maths is needed.'},3:{title:'Level 3 · Castle Gate',text:'An if statement checks one rule. If the rule is true, the gate can open.',example:'age = 18\nif age >= 18:\n    print("Gate open")',step:'Read this example first. The full AI mission below will guide you slowly.'}};
      function show(name){document.querySelectorAll('.screen').forEach(x=>x.classList.remove('active'));document.getElementById(name).classList.add('active')}
      function openLevel(n){const x=lessons[n];document.getElementById('lessonTitle').textContent=x.title;document.getElementById('lessonText').textContent=x.text;document.getElementById('example').textContent=x.example;document.getElementById('lessonStep').textContent=x.step;document.getElementById('practice').value='';document.getElementById('result').textContent='';show('lesson')}
      function checkPractice(){const v=document.getElementById('practice').value;if(v.includes('print(')){document.getElementById('result').textContent='✨ Great start! You used print(). Now try the AI mission below.'}else{document.getElementById('result').textContent='Try typing print("Hello") — you are very close.'}}
      function locked(){alert('This world unlocks after you complete the earlier quests.')}
       </script></body></html>""".replace("{MAP}", _asset_data("python-quest-map.png")).replace("{CART}", _asset_data("shopping-cart-quest.png")).replace("{COINS}", str(coins)).replace("{COMPLETED}", str(completed)).replace("</style>", """.game{background:#3a2118}.hud{background:linear-gradient(100deg,#3a2118,#6b4332);border-color:#d6ad76}.brand{color:#ffe09a;text-shadow:2px 2px #24120c}.sub{color:#f3d9bb}.coins{background:#2d1810;border-color:#e0b77c;color:#ffe09a}.nav button,.primary{background:#513123;border-color:#e0b77c}.nav button:hover,.nav button.active,.primary{background:#8a5b41}.home,.map{filter:saturate(.82)}.home-card,.panel{background:#3a2118ed;border-color:#e0b77c}.home-card h1,.panel h2{color:#ffe09a}.levels,.lesson{background:linear-gradient(135deg,#f1dfc9,#c99f78);color:#3a2118}.levels h2{color:#4b2e24}.level{background:#fff5e8;border-color:#b88359;color:#4b2e24}.level:hover{background:#f4d5ae}.node{background:linear-gradient(#704731ee,#3b2218ee);border-color:#f5d6a3}.node small{color:#ffe09a}.tip{background:#fff1bf;color:#5a3816}.lesson-grid{grid-template-columns:minmax(200px,.55fr) minmax(440px,1.45fr);max-width:1160px}.practice{min-height:160px;font-size:15px;line-height:1.55}.code{font-size:15px}.coin-fly{position:fixed;z-index:9999;font-size:34px;pointer-events:none;filter:drop-shadow(0 3px 2px #4b2e24);transition:left .72s cubic-bezier(.2,.8,.25,1),top .72s cubic-bezier(.2,.8,.25,1),transform .72s ease,opacity .72s ease}.coins.reward-pop{animation:reward-pop .6s ease}@keyframes reward-pop{50%{transform:scale(1.22);color:#fff2a7}}@media(max-width:720px){.lesson-grid{grid-template-columns:1fr}.practice{min-height:130px}}</style>""").replace("</script>", """let demoCoins={COINS};let earnedDemo=false;function awardDemoCoin(){if(earnedDemo)return;earnedDemo=true;const source=document.querySelector('.primary');const target=document.querySelector('.coins');if(!source||!target)return;const a=source.getBoundingClientRect(),b=target.getBoundingClientRect(),coin=document.createElement('div');coin.className='coin-fly';coin.textContent='🪙';coin.style.left=(a.left+a.width/2)+'px';coin.style.top=(a.top+a.height/2)+'px';document.body.appendChild(coin);requestAnimationFrame(()=>{coin.style.left=(b.left+b.width/2)+'px';coin.style.top=(b.top+b.height/2)+'px';coin.style.transform='scale(.45) rotate(540deg)';coin.style.opacity='0'});setTimeout(()=>{demoCoins+=1;target.textContent='🪙 '+demoCoins+' coins · ⭐ {COMPLETED} quests';target.classList.add('reward-pop');coin.remove();setTimeout(()=>target.classList.remove('reward-pop'),650)},730)}function checkPractice(){const v=document.getElementById('practice').value;if(v.includes('print(')){document.getElementById('result').textContent='✨ Great start! Your first practice coin is flying to your wallet. Now try the AI mission below.';awardDemoCoin()}else{document.getElementById('result').textContent='Try typing print("Hello") — you are very close.'}}</script>""")
    # Replacement also covers values inserted by the reward-animation script above.
    game_html = game_html.replace("{COINS}", str(coins)).replace("{COMPLETED}", str(completed))
    components.html(game_html, height=630, scrolling=False)


class CodingLabState(TypedDict, total=False):
    action: Literal["generate", "review", "hint", "solution"]
    level: str
    completed_count: int
    previous_titles: list[str]
    task: dict[str, Any]
    code: str
    research: str
    feedback: str
    passed: bool
    solution: str
    error: str
    scenario: dict[str, str]


def _json_object(text: str) -> dict[str, Any]:
    """Read a JSON object even when the model wraps it in Markdown."""
    fence = chr(96) * 3
    cleaned = text.strip().replace(fence + "json", "").replace(fence, "").strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            return {}
        try:
            value = json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            return {}
    return value if isinstance(value, dict) else {}


def _content(message: Any) -> str:
    content = getattr(message, "content", message)
    return " ".join(str(item) for item in content) if isinstance(content, list) else str(content)


@lru_cache(maxsize=1)
def _model() -> ChatGroq:
    api_key = get_groq_api_key()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is required for the Coding Lab agent.")
    return ChatGroq(model=get_groq_model(), api_key=api_key, temperature=0.25)


def _search_learning_context(state: CodingLabState) -> dict[str, Any]:
    """Tool node: optional web context before planning a challenge."""
    try:
        from langchain_community.tools import DuckDuckGoSearchRun
        query = f"Python {state.get('level', 'Beginner')} tutorial concepts"
        return {"research": DuckDuckGoSearchRun().run(query)[:1800]}
    except Exception:
        return {"research": "Use standard Python documentation and first-principles teaching."}


def _generate_task(state: CodingLabState) -> dict[str, Any]:
    prior = ", ".join(state.get("previous_titles", [])[-12:]) or "none"
    scenario = state.get("scenario", {})
    prompt = f"""You are the planning node in an adaptive Python Coding Lab.
Create one fresh {state.get('level', 'Beginner')} Python challenge for a learner who has completed {state.get('completed_count', 0)} verified challenges.
Do not repeat these previous titles: {prior}.
The task must be small, practical, solvable without external packages, and teach one clear idea.
Frame the mission as the reusable scenario '{scenario.get('name', 'Forest Path')}'. Story direction: {scenario.get('story', '')}. Focus first on {scenario.get('concept_focus', 'a suitable Python concept')}.
Use this optional research context only to choose an appropriate concept: {state.get('research', '')}.
Return JSON only with title, prompt, concept, requirements (array of 2-4 strings), and starter_code.
Do not include a solution, tests, answer, or markdown fences."""
    if state.get("level") == "Beginner":
        completed = int(state.get("completed_count", 0))
        guardrail = (
            "BEGINNER SAFETY LADDER: This learner may know nothing. "
            "For challenges 0-1 use only print(), strings, or one variable; no input(), if, loops, lists, functions, or math. "
            "For challenges 2-3 allow one input() or one variable plus print(). "
            "For challenges 4-5 allow exactly one simple if comparison. "
            "Use a single sentence mission, at most two requirements, and give a tiny starter-code comment. "
            f"Current completed count is {completed}; obey the matching rung exactly."
        )
        prompt += "\n" + guardrail
    payload = _json_object(_content(_model().invoke(prompt)))
    required = ("title", "prompt", "concept", "requirements")
    if not all(payload.get(key) for key in required) or not isinstance(payload.get("requirements"), list):
        return {"error": "The tutor could not create a structured challenge. Please try again."}
    return {"task": {
        "key": uuid4().hex,
        "title": str(payload["title"]).strip()[:120],
        "prompt": str(payload["prompt"]).strip(),
        "concept": str(payload["concept"]).strip()[:180],
        "requirements": [str(item).strip() for item in payload["requirements"][:4]],
        "starter_code": str(payload.get("starter_code", "")),
        "category": state.get("level", "Beginner"),
        "scenario": scenario,
    }}


def _review_attempt(state: CodingLabState) -> dict[str, Any]:
    task = state.get("task", {})
    prompt = f"""You are the review node in a Python learning graph. Assess this submitted code without executing it.
A submission passes only if it clearly satisfies every requirement. Be kind but exact.
Task: {task.get('prompt', '')}
Concept: {task.get('concept', '')}
Requirements: {json.dumps(task.get('requirements', []))}
Student code:
{state.get('code', '')}
Return JSON only: {{"passed": true or false, "feedback": "concise explanation and next step"}}.
Never provide a complete replacement solution."""
    payload = _json_object(_content(_model().invoke(prompt)))
    return {"passed": bool(payload.get("passed", False)), "feedback": str(payload.get("feedback", "I could not verify this attempt. Please try again."))}


def _give_hint(state: CodingLabState) -> dict[str, Any]:
    task = state.get("task", {})
    prompt = f"""You are a supportive Python tutor. Give exactly one progressive hint for this task using the student's current attempt.
Explain the missing idea, but do not give final code, full pseudocode, or an answer.
Task: {task.get('prompt', '')}
Concept: {task.get('concept', '')}
Student code:
{state.get('code', '') or '(no attempt yet)'}"""
    return {"feedback": _content(_model().invoke(prompt)).strip()}


def _reveal_solution(state: CodingLabState) -> dict[str, Any]:
    task = state.get("task", {})
    prompt = f"""You are the answer node in a Python learning graph. Produce a correct, short reference solution for this exact task.
Include only Python code followed by a two-sentence explanation.
Task: {task.get('prompt', '')}
Requirements: {json.dumps(task.get('requirements', []))}"""
    return {"solution": _content(_model().invoke(prompt)).strip()}


def _route(state: CodingLabState) -> str:
    return state.get("action", "generate")


@lru_cache(maxsize=1)
def coding_lab_graph():
    """Compile the LangGraph workflow once per Streamlit process."""
    graph = StateGraph(CodingLabState)
    graph.add_node("research", _search_learning_context)
    graph.add_node("generate", _generate_task)
    graph.add_node("review", _review_attempt)
    graph.add_node("hint", _give_hint)
    graph.add_node("solution", _reveal_solution)
    graph.add_conditional_edges(START, _route, {
        "generate": "research", "review": "review", "hint": "hint", "solution": "solution",
    })
    graph.add_edge("research", "generate")
    graph.add_edge("generate", END)
    graph.add_edge("review", END)
    graph.add_edge("hint", END)
    graph.add_edge("solution", END)
    return graph.compile()


def run_coding_agent(action: str, **state: Any) -> dict[str, Any]:
    """Invoke one explicit LangGraph path and return a serialisable result."""
    return dict(coding_lab_graph().invoke({"action": action, **state}))


def _count_completed(user_id: int) -> int:
    conn = get_connection()
    try:
        row = conn.execute("SELECT COUNT(DISTINCT question_key) AS total FROM coding_lab_attempts WHERE user_id = ? AND passed = 1", (user_id,)).fetchone()
        return int(row["total"]) if row else 0
    finally:
        conn.close()


def _count_stage_completed(user_id: int, stage_key: str) -> int:
    """Mastery requires several distinct verified challenges in the same skill."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(DISTINCT question_key) AS total FROM coding_lab_attempts WHERE user_id = ? AND category = ? AND passed = 1",
            (user_id, stage_key),
        ).fetchone()
        return int(row["total"]) if row else 0
    finally:
        conn.close()


def _current_pyquest_stage(user_id: int) -> tuple[dict[str, str], int, int]:
    for stage in PYQUEST_STAGES:
        progress = _count_stage_completed(user_id, stage["key"])
        if progress < stage["need"]:
            return stage, progress, stage["need"]
    final = PYQUEST_STAGES[-1]
    return final, final["need"], final["need"]


def _stage_scenario(stage: dict[str, str], completed: int) -> dict[str, str]:
    return {
        "name": stage["world"], "story": "Master {} through small, friendly missions before moving on.".format(stage["concept"]),
        "concept_focus": stage["concept"], "difficulty": "Beginner", "stage": str(completed + 1),
        "scenario_id": stage["scenario"], "mastery_stage": stage["key"],
    }


def _count_unlocks(user_id: int) -> int:
    conn = get_connection()
    try:
        row = conn.execute("SELECT COUNT(*) AS count FROM coding_lab_attempts WHERE user_id = ? AND feedback = ?", (user_id, "solution_unlock")).fetchone()
        return int(row["count"]) if row else 0
    finally:
        conn.close()


def _is_task_completed(user_id: int, question_key: str) -> bool:
    """A challenge can award progress only once, even after repeated checks."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS count FROM coding_lab_attempts WHERE user_id = ? AND question_key = ? AND passed = 1",
            (user_id, question_key),
        ).fetchone()
        return bool(row and int(row["count"]))
    finally:
        conn.close()


def _render_learn_first(task: dict[str, Any]) -> bool:
    """Give every learner a no-cost learning route before they attempt a task."""
    concept = str(task.get("concept", "Python basics"))
    query = quote_plus(f"Python {concept}")
    st.markdown("### Learn this before you code")
    st.write(f"You do not need prior knowledge. Spend a few minutes learning **{concept}**, then return and try the challenge.")
    resource_columns = st.columns(3)
    with resource_columns[0]:
        st.link_button("IBM SkillsBuild · free learning", "https://skillsbuild.org/", use_container_width=True)
    with resource_columns[1]:
        st.link_button("Cisco Networking Academy · free courses", "https://www.netacad.com/courses", use_container_width=True)
    with resource_columns[2]:
        st.link_button("Python docs · topic guide", f"https://docs.python.org/3/search.html?q={query}", use_container_width=True)
    st.caption("These are focused learning sources, not answers. Read one source, then use the coach and hints if you are stuck.")
    return st.checkbox("I reviewed a learning resource and I am ready to try this task", key=f"coding_lab_ready_{task['key']}")


def _save_attempt(user_id: int, task: dict[str, Any], code: str, passed: bool, feedback: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO coding_lab_attempts (user_id, question_key, category, code, passed, feedback, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, task["key"], task.get("category", "Beginner"), code, int(passed), feedback, datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def _student_id() -> int | None:
    user = st.session_state.get("user")
    if isinstance(user, dict) and user.get("id"):
        return int(user["id"])
    value = st.session_state.get("user_id")
    return int(value) if value else None


def _tutorial_pages(stage_key: str) -> list[tuple[str, str, str]]:
    """Fixed teaching scenes; AI creates missions only after foundations are shown."""
    common = [
        ("Your quest rule", "You never need to memorize everything. Read one small idea, see an example, then try it yourself.", "🗺️"),
    ]
    lessons = {
        "print": [
            ("Meet print()", "`print()` tells Python to show a message. It is like asking the Shopping Cart sign to speak to a shopper.", "🛒"),
            ("Your first line", "Example: `print(\"Hello!\")`\n\nThe text goes inside quotes because it is a string.", "💬"),
            ("Data types", "Python stores different kinds of data: text (`\"apple\"`), whole numbers (`5`), decimal numbers (`2.5`), and true/false values (`True`).", "📦"),
            ("Comments help humans", "A comment starts with `#`. Python ignores it, but it helps you remember your plan.\n\nExample: `# greet the shopper`", "📝"),
        ],
        "input": [
            ("Meet input()", "`input()` lets your program ask the user a question while it is running. The answer arrives as text.", "🎤"),
            ("Ask, then display", "Example: `name = input(\"What is your name? \")` then `print(name)`.", "⌨️"),
            ("Variables are labeled boxes", "`name` is a variable. It remembers the answer so you can use it later.", "📦"),
        ],
        "variables": [
            ("Store information", "A variable is a name that points to a value: `item = \"apple\"`.", "🛍️"),
            ("Use the value", "You can show it with `print(item)`. Keep names short and meaningful.", "🏷️"),
        ],
        "conditions": [
            ("Make a decision", "`if` checks a rule. Your program chooses what to do when the rule is true or false.", "🏰"),
            ("A simple gate", "Example: `if age >= 18:` followed by an indented `print(\"Gate open\")`.", "🔑"),
        ],
        "loops": [("Repeat safely", "A loop repeats a small action. Start with `for number in range(3):`.", "🔁")],
        "functions": [("Build a helper", "A function gives a repeated job a name, so your program stays organized.", "🤖")],
    }
    return common + lessons.get(stage_key, [])


def _render_pre_level_tutorial(stage: dict[str, str]) -> bool:
    pages = _tutorial_pages(stage["key"])
    state_key = "pyquest_lesson_page_{}".format(stage["key"])
    page = min(int(st.session_state.get(state_key, 0)), len(pages) - 1)
    title, copy, icon = pages[page]
    st.markdown("<div style='padding:1.35rem;border:2px solid #b7835e;border-radius:18px;background:linear-gradient(135deg,#fff7eb,#ead4bd);color:#4b2e24'><div style='font-size:2rem'>{}</div><h3 style='margin:.2rem 0;color:#4b2e24'>Story lesson {}/{} · {}</h3><div style='white-space:pre-line;line-height:1.65'>{}</div></div>".format(icon, page + 1, len(pages), html.escape(title), html.escape(copy)), unsafe_allow_html=True)
    previous, next_page, start = st.columns(3)
    with previous:
        if st.button("← Previous", disabled=page == 0, key="tutorial_previous_" + stage["key"]):
            st.session_state[state_key] = page - 1
            st.rerun()
    with next_page:
        if st.button("Next lesson →", disabled=page >= len(pages) - 1, key="tutorial_next_" + stage["key"]):
            st.session_state[state_key] = page + 1
            st.rerun()
    with start:
        return st.button("▶ Start this level", type="primary", disabled=page < len(pages) - 1, key="tutorial_start_" + stage["key"], use_container_width=True)
    return False


def _start_stage_quest(user_id: int, stage: dict[str, str], completed: int, session_key: str, history_key: str) -> None:
    """Python/LangGraph starts a quest only after the learner finishes the story lesson."""
    with st.spinner("The Python learning engine is preparing your next small mission…"):
        scenario = _stage_scenario(stage, completed)
        result = run_coding_agent(
            "generate", level="Beginner", completed_count=completed,
            previous_titles=st.session_state.get(history_key, []), scenario=scenario,
        )
    task = result.get("task")
    if not task:
        st.warning(result.get("error", "The planner did not return a challenge. Please try again."))
        return
    task["category"] = stage["key"]
    task["mastery_stage"] = stage["key"]
    task["scenario"] = scenario
    st.session_state[session_key] = task
    st.session_state[history_key] = (st.session_state.get(history_key, []) + [task["title"]])[-30:]
    st.session_state.pop(f"coding_lab_answer_{user_id}", None)
    st.rerun()


def render_coding_lab() -> None:
    """Render an endless, adaptive Python practice loop."""
    user_id = _student_id()
    if not user_id:
        st.info("Sign in as a student to start your personal Coding Lab.")
        return

    completed = _count_completed(user_id)
    coins = max(0, completed // 3 - _count_unlocks(user_id))
    progress_in_coin_cycle = completed % 3
    _render_game_hud(completed, coins)
    st.markdown("<div style='display:flex;justify-content:space-between;align-items:center'><h3 style='margin:.25rem 0;color:#073b70'>🗺️ Your Python Quest Map</h3><span style='background:#fff0a1;padding:.35rem .75rem;border-radius:99px;color:#5a3800;font-weight:700'>Complete quests · collect coins · unlock worlds</span></div>", unsafe_allow_html=True)
    _render_interactive_game(completed, coins)

    info, bar, next_up = st.columns([1, 3, 1])
    with info:
        st.metric("Verified quests", completed)
    with bar:
        st.markdown("**Coin progress**")
        coin_progress = st.progress(progress_in_coin_cycle / 3, text=f"{progress_in_coin_cycle}/3 correct answers toward the next 🪙")
    with next_up:
        st.metric("Next coin", 3 - progress_in_coin_cycle if progress_in_coin_cycle else 3)

    stage, stage_progress, stage_goal = _current_pyquest_stage(user_id)
    pending_events = validated_events(st.session_state.pop("pyquest_game_events", []))
    event_scenario = str(st.session_state.pop("pyquest_event_scenario", stage["scenario"]))
    if pending_events:
        _render_game_event_scene(event_scenario, pending_events, coins)
    st.markdown("### 🎮 Mission Control")
    st.caption("Current learning world: **{}** · {} · Mastery: {}/{} verified missions".format(stage["title"], stage["concept"], stage_progress, stage_goal))
    session_key = f"coding_lab_task_{user_id}"
    history_key = f"coding_lab_titles_{user_id}"
    task = st.session_state.get(session_key)

    if not task:
        if _render_pre_level_tutorial(stage):
            try:
                _start_stage_quest(user_id, stage, completed, session_key, history_key)
            except Exception:
                st.error("The AI tutor is temporarily unavailable. Please try again shortly.")
        else:
            st.info("Read each story lesson, then the Start Level button will unlock your first AI-generated mission.")
        return

    safe_title = html.escape(task["title"])
    st.markdown("<div style='background:linear-gradient(100deg,#063563,#0878bf);border-radius:16px;padding:1rem 1.2rem;color:#fff;margin-top:.8rem'><h3 style='color:#ffe95a;margin:0'>🏆 " + safe_title + "</h3><small>Complete this mission to earn progress toward a coin.</small></div>", unsafe_allow_html=True)
    scenario = task.get("scenario") or _stage_scenario(stage, completed)
    scene, briefing = st.columns([1, 1.35], gap="large")
    with scene:
        _render_scenario_art(scenario)
        st.info(f"🎮 **Mission world: {scenario.get('name', 'Forest Path')}**")
    with briefing:
        st.markdown("#### Quest briefing")
        st.write(scenario.get("story", "Build your Python skill one step at a time."))
        st.write(task["prompt"])
        st.caption(f"Skill unlocked: {task['concept']}")
        st.markdown("**Win this quest by**")
        for requirement in task["requirements"]:
            st.markdown(f"- {requirement}")

    if not _render_learn_first(task):
        st.info("Start with one free learning resource above. When you are ready, tick the box to open your coding workspace.")
        return

    st.markdown("#### 🖥️ Wide coding terminal")
    code = st.text_area("Write your Python attempt", value=task.get("starter_code", ""), height=360, key=f"coding_lab_code_{task['key']}")
    check, hint, answer = st.columns(3)
    if check.button("Check my logic"):
        if _is_task_completed(user_id, task["key"]):
            st.info("You already earned this task's progress point. Create a fresh challenge for the next point.")
        elif not code.strip():
            st.warning("Write an attempt first. The tutor will coach your first step.")
        else:
            with st.spinner("The review node is checking your logic…"):
                try:
                    result = run_coding_agent("review", task=task, code=code)
                    passed = bool(result.get("passed", False))
                    feedback = result.get("feedback", "No review was returned.")
                    _save_attempt(user_id, task, code, passed, feedback)
                    if passed:
                        next_completed = completed + 1
                        next_stage_progress = stage_progress + 1
                        scenario_id = str((task.get("scenario") or {}).get("scenario_id", stage["scenario"]))
                        st.session_state["pyquest_game_events"] = outcome_events(scenario_id, True, level_up=next_stage_progress >= stage_goal)
                        st.session_state["pyquest_event_scenario"] = scenario_id
                        st.session_state.pop(session_key, None)
                        st.success("Correct answer verified! Your scene reward is ready.")
                        st.rerun()
                    else:
                        scenario_id = str((task.get("scenario") or {}).get("scenario_id", stage["scenario"]))
                        _render_game_event_scene(scenario_id, outcome_events(scenario_id, False), coins)
                        st.info(feedback)
                except Exception:
                    st.error("The review node is temporarily unavailable. Your work has not been marked.")

    if hint.button("Give a gentle hint"):
        with st.spinner("The coaching node is preparing one hint…"):
            try:
                st.info(run_coding_agent("hint", task=task, code=code).get("feedback", "Try breaking the task into one smaller step."))
            except Exception:
                st.error("The hint node is temporarily unavailable.")

    if answer.button("Use 1 coin for answer", disabled=coins < 1):
        with st.spinner("Unlocking the reference answer…"):
            try:
                solution = run_coding_agent("solution", task=task, code=code).get("solution", "No answer was returned.")
                _save_attempt(user_id, task, "", False, "solution_unlock")
                st.session_state[f"coding_lab_answer_{user_id}"] = solution
                st.rerun()
            except Exception:
                st.error("The answer node is temporarily unavailable. Your coin was not used.")

    if coins < 1:
        st.caption("Earn one answer coin after every three verified, distinct challenges. Coins are not required for hints.")
    unlocked = st.session_state.get(f"coding_lab_answer_{user_id}")
    if unlocked:
        st.markdown("### Unlocked reference answer")
        st.code(unlocked, language="python")
