# -*- coding: utf-8 -*-
"""生成模型 3D 预览 HTML（three.js + OrbitControls，零 Python 第三方依赖）。

两种输出：
- render_html：自包含单文件，three.js 离线内联，双击即可打开（file:// 也可，无需联网）；
- render_float_html：网页端浮窗版本，three.js 走本地静态资源（/app/static/three_bundle.js），
  只在浏览器缓存一次，不随每次重渲染重传 1.3 MB。

three.js 源在 vendor/，由 scripts/make_vendor_bundle.py 打成一个无 import 的单文件。
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_VENDOR_BUNDLE = Path(__file__).resolve().parents[1] / "vendor" / "three_bundle.js"
_STATIC_URL = "/app/static/three_bundle.js"


@lru_cache(maxsize=1)
def three_bundle() -> str:
    """读取离线打包的 three.js（无缓存则返回空串，由调用方回退）。"""
    try:
        return _VENDOR_BUNDLE.read_text(encoding="utf-8")
    except Exception:
        return ""


@lru_cache(maxsize=1)
def three_script_tag(inline: bool) -> str:
    """返回引入 three 的 script 标签。

    inline=True  -> 把 1.3 MB 源码内联进 HTML（独立文件，file:// 可开，可断网）；
    inline=False -> 引用 Streamlit 静态路由（网页浮窗用，浏览器缓存一次）。
    """
    if inline:
        src = three_bundle()
        if not src:
            return ('<script src="https://cdn.jsdelivr.net/npm/three@0.160.0/build/'
                    'three.module.js"></script>')
        return "<script>\n" + src + "\n</script>"
    return f'<script src="{_STATIC_URL}"></script>'

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  html, body { margin: 0; height: 100%; overflow: hidden; font-family: "Microsoft YaHei", sans-serif; }
  #c { position: fixed; inset: 0; }
  #panel { position: fixed; top: 12px; left: 12px; background: rgba(255,255,255,0.93);
           padding: 12px 14px; border-radius: 10px; box-shadow: 0 2px 12px rgba(0,0,0,0.16);
           font-size: 13px; color: #1f2a3a; max-width: 270px; }
  #panel h1 { font-size: 15px; margin: 0 0 6px; }
  #panel .row { display: flex; align-items: center; gap: 7px; margin: 3px 0; }
  .sw { width: 12px; height: 12px; border-radius: 3px; display: inline-block; flex: none; }
  button { margin-top: 8px; padding: 5px 10px; border: 1px solid #3b6a9e; border-radius: 6px;
           background: #eef2f7; color: #2e5e8c; cursor: pointer; font-size: 12px; }
  button:hover { background: #dde7f2; }
  #hint { position: fixed; bottom: 12px; left: 50%; transform: translateX(-50%);
          background: rgba(0,0,0,0.55); color: #fff; padding: 6px 14px; border-radius: 20px;
          font-size: 12px; pointer-events: none; }
</style>
</head>
<body>
<div id="c"></div>
<div id="panel">
  <h1>Abaqus 模型预览</h1>
  <div class="row"><span class="sw" style="background:#4a7fb5"></span> 壳单元（S4R 等）</div>
  <div class="row"><span class="sw" style="background:#9aa7b0"></span> 体单元（C3D8R 等）</div>
  <div class="row"><span class="sw" style="background:#d64545"></span> 线单元（梁 / 桁架 / 弹簧）</div>
  <div class="row"><span class="sw" style="background:#f6c518"></span> 约束（黄点）</div>
  <div class="row"><span class="sw" style="background:#ff9f1c"></span> 温度边界（橙点，DOF 11）</div>
  <div class="row"><span class="sw" style="background:#00d0a0"></span> 位移载荷（青绿箭头）</div>
  <div class="row"><span class="sw" style="background:#e84545"></span> 力载荷（红箭头）</div>
  <div class="row"><span class="sw" style="background:#ff3b30;border-radius:50%"></span> 分布载荷（红点＝受载单元）</div>
  <div class="row" id="stats" style="margin-top:6px;color:#5a6b7d"></div>
  <button id="wire">线框模式</button>
  <button id="onlybc" style="margin-left:6px">仅边界条件</button>
</div>
<div id="hint">鼠标左键旋转 · 滚轮缩放 · 右键平移</div>
__THREE__
<script>
const THREE = window.THREE;
const OrbitControls = window.OrbitControls;

const data = __DATA__;

const b = data.summary.bbox;
const cx = (b[0]+b[3])/2, cy = (b[1]+b[4])/2, cz = (b[2]+b[5])/2;
const maxDim = Math.max(b[3]-b[0], b[4]-b[1], b[5]-b[2]) || 1;
const s = 20 / maxDim;
const pos = new Float32Array(data.nodes.length);
for (let i=0;i<data.nodes.length;i+=3){
  pos[i]   = (data.nodes[i]   - cx) * s;
  pos[i+1] = (data.nodes[i+1] - cy) * s;
  pos[i+2] = (data.nodes[i+2] - cz) * s;
}

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xf5f7fa);

const renderer = new THREE.WebGLRenderer({antialias:true});
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
document.getElementById('c').appendChild(renderer.domElement);

const camera = new THREE.PerspectiveCamera(45, window.innerWidth/window.innerHeight, 0.1, 500);
camera.position.set(28, 18, 28);
camera.lookAt(0,0,0);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

scene.add(new THREE.AmbientLight(0xffffff, 0.75));
const dl = new THREE.DirectionalLight(0xffffff, 0.9);
dl.position.set(30, 50, 30);
scene.add(dl);

const shellMat = new THREE.MeshLambertMaterial({color:0x4a7fb5, side:THREE.DoubleSide});
const solidMat = new THREE.MeshLambertMaterial({color:0x9aa7b0, side:THREE.DoubleSide});
const lineMat = new THREE.LineBasicMaterial({color:0xd64545});

function makeMesh(faces, mat){
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setIndex(faces);
  g.computeVertexNormals();
  const m = new THREE.Mesh(g, mat);
  m.userData.m = true;
  scene.add(m);
  return m;
}

let shellMesh=null, solidMesh=null, lineMesh=null;
if (data.shell_faces.length) shellMesh = makeMesh(data.shell_faces, shellMat);
if (data.solid_faces.length) solidMesh = makeMesh(data.solid_faces, solidMat);
if (data.lines.length){
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setIndex(data.lines);
  lineMesh = new THREE.LineSegments(g, lineMat);
  lineMesh.userData.m = true;
  scene.add(lineMesh);
}

// ---- 边界条件与载荷：约束=黄点；温度(DOF 11)=橙点；非零位移=青绿箭头；力=红箭头；分布载荷=红点 ----
let bcCons = 0, bcDisp = 0, bcTemp = 0, dloadCount = 0, wholeTempField = false;
if (data.boundary && data.boundary.length){
  const cpos = [], tpos = [], disps = [];
  for (const bc of data.boundary){
    const n = bc.node * 3;
    const dofs = (bc.dofs && bc.dofs.length) ? bc.dofs : [1];
    if (dofs.every(d => d === 11)){ tpos.push(pos[n], pos[n+1], pos[n+2]); bcTemp++; }
    else if (bc.value){ disps.push([bc, n]); bcDisp++; }
    else { cpos.push(pos[n], pos[n+1], pos[n+2]); bcCons++; }
  }
  if (cpos.length){
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(cpos), 3));
    scene.add(new THREE.Points(g, new THREE.PointsMaterial({color:0xf6c518, size:0.35, sizeAttenuation:true})));
  }
  if (tpos.length){
    // 温度施加到绝大多数节点时按"全场温度场"处理，否则橙点会把模型盖住看不清
    wholeTempField = tpos.length / 3 > (data.summary.nodes || 1) * 0.6;
    if (!wholeTempField){
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(tpos), 3));
      scene.add(new THREE.Points(g, new THREE.PointsMaterial({color:0xff9f1c, size:0.42, sizeAttenuation:true, depthTest:false})));
    }
  }
  let dmax = 1;
  for (const [bc] of disps) dmax = Math.max(dmax, Math.abs(bc.value));
  for (const [bc, n] of disps){
    const dofs = (bc.dofs && bc.dofs.length) ? bc.dofs : [1];
    for (const dof of dofs){
      let dir = null;
      if (dof === 1) dir = new THREE.Vector3(1,0,0);
      else if (dof === 2) dir = new THREE.Vector3(0,1,0);
      else if (dof === 3) dir = new THREE.Vector3(0,0,1);
      else continue;
      if (bc.value < 0) dir.negate();
      const org = new THREE.Vector3(pos[n], pos[n+1], pos[n+2]);
      const len = 5.0 + 2.0 * Math.abs(bc.value) / dmax;
      const arrow = new THREE.ArrowHelper(dir, org.clone().addScaledVector(dir, -5.0), len, 0x00d0a0, 0.8, 0.34);
      arrow.line.material.depthTest = false;
      arrow.cone.material.depthTest = false;
      scene.add(arrow);
    }
  }
}
if (data.loads && data.loads.length){
  const maxAbs = Math.max(1, ...data.loads.map(l => Math.abs(l.value)));
  for (const ld of data.loads){
    const n = ld.node * 3, dir = new THREE.Vector3(0,0,0);
    if (ld.dof === 1) dir.set(1,0,0);
    else if (ld.dof === 2) dir.set(0,1,0);
    else if (ld.dof === 3) dir.set(0,0,1);
    else continue;
    if (ld.value < 0) dir.negate();
    const org = new THREE.Vector3(pos[n], pos[n+1], pos[n+2]);
    const len = 5.0 + 2.0 * Math.abs(ld.value) / maxAbs;
    const arrow = new THREE.ArrowHelper(dir, org.clone().addScaledVector(dir, -5.0), len, 0xe84545, 0.8, 0.34);
    arrow.line.material.depthTest = false;
    arrow.cone.material.depthTest = false;
    scene.add(arrow);
  }
}
if (data.dloads && data.dloads.length){
  dloadCount = data.dloads.length;
  const p = [];
  for (const dl of data.dloads){
    if (!dl.c.length) continue;
    let x = 0, y = 0, z = 0;
    for (const n of dl.c){ x += pos[n*3]; y += pos[n*3+1]; z += pos[n*3+2]; }
    p.push(x / dl.c.length, y / dl.c.length, z / dl.c.length);
  }
  if (p.length){
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(p), 3));
    scene.add(new THREE.Points(g, new THREE.PointsMaterial({color:0xff3b30, size:0.62, sizeAttenuation:true, depthTest:false})));
  }
}

document.getElementById('stats').innerHTML =
  '节点 ' + data.summary.nodes.toLocaleString() +
  '<br>壳三角 ' + data.summary.shell_tris.toLocaleString() +
  ' · 体三角 ' + data.summary.solid_tris.toLocaleString() +
  '<br>线段 ' + data.summary.line_segs.toLocaleString() +
  '<br>约束 ' + bcCons + ' · 位移载荷 ' + bcDisp +
  ' · 力载荷 ' + (data.loads ? data.loads.length : 0) +
  (bcTemp ? ' · 温度边界 ' + bcTemp + (wholeTempField ? '（全场）' : '') : '') +
  (dloadCount ? ' · 分布载荷 ' + dloadCount : '');

let wire = false;
document.getElementById('wire').onclick = () => {
  wire = !wire;
  if (shellMesh) shellMesh.material.wireframe = wire;
  if (solidMesh) solidMesh.material.wireframe = wire;
  repaint();
};

// 仅边界条件：隐藏所有单元，只留约束/载荷标记，用来核对 BC 位置对不对
let onlyBC = false;
document.getElementById('onlybc').onclick = () => {
  onlyBC = !onlyBC;
  scene.traverse(o => { if (o.userData && o.userData.m) o.visible = !onlyBC; });
  repaint();
};

// 按需渲染：交互时满帧，静止时降到 5 帧/秒兜底（大模型拖动能明显跟手）
let dirty = true, lastAct = performance.now(), lastPaint = 0;
function repaint(){ dirty = true; lastAct = performance.now(); }
controls.addEventListener('change', repaint);
function animate(ts){
  requestAnimationFrame(animate);
  const damping = controls.enableDamping && (performance.now() - lastAct < 700);
  if (dirty || damping || (ts - lastPaint) > 200){
    dirty = false; lastPaint = ts;
    controls.update();
    renderer.render(scene, camera);
  }
}
// 同步测单帧耗时，用于验证不同规模模型的渲染成本
window.__bench = function(n){ n = n || 10; const t0 = performance.now(); for (let i = 0; i < n; i++){ controls.update(); renderer.render(scene, camera); } return ((performance.now() - t0) / n).toFixed(1) + ' ms/frame'; };
animate();
window.addEventListener('resize', ()=>{
  camera.aspect = window.innerWidth/window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
  repaint();
});
</script>
</body>
</html>
"""


def render_html(data: dict, title: str = "Abaqus 模型预览") -> str:
    """自包含单文件：three.js 内联，双击/file:// 打开即可，无需联网。"""
    import html as _html

    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return (
        _HTML_TEMPLATE.replace("__THREE__", three_script_tag(inline=True))
        .replace("__DATA__", payload)
        .replace("__TITLE__", _html.escape(title))
    )


_FLOAT_TEMPLATE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  html,body{margin:0;height:100%;background:transparent;overflow:hidden;font-family:"Microsoft YaHei",sans-serif;}
  #win{position:absolute;inset:0;background:#fff;border-radius:12px;display:flex;flex-direction:column;overflow:hidden;}
  #resize{position:absolute;right:0;bottom:0;width:18px;height:18px;cursor:nwse-resize;z-index:20;
          background:linear-gradient(135deg,transparent 45%,#8a97a3 45%,#8a97a3 55%,transparent 55%);}
  #bar{height:40px;background:#1f2937;color:#fff;display:flex;align-items:center;padding:0 12px;cursor:move;
       user-select:none;font-size:13px;flex:none;gap:8px;}
  #bar .t{flex:1;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
  #bar .x{border:none;background:#ef4444;color:#fff;border-radius:6px;width:26px;height:24px;cursor:pointer;}
  #view{flex:1;position:relative;min-height:0;}
  #c{position:absolute;inset:0;}
  #panel{position:absolute;top:8px;left:8px;background:rgba(255,255,255,.92);padding:7px 9px;border-radius:9px;
         box-shadow:0 2px 10px rgba(0,0,0,.1);font-size:11px;line-height:1.5;color:#1f2a3a;max-width:196px;}
  #panel h1{font-size:12px;margin:0 0 4px;}
  #panel .row{display:flex;align-items:center;gap:6px;margin:2px 0;}
  .sw{width:11px;height:11px;border-radius:3px;display:inline-block;flex:none;}
  button.ctl{margin-top:6px;padding:4px 9px;border:1px solid #3b6a9e;border-radius:6px;background:#eef2f7;
             color:#2e5e8c;cursor:pointer;font-size:12px;}
  #hint{position:absolute;bottom:8px;left:50%;transform:translateX(-50%);background:rgba(0,0,0,.55);color:#fff;
        padding:5px 12px;border-radius:16px;font-size:11px;pointer-events:none;}
</style>
</head>
<body>
<div id="win">
  <div id="bar"><span class="t">__TITLE__</span><button class="x" id="close">✕</button></div>
  <div id="view">
    <div id="c"></div>
    <div id="panel">
      <h1>Abaqus 模型预览</h1>
      <div class="row"><span class="sw" style="background:#4a7fb5"></span> 壳单元（S4R 等）</div>
      <div class="row"><span class="sw" style="background:#9aa7b0"></span> 体单元（C3D8R 等）</div>
      <div class="row"><span class="sw" style="background:#d64545"></span> 线单元（梁 / 桁架 / 弹簧）</div>
      <div class="row"><span class="sw" style="background:#f6c518;border-radius:50%"></span> 约束（黄色节点）</div>
      <div class="row"><span class="sw" style="background:#ff9f1c;border-radius:50%"></span> 温度边界（橙色节点，DOF 11）</div>
      <div class="row"><span class="sw" style="background:#00d0a0"></span> 位移载荷（青绿箭头，如 U1=120mm）</div>
      <div class="row"><span class="sw" style="background:#e84545"></span> 力载荷（红色箭头）</div>
      <div class="row"><span class="sw" style="background:#e84545;border-radius:50%"></span> 分布载荷（红色散点，单元中心）</div>
      <div class="row" id="stats" style="margin-top:5px;color:#5a6b7d"></div>
      <button class="ctl" id="wire" onclick="var s=window.__s;if(s){window.__w=!window.__w;s.children.forEach(function(o){if(o.userData&&o.userData.m&&o.material)o.material.wireframe=window.__w;});}if(window.__repaint)window.__repaint();">线框模式</button>
      <button class="ctl" id="onlybc" onclick="var s=window.__s;if(s){window.__hide3d=!window.__hide3d;s.children.forEach(function(o){if(o.userData&&o.userData.m)o.visible=!window.__hide3d;});}if(window.__repaint)window.__repaint();">仅边界条件</button>
    </div>
    <div id="hint">左键旋转 · 滚轮缩放 · 右键平移 · 拖标题栏移动 · 右下角手柄缩放</div>
  </div>
  <div id="resize" title="拖动缩放"></div>
</div>
__THREE__
<script>
const THREE = window.THREE;
const OrbitControls = window.OrbitControls;
const data = __DATA__;
(function(){
  const win=document.getElementById('win'), bar=document.getElementById('bar'),
        close=document.getElementById('close'), rz=document.getElementById('resize'),
        hint=document.getElementById('hint');
  let fe=null;
  try{ fe = window.frameElement; }catch(e){ fe=null; }
  let pdoc=document;
  try{ if(window.parent && window.parent!==window) pdoc=window.parent.document; }catch(e){}

  // 让宿主 iframe 脱离文档流，变成右下角可拖拽/可缩放的小浮窗（不占对话空间）
  if(fe){
    try{
      const vw = (pdoc.documentElement && pdoc.documentElement.clientWidth) || 1200;
      const vh = (pdoc.documentElement && pdoc.documentElement.clientHeight) || 800;
      const w0 = Math.max(380, Math.min(620, vw - 40));
      const h0 = Math.max(300, Math.min(470, vh - 90));
      const st=fe.style;
      st.position='fixed'; st.right='16px'; st.bottom='16px'; st.left='auto'; st.top='auto';
      st.width=w0+'px'; st.height=h0+'px'; st.zIndex='2147483000'; st.border='none';
      st.borderRadius='12px'; st.boxShadow='0 10px 40px rgba(0,0,0,.35)';
      st.background='#fff'; st.overflow='hidden';
      // 消除原文档流占位，避免拖拽时初始位置留残影
      if(fe.parentElement){ try{ fe.parentElement.style.height='0px'; fe.parentElement.style.minHeight='0px'; fe.parentElement.style.overflow='visible'; }catch(_){} }
    }catch(e){}
  }

  // 拖拽用 transform（GPU 合成，无重绘残影、更跟手）；缩放改 width/height
  let active=false, mode=null, sx=0, sy=0, bx=0, by=0, bw=0, bh=0, lastDx=0, lastDy=0;
  function begin(e, m){
    mode=m; active=true; sx=e.clientX; sy=e.clientY; lastDx=0; lastDy=0;
    try{ window.__rendering=false; }catch(_){}
    if(fe){ const r=fe.getBoundingClientRect(); bx=r.left; by=r.top; bw=r.width; bh=r.height;
            try{ fe.style.willChange='transform'; fe.style.pointerEvents='none'; fe.style.backfaceVisibility='hidden'; fe.style.contain='strict'; fe.style.transform='translateZ(0)'; }catch(_){} }
    else { bx=win.offsetLeft; by=win.offsetTop; bw=win.offsetWidth; bh=win.offsetHeight; }
  }
  let rafPending=false, lastX=0, lastY=0;
  function move(e){
    if(!active) return;
    lastX=e.clientX; lastY=e.clientY;
    if(rafPending) return;
    rafPending=true;
    requestAnimationFrame(()=>{
      rafPending=false;
      if(!active) return;
      const dx=lastX-sx, dy=lastY-sy; lastDx=dx; lastDy=dy;
      if(mode==='drag'){
        if(fe){ fe.style.transform='translate3d('+dx+'px,'+dy+'px,0)'; }
        else { win.style.left=(bx+dx)+'px'; win.style.top=(by+dy)+'px'; }
      } else {
        const nw=Math.max(340,bw+dx)+'px', nh=Math.max(260,bh+dy)+'px';
        if(fe){ fe.style.width=nw; fe.style.height=nh; }
        else { win.style.width=nw; win.style.height=nh; }
        // 缩放过程中就让画布跟着重排，否则松手前画面被裁、点击落点也对不上
        try{ window.dispatchEvent(new Event('resize')); }catch(_){}
      }
    });
  }
  function end(){
    if(mode==='drag'){
      if(fe){ fe.style.transform=''; fe.style.left=(bx+lastDx)+'px'; fe.style.top=(by+lastDy)+'px';
              fe.style.right='auto'; fe.style.bottom='auto'; }
      else { win.style.left=(bx+lastDx)+'px'; win.style.top=(by+lastDy)+'px'; }
    }
    if(mode==='size'){ try{ window.dispatchEvent(new Event('resize')); }catch(_){} }
    // 不管拖动还是缩放，都要把 iframe 的交互恢复回来：
    // 之前 pointerEvents='none' 只在拖动分支复原，缩放一次之后浮窗就再也点不动了
    if(fe){
      try{ fe.style.willChange='auto'; fe.style.pointerEvents=''; fe.style.contain=''; }catch(_){}
    }
    try{ window.__rendering=true; }catch(_){}
    try{ if(window.__repaint) window.__repaint(); }catch(_){}
    active=false; mode=null;
  }
  bar.addEventListener('pointerdown', e=>{
    if(e.target===close) return;
    begin(e,'drag');
    try{ bar.setPointerCapture(e.pointerId); }catch(_){}
    e.preventDefault();
  });
  bar.addEventListener('pointermove', move);
  bar.addEventListener('pointerup', end);
  bar.addEventListener('pointercancel', end);
  window.addEventListener('pointerup', end);

  rz.addEventListener('pointerdown', e=>{
    e.stopPropagation(); e.preventDefault();
    begin(e,'size');
    try{ rz.setPointerCapture(e.pointerId); }catch(_){}
  });
  rz.addEventListener('pointermove', move);
  rz.addEventListener('pointerup', end);
  rz.addEventListener('pointercancel', end);

  close.onclick=()=>{ if(fe){ fe.style.display='none'; } else { win.style.display='none'; hint.style.display='none'; } };
})();
const view=document.getElementById('view');
const b=data.summary.bbox;
const cx=(b[0]+b[3])/2, cy=(b[1]+b[4])/2, cz=(b[2]+b[5])/2;
const maxDim=Math.max(b[3]-b[0],b[4]-b[1],b[5]-b[2])||1;
const s=20/maxDim;
const pos=new Float32Array(data.nodes.length);
for(let i=0;i<data.nodes.length;i+=3){
  pos[i]=(data.nodes[i]-cx)*s; pos[i+1]=(data.nodes[i+1]-cy)*s; pos[i+2]=(data.nodes[i+2]-cz)*s;
}
const scene=new THREE.Scene(); scene.background=new THREE.Color(0xf5f7fa); window.__s=scene;
const renderer=new THREE.WebGLRenderer({antialias:false,powerPreference:'high-performance'});
renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.25));
const __tris=(data.summary.shell_tris||0)+(data.summary.solid_tris||0);
// 大模型降采样：三角形超过 20 万时按 1 倍像素渲染，帧率优先于锐度
if(__tris>200000) renderer.setPixelRatio(1);
let W=view.clientWidth||600, H=view.clientHeight||400;
renderer.setSize(W,H);
document.getElementById('c').appendChild(renderer.domElement);
const camera=new THREE.PerspectiveCamera(45,W/H,0.1,500);
camera.position.set(28,18,28); camera.lookAt(0,0,0);
const controls=new OrbitControls(camera,renderer.domElement); controls.enableDamping=true;
scene.add(new THREE.AmbientLight(0xffffff,0.75));
const dl=new THREE.DirectionalLight(0xffffff,0.9); dl.position.set(30,50,30); scene.add(dl);
const shellMat=new THREE.MeshLambertMaterial({color:0x4a7fb5,side:THREE.DoubleSide});
const solidMat=new THREE.MeshLambertMaterial({color:0x9aa7b0,side:THREE.DoubleSide});
const lineMat=new THREE.LineBasicMaterial({color:0xd64545});
function makeMesh(faces,mat){const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.BufferAttribute(pos,3));g.setIndex(faces);g.computeVertexNormals();const m=new THREE.Mesh(g,mat);m.userData.m=true;scene.add(m);return m;}
let shellMesh=null,solidMesh=null,lineMesh=null;
if(data.shell_faces.length)shellMesh=makeMesh(data.shell_faces,shellMat);
if(data.solid_faces.length)solidMesh=makeMesh(data.solid_faces,solidMat);
if(data.lines.length){const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.BufferAttribute(pos,3));g.setIndex(data.lines);lineMesh=new THREE.LineSegments(g,lineMat);lineMesh.userData.m=true;scene.add(lineMesh);}
// 边界条件：约束=黄色点；位移载荷（U1/UX 给非零值）=蓝色箭头；力载荷=红色箭头
let bcCons=0, bcDisp=0, bcTemp=0, wholeTempField=false;
if(data.boundary && data.boundary.length){
  const cpos=[], disps=[], tpos=[];
  for(const b of data.boundary){
    const n=b.node*3;
    const dofs=(b.dofs&&b.dofs.length)?b.dofs:[1];
    const onlyTemp=dofs.every(d=>d===11);
    if(onlyTemp){ tpos.push(pos[n],pos[n+1],pos[n+2]); bcTemp++; }
    else if(b.value){ disps.push([b,n]); bcDisp++; }
    else { cpos.push(pos[n],pos[n+1],pos[n+2]); bcCons++; }
  }
  if(cpos.length){
    const bgl=new THREE.BufferGeometry();bgl.setAttribute('position',new THREE.BufferAttribute(new Float32Array(cpos),3));
    scene.add(new THREE.Points(bgl,new THREE.PointsMaterial({color:0xf6c518,size:0.35,sizeAttenuation:true})));
  }
  if(tpos.length){
    wholeTempField = tpos.length/3 > (data.summary.nodes||1)*0.6;
    if(!wholeTempField){
      const tgl=new THREE.BufferGeometry();tgl.setAttribute('position',new THREE.BufferAttribute(new Float32Array(tpos),3));
      scene.add(new THREE.Points(tgl,new THREE.PointsMaterial({color:0xff9f1c,size:0.42,sizeAttenuation:true,depthTest:false})));
    }
  }
  let dmax=1; for(const [b,n] of disps){ dmax=Math.max(dmax,Math.abs(b.value)); }
  for(const [b,n] of disps){
    const dofs=(b.dofs&&b.dofs.length)?b.dofs:[1];
    for(const dof of dofs){
      let dir=null;
      if(dof===1)dir=new THREE.Vector3(1,0,0); else if(dof===2)dir=new THREE.Vector3(0,1,0); else if(dof===3)dir=new THREE.Vector3(0,0,1);
      if(!dir) continue;
      if(b.value<0)dir.negate();
      const org=new THREE.Vector3(pos[n],pos[n+1],pos[n+2]);
      const len=5.0+2.0*Math.abs(b.value)/dmax;
      const start=org.clone().addScaledVector(dir,-5.0);
      const arrow=new THREE.ArrowHelper(dir,start,len,0x00d0a0,0.8,0.34);
      arrow.line.material.depthTest=false; arrow.cone.material.depthTest=false;
      scene.add(arrow);
    }
  }
}
if(data.loads && data.loads.length){
  const maxAbs=Math.max(1,...data.loads.map(l=>Math.abs(l.value)));
  for(const ld of data.loads){
    const n=ld.node*3, dir=new THREE.Vector3(0,0,0);
    if(ld.dof===1)dir.set(1,0,0);else if(ld.dof===2)dir.set(0,1,0);else if(ld.dof===3)dir.set(0,0,1);else continue;
    if(ld.value<0)dir.negate();
    const org=new THREE.Vector3(pos[n],pos[n+1],pos[n+2]);
    const len=5.0+2.0*Math.abs(ld.value)/maxAbs;
    const start=org.clone().addScaledVector(dir,-5.0);
    const arrow=new THREE.ArrowHelper(dir,start,len,0xe84545,0.8,0.34);
    arrow.line.material.depthTest=false; arrow.cone.material.depthTest=false;
    scene.add(arrow);
  }
}
let dloadCount=0;
if(data.dloads && data.dloads.length){
  dloadCount=data.dloads.length;
  const p=[];
  for(const dl of data.dloads){
    let cx=0,cy=0,cz=0,k=dl.c.length;
    if(!k) continue;
    for(const n of dl.c){ cx+=pos[n*3]; cy+=pos[n*3+1]; cz+=pos[n*3+2]; }
    p.push(cx/k,cy/k,cz/k);
  }
  if(p.length){
    const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.BufferAttribute(new Float32Array(p),3));
    scene.add(new THREE.Points(g,new THREE.PointsMaterial({color:0xff3b30,size:0.62,sizeAttenuation:true,depthTest:false})));
  }
}
document.getElementById('stats').innerHTML='节点 '+data.summary.nodes.toLocaleString()+'<br>壳三角 '+data.summary.shell_tris.toLocaleString()+' · 体三角 '+data.summary.solid_tris.toLocaleString()+'<br>线段 '+data.summary.line_segs.toLocaleString()+' · 约束 '+bcCons+' · 位移载荷 '+bcDisp+' · 力载荷 '+(data.loads?data.loads.length:0)+(bcTemp?' · 温度边界 '+bcTemp+(wholeTempField?'（全场）':''):'')+(dloadCount?' · 分布载荷 '+dloadCount:'');
function fit(){const w=view.clientWidth,h=view.clientHeight;if(w&&h){W=w;H=h;camera.aspect=w/h;camera.updateProjectionMatrix();renderer.setSize(w,h);}}
setTimeout(fit,60);
// 按需渲染：交互时满帧，静止时降到 5 帧/秒兜底（保证按钮切换、外部改状态也能在 0.2 秒内看到）
let dirty=true, lastAct=performance.now(), lastPaint=0;
window.__repaint=function(){ dirty=true; lastAct=performance.now(); };
controls.addEventListener('change', window.__repaint);
function paint(){ controls.update(); renderer.render(scene,camera); }
function animate(ts){
  requestAnimationFrame(animate);
  if(window.__rendering===false) return;
  const damping = controls.enableDamping && (performance.now()-lastAct<700);
  if(dirty || damping || (ts-lastPaint)>200){
    dirty=false; lastPaint=ts; paint();
  }
}
// 同步测单帧耗时（不受后台标签页 rAF 节流影响），用于回归验证渲染性能
window.__bench=function(n){n=n||10;const t0=performance.now();for(let i=0;i<n;i++){controls.update();renderer.render(scene,camera);}return ((performance.now()-t0)/n).toFixed(1)+' ms/frame';};
animate();
window.addEventListener('resize',()=>{ fit(); window.__repaint(); });
</script>
</body>
</html>
"""


def render_float_html(data: dict, title: str = "Abaqus 模型预览") -> str:
    """页面内可拖拽浮层版本（Streamlit 用，不是独立窗口）。

    three.js 走本地静态路由，避免每次 rerun 都往 iframe 里塞 1.3 MB。
    """
    import html as _html

    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return (
        _FLOAT_TEMPLATE.replace("__THREE__", three_script_tag(inline=True))
        .replace("__DATA__", payload)
        .replace("__TITLE__", _html.escape(title))
    )


def save_viewer_html(inp_path: str, out_html_path: str) -> dict:
    from .inp_viewer import parse_inp_file

    data = parse_inp_file(inp_path)
    with open(out_html_path, "w", encoding="utf-8") as f:
        f.write(render_html(data))
    return data["summary"]


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python -m agent.viewer_html <inp文件> [输出html]")
        sys.exit(1)
    inp = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else inp.rsplit(".", 1)[0] + "_preview.html"
    s = save_viewer_html(inp, out)
    print(f"已生成: {out}")
    print(f"节点 {s['nodes']} · 壳三角 {s['shell_tris']} · 体三角 {s['solid_tris']} · 线段 {s['line_segs']}")

