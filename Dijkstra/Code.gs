/**
 * DijkstraNav: Single-Source Shortest Path Visualizer - Google Apps Script Backend (Code.gs)
 * FastAPI(@main.py) 연동 + 동일 스키마의 GAS 내장 로컬 다익스트라 폴백 엔진 지원
 */

var DEFAULT_FASTAPI_URL = 'http://localhost:8000';

function getApiBaseUrl() {
  var props = PropertiesService.getScriptProperties();
  return props.getProperty('FASTAPI_URL') || DEFAULT_FASTAPI_URL;
}

function doGet(e) {
  return HtmlService.createHtmlOutputFromFile('index')
    .setTitle('DijkstraNav | 다익스트라 네비게이션 알고리즘 시각화 워크벤치')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
    .addMetaTag('viewport', 'width=device-width, initial-scale=1.0');
}

/**
 * GitHub Actions(gas-url-sync)에서 Cloud Run URL을 자동 주입하는 웹훅 엔드포인트
 */
function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    var serviceUrl = data.serviceUrl || data.url;
    if (serviceUrl) {
      PropertiesService.getScriptProperties().setProperty('FASTAPI_URL', serviceUrl);
      return ContentService
        .createTextOutput(JSON.stringify({ status: 'ok', message: 'FASTAPI_URL updated', url: serviceUrl }))
        .setMimeType(ContentService.MimeType.JSON);
    }
    return ContentService
      .createTextOutput(JSON.stringify({ status: 'error', message: 'serviceUrl not provided' }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ status: 'error', message: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * FastAPI 백엔드 헬스체크
 */
function checkServerStatus() {
  var baseUrl = getApiBaseUrl();
  try {
    var res = UrlFetchApp.fetch(baseUrl + '/health', {
      method: 'get',
      muteHttpExceptions: true
    });
    var code = res.getResponseCode();
    if (code === 200) {
      return {
        status: 'online',
        statusCode: 200,
        url: baseUrl,
        message: 'Connected ' + baseUrl
      };
    }
    return {
      status: 'warning',
      statusCode: code,
      url: baseUrl,
      message: 'FastAPI 응답 오류 (HTTP ' + code + ') — 로컬 엔진 전환'
    };
  } catch (err) {
    return {
      status: 'offline',
      url: baseUrl,
      message: 'GAS Local Engine (FastAPI 오프라인 폴백)'
    };
  }
}

/**
 * 다익스트라 시뮬레이션 실행 (FastAPI 우선 -> 실패 시 GAS 내장 엔진 폴백)
 */
function runDijkstraSimulation(options) {
  options = options || {};
  var preset = options.preset || 'centum_ai_hub';
  var start = options.start || null;
  var end = options.end || null;
  var trafficMultiplier = typeof options.traffic_multiplier === 'number' ? options.traffic_multiplier : 1.0;
  var isRandom = (preset === 'custom_random');
  var nodeCount = options.node_count || 8;

  var baseUrl = getApiBaseUrl();
  var endpoint = isRandom ? '/api/dijkstra/generate' : '/api/dijkstra/run';
  var payload = isRandom
    ? { node_count: nodeCount, traffic_multiplier: trafficMultiplier }
    : { preset: preset, start: start, end: end, traffic_multiplier: trafficMultiplier };

  try {
    var res = UrlFetchApp.fetch(baseUrl + endpoint, {
      method: 'post',
      contentType: 'application/json',
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    });
    if (res.getResponseCode() === 200) {
      var data = JSON.parse(res.getContentText());
      data.engineSource = 'FastAPI (' + baseUrl + ')';
      return data;
    }
  } catch (err) {
    // 오프라인 시 아래 GAS 내장 엔진으로 즉시 폴백
  }

  var localData = runGasLocalDijkstra(preset, start, end, trafficMultiplier, nodeCount);
  localData.engineSource = 'GAS Local Engine';
  return localData;
}

/**
 * 기본 도로망 프리셋 (main.py와 100% 동일)
 */
function getLocalPresets_() {
  return {
    centum_ai_hub: {
      id: 'centum_ai_hub',
      name: '센텀-AI허브 도심 도로망 (8정점)',
      default_start: 'V0',
      default_end: 'V7',
      nodes: [
        { id: 'V0', label: '센텀 중앙로터리', short_label: 'Centum', map_x: 120, map_y: 240, graph_x: 50, graph_y: 125 },
        { id: 'V1', label: '테크노밸리 북로', short_label: '테크노북로', map_x: 260, map_y: 110, graph_x: 140, graph_y: 55 },
        { id: 'V2', label: '판교 나들목 IC', short_label: '판교 IC남로', map_x: 320, map_y: 380, graph_x: 140, graph_y: 195 },
        { id: 'V3', label: '바이오캠퍼스 교차로', short_label: '바이오교차', map_x: 340, map_y: 240, graph_x: 180, graph_y: 125 },
        { id: 'V4', label: '북부 순환 고가', short_label: '북부고가', map_x: 460, map_y: 90, graph_x: 270, graph_y: 55 },
        { id: 'V5', label: '글로벌 R&D 사거리', short_label: '글로벌 R&D', map_x: 590, map_y: 240, graph_x: 290, graph_y: 125 },
        { id: 'V6', label: '스마트 물류 터미널', short_label: '스마트물류', map_x: 820, map_y: 190, graph_x: 380, graph_y: 70 },
        { id: 'V7', label: 'AI R&D Hub 미래관', short_label: 'AI R&D Hub', map_x: 980, map_y: 270, graph_x: 410, graph_y: 175 }
      ],
      edges: [
        { source: 'V0', target: 'V1', weight: 8.4, distance_km: 3.1, congestion: 0.72, road_name: '센텀북대로' },
        { source: 'V0', target: 'V2', weight: 6.2, distance_km: 2.9, congestion: 0.35, road_name: '남부순환로' },
        { source: 'V0', target: 'V3', weight: 4.2, distance_km: 2.4, congestion: 0.15, road_name: '중앙대로 직진' },
        { source: 'V1', target: 'V4', weight: 5.5, distance_km: 2.8, congestion: 0.85, road_name: '북부고가 진입로' },
        { source: 'V1', target: 'V3', weight: 3.0, distance_km: 1.6, congestion: 0.25, road_name: '테크노 연결로' },
        { source: 'V2', target: 'V3', weight: 2.4, distance_km: 1.5, congestion: 0.20, road_name: 'IC 연결도로' },
        { source: 'V2', target: 'V5', weight: 6.8, distance_km: 3.5, congestion: 0.78, road_name: '남측 외곽로' },
        { source: 'V3', target: 'V5', weight: 3.8, distance_km: 2.8, congestion: 0.18, road_name: '글로벌 R&D 직진로' },
        { source: 'V4', target: 'V5', weight: 4.6, distance_km: 2.5, congestion: 0.40, road_name: '고가 하행선' },
        { source: 'V4', target: 'V6', weight: 6.5, distance_km: 3.9, congestion: 0.55, road_name: '동부 간선로' },
        { source: 'V5', target: 'V6', weight: 4.4, distance_km: 3.8, congestion: 0.22, road_name: '물류터미널 우회로' },
        { source: 'V5', target: 'V7', weight: 9.2, distance_km: 4.9, congestion: 0.88, road_name: '도심 혼잡 직선로' },
        { source: 'V6', target: 'V7', weight: 3.1, distance_km: 3.4, congestion: 0.12, road_name: 'AI허브 진입로' }
      ]
    },
    urban_rush_hour: {
      id: 'urban_rush_hour',
      name: '출퇴근 혼잡 우회망 (10정점)',
      default_start: 'V0',
      default_end: 'V9',
      nodes: [
        { id: 'V0', label: '강남역 사거리', short_label: '강남역', map_x: 100, map_y: 240, graph_x: 42, graph_y: 125 },
        { id: 'V1', label: '역삼 테헤란로', short_label: '역삼', map_x: 240, map_y: 130, graph_x: 115, graph_y: 55 },
        { id: 'V2', label: '양재 시민의숲', short_label: '양재', map_x: 240, map_y: 355, graph_x: 115, graph_y: 195 },
        { id: 'V3', label: '선릉 교차로', short_label: '선릉', map_x: 400, map_y: 225, graph_x: 185, graph_y: 125 },
        { id: 'V4', label: '삼성 무역센터', short_label: '삼성', map_x: 540, map_y: 100, graph_x: 255, graph_y: 50 },
        { id: 'V5', label: '도곡 타워로', short_label: '도곡', map_x: 520, map_y: 365, graph_x: 255, graph_y: 200 },
        { id: 'V6', label: '잠실 종합운동장', short_label: '종합운동장', map_x: 690, map_y: 195, graph_x: 325, graph_y: 115 },
        { id: 'V7', label: '수서 환승센터', short_label: '수서', map_x: 720, map_y: 350, graph_x: 335, graph_y: 195 },
        { id: 'V8', label: '석촌 호수로', short_label: '석촌', map_x: 865, map_y: 140, graph_x: 390, graph_y: 75 },
        { id: 'V9', label: '판교 테크노 허브', short_label: '테크노허브', map_x: 1020, map_y: 255, graph_x: 425, graph_y: 150 }
      ],
      edges: [
        { source: 'V0', target: 'V1', weight: 7.5, distance_km: 1.8, congestion: 0.90, road_name: '테헤란 정체구간' },
        { source: 'V0', target: 'V2', weight: 3.4, distance_km: 2.2, congestion: 0.25, road_name: '강남대로 남행' },
        { source: 'V0', target: 'V3', weight: 6.2, distance_km: 2.6, congestion: 0.70, road_name: '언주로' },
        { source: 'V1', target: 'V3', weight: 2.8, distance_km: 1.4, congestion: 0.30, road_name: '선릉로' },
        { source: 'V1', target: 'V4', weight: 6.4, distance_km: 2.5, congestion: 0.80, road_name: '봉은사로' },
        { source: 'V2', target: 'V3', weight: 4.1, distance_km: 2.1, congestion: 0.35, road_name: '도곡로' },
        { source: 'V2', target: 'V5', weight: 3.2, distance_km: 2.4, congestion: 0.20, road_name: '남부순환 우회' },
        { source: 'V3', target: 'V4', weight: 3.9, distance_km: 1.9, congestion: 0.45, road_name: '테헤란 동행' },
        { source: 'V3', target: 'V6', weight: 5.6, distance_km: 3.1, congestion: 0.60, road_name: '영동대로' },
        { source: 'V4', target: 'V6', weight: 3.1, distance_km: 1.7, congestion: 0.25, road_name: '탄천교' },
        { source: 'V4', target: 'V8', weight: 7.8, distance_km: 3.8, congestion: 0.82, road_name: '올림픽대로' },
        { source: 'V5', target: 'V7', weight: 3.5, distance_km: 2.7, congestion: 0.18, road_name: '양재대로' },
        { source: 'V6', target: 'V8', weight: 3.3, distance_km: 2.1, congestion: 0.30, road_name: '백제고분로' },
        { source: 'V6', target: 'V9', weight: 7.9, distance_km: 4.6, congestion: 0.75, road_name: '송파대로' },
        { source: 'V7', target: 'V9', weight: 4.2, distance_km: 3.6, congestion: 0.15, road_name: '분당수서고속화' },
        { source: 'V8', target: 'V9', weight: 4.8, distance_km: 3.9, congestion: 0.40, road_name: '위례서로' }
      ]
    }
  };
}

function generateLocalRandomNetwork_(nodeCount) {
  nodeCount = Math.max(6, Math.min(12, nodeCount || 8));
  var landmarks = ['중앙로터리', '테크노북로', 'IC 나들목', '바이오교차로', '북부고가', 'R&D 사거리', '물류터미널', 'AI 허브', '스마트타워', '에코파크', '환승센터', '미래관'];
  var nodes = [];
  var edges = [];
  for (var i = 0; i < nodeCount; i++) {
    var mx, my, gx, gy;
    if (i === 0) {
      mx = 110; my = 240; gx = 45; gy = 125;
    } else if (i === nodeCount - 1) {
      mx = 1000; my = 245; gx = 415; gy = 125;
    } else {
      var stepX = (880 - 210) / Math.max(1, (nodeCount - 2) / 2);
      var layer = Math.floor((i - 1) / 2);
      var isTop = (i % 2 === 1);
      mx = Math.round(230 + layer * Math.min(190, stepX) + (Math.random() * 50 - 25));
      my = Math.round((isTop ? 125 : 355) + (Math.random() * 70 - 35));
      gx = Math.round(45 + (mx - 110) * (370 / 890));
      gy = Math.round(35 + (my - 80) * (180 / 320));
    }
    var nm = landmarks[i % landmarks.length];
    nodes.push({ id: 'V' + i, label: nm + ' (' + i + '구역)', short_label: nm, map_x: mx, map_y: my, graph_x: gx, graph_y: gy });
  }
  var seen = {};
  function addE(u, v) {
    var k = u + '-' + v;
    if (u === v || seen[k]) return;
    seen[k] = true;
    var un = nodes[u], vn = nodes[v];
    var px = Math.sqrt(Math.pow(vn.map_x - un.map_x, 2) + Math.pow(vn.map_y - un.map_y, 2));
    var dkm = Math.round(Math.max(0.8, px / 95.0) * 10) / 10;
    var cong = Math.round((0.1 + Math.random() * 0.82) * 100) / 100;
    var w = Math.round(dkm * (1.2 + cong * 1.4) * 10) / 10;
    edges.push({ source: un.id, target: vn.id, weight: w, distance_km: dkm, congestion: cong, road_name: '도로 ' + un.id + '-' + vn.id });
  }
  for (var j = 0; j < nodeCount - 1; j++) {
    addE(j, j + 1);
    if (j + 2 < nodeCount) addE(j, j + 2);
    if (j + 3 < nodeCount && Math.random() < 0.55) addE(j, j + 3);
  }
  return { id: 'custom_random', name: '랜덤 도로망 (' + nodeCount + '정점)', default_start: 'V0', default_end: 'V' + (nodeCount - 1), nodes: nodes, edges: edges };
}

/**
 * GAS 내장 다익스트라 엔진 (FastAPI와 100% 동일 스키마)
 */
function runGasLocalDijkstra(presetId, startId, endId, trafficMultiplier, nodeCount) {
  var t0 = new Date().getTime();
  var presets = getLocalPresets_();
  var net = (presetId === 'custom_random') ? generateLocalRandomNetwork_(nodeCount) : (presets[presetId] || presets.centum_ai_hub);

  var nodes = net.nodes;
  var rawEdges = net.edges;
  startId = startId || net.default_start;
  endId = endId || net.default_end;
  trafficMultiplier = trafficMultiplier || 1.0;

  var nodeIds = [];
  var nodeMap = {};
  var adj = {};
  for (var i = 0; i < nodes.length; i++) {
    nodeIds.push(nodes[i].id);
    nodeMap[nodes[i].id] = nodes[i];
    adj[nodes[i].id] = [];
  }
  if (!nodeMap[startId]) startId = net.default_start;
  if (!nodeMap[endId]) endId = net.default_end;

  var effectiveEdges = [];
  var edgeLookup = {};
  for (var eIdx = 0; eIdx < rawEdges.length; eIdx++) {
    var re = rawEdges[eIdx];
    var cong = re.congestion || 0.1;
    var effW = Math.max(0.5, Math.round(re.weight * (1.0 + (trafficMultiplier - 1.0) * (0.4 + cong)) * 10) / 10);
    var eo = {
      source: re.source,
      target: re.target,
      base_weight: re.weight,
      weight: effW,
      distance_km: re.distance_km,
      congestion: cong,
      road_name: re.road_name
    };
    effectiveEdges.push(eo);
    if (adj[re.source]) adj[re.source].push(eo);
    edgeLookup[re.source + '->' + re.target] = eo;
  }

  var V = nodeIds.length;
  var E = effectiveEdges.length;
  var theoreticalMax = Math.max(1, Math.round((V + E) * (Math.log(Math.max(2, V)) / Math.LN2)));

  var dist = {};
  var prev = {};
  for (var n = 0; n < V; n++) {
    dist[nodeIds[n]] = Infinity;
    prev[nodeIds[n]] = null;
  }
  dist[startId] = 0.0;

  var settled = [];
  var settledSet = {};
  var pq = [{ dist: 0.0, node: startId }];

  function pqPush(item) {
    pq.push(item);
    var idx = pq.length - 1;
    while (idx > 0) {
      var p = Math.floor((idx - 1) / 2);
      if (pq[p].dist <= pq[idx].dist) break;
      var tmp = pq[p]; pq[p] = pq[idx]; pq[idx] = tmp;
      idx = p;
    }
  }

  function pqPop() {
    if (pq.length === 0) return null;
    var top = pq[0];
    var last = pq.pop();
    if (pq.length > 0) {
      pq[0] = last;
      var idx = 0;
      while (true) {
        var l = 2 * idx + 1, r = 2 * idx + 2, s = idx;
        if (l < pq.length && pq[l].dist < pq[s].dist) s = l;
        if (r < pq.length && pq[r].dist < pq[s].dist) s = r;
        if (s === idx) break;
        var tmp = pq[idx]; pq[idx] = pq[s]; pq[s] = tmp;
        idx = s;
      }
    }
    return top;
  }

  var extractCount = 0, relaxChecks = 0, relaxUpdates = 0, heapPushes = 1, peakHeapSize = 1;
  var steps = [];
  var relaxationLogs = [];

  function buildStep(action, activeLine, message, currentNode, targetNode, activeEdge) {
    if (pq.length > peakHeapSize) peakHeapSize = pq.length;
    var elapsedMs = Math.round(((new Date().getTime() - t0) + steps.length * 0.14) * 1000) / 1000;

    var queuedMap = {};
    for (var qi = 0; qi < pq.length; qi++) {
      if (!settledSet[pq[qi].node]) queuedMap[pq[qi].node] = true;
    }
    var queuedList = Object.keys(queuedMap).sort();

    var maxFinite = 1.0;
    for (var fi = 0; fi < V; fi++) {
      var dv = dist[nodeIds[fi]];
      if (dv !== Infinity && dv > maxFinite) maxFinite = dv;
    }

    var distanceBars = [];
    var distCopy = {};
    var prevCopy = {};
    for (var bi = 0; bi < V; bi++) {
      var nid = nodeIds[bi];
      var dVal = dist[nid];
      var isInf = (dVal === Infinity);
      var st = 'UNVISITED';
      if (nid === currentNode && (action === 'EXTRACT_MIN' || action === 'RELAX_SUCCESS' || action === 'RELAX_SKIP')) {
        st = 'EXTRACTING';
      } else if (settledSet[nid]) {
        st = 'SETTLED';
      } else if (queuedMap[nid]) {
        st = 'QUEUED';
      }
      distCopy[nid] = isInf ? null : Math.round(dVal * 10) / 10;
      prevCopy[nid] = prev[nid];
      distanceBars.push({
        node: nid,
        label: nodeMap[nid].short_label,
        distance: distCopy[nid],
        is_inf: isInf,
        ratio: isInf ? 0.0 : Math.round(Math.min(1.0, dVal / maxFinite) * 1000) / 1000,
        state: st,
        prev: prev[nid]
      });
    }

    var heapSnap = [];
    for (var hi = 0; hi < pq.length; hi++) {
      heapSnap.push({
        index: hi,
        dist: Math.round(pq[hi].dist * 10) / 10,
        node: pq[hi].node,
        parent_idx: hi === 0 ? null : Math.floor((hi - 1) / 2),
        is_stale: !!settledSet[pq[hi].node] || (pq[hi].dist > dist[pq[hi].node])
      });
    }

    var heapDepth = pq.length === 0 ? 0 : Math.floor(Math.log(pq.length) / Math.LN2) + 1;
    var cumOps = extractCount + relaxChecks + relaxUpdates + heapPushes;

    steps.push({
      step_id: steps.length + 1,
      action: action,
      active_line: activeLine,
      message: message,
      current_node: currentNode || null,
      target_node: targetNode || null,
      active_edge: activeEdge || null,
      distances: distCopy,
      prev: prevCopy,
      settled: settled.slice(),
      queued: queuedList,
      pq: heapSnap,
      heap_depth: heapDepth,
      histogram: {
        distance_bars: distanceBars,
        state_counts: {
          settled: settled.length,
          queued: queuedList.length,
          unvisited: Math.max(0, V - settled.length - queuedList.length)
        },
        ops_bars: {
          extract_min: extractCount,
          relax_checks: relaxChecks,
          relax_updates: relaxUpdates,
          heap_pushes: heapPushes
        }
      },
      metadata: {
        elapsed_ms: elapsedMs,
        time_complexity: {
          notation: 'O((V + E) log V)',
          cumulative_operations: cumOps,
          theoretical_max: theoreticalMax,
          savings_pct: Math.round(Math.max(0, (1 - cumOps / Math.max(1, theoreticalMax * 2)) * 100) * 10) / 10
        },
        space_complexity: {
          notation: 'O(V + E)',
          current_heap_size: pq.length,
          peak_heap_size: peakHeapSize,
          est_memory_kb: Math.round(((V * 64 + E * 48 + pq.length * 32) / 1024) * 100) / 100
        },
        settled_pct: Math.round((settled.length / Math.max(1, V)) * 1000) / 10
      }
    });
  }

  buildStep('INIT', 4, '초기화 완료: D[' + startId + '] = 0.0 설정 및 Min-Heap에 (0.0, ' + startId + ') 삽입', startId, null, null);

  var foundGoal = false;
  while (pq.length > 0) {
    var top = pqPop();
    extractCount++;
    var u = top.node;
    var curD = top.dist;

    if (settledSet[u] || curD > dist[u]) {
      relaxationLogs.push({ step: steps.length + 1, type: 'STALE', text: '힙에서 (' + (Math.round(curD * 10) / 10) + ', ' + u + ') 추출 — 이미 확정되어 건너뜀' });
      buildStep('SKIP_STALE', 7, '오래된 힙 항목 (' + (Math.round(curD * 10) / 10) + ', ' + u + ') 무시', u, null, null);
      continue;
    }

    settled.push(u);
    settledSet[u] = true;
    buildStep('EXTRACT_MIN', 6, 'Min-Heap 최솟값 추출: ' + u + ' (' + nodeMap[u].short_label + ') 확정 — D[' + u + '] = ' + (Math.round(curD * 10) / 10), u, null, null);

    if (u === endId) {
      foundGoal = true;
      relaxationLogs.push({ step: steps.length + 1, type: 'GOAL', text: '목적지 ' + endId + ' (' + nodeMap[endId].label + ') 최단 거리 ' + (Math.round(curD * 10) / 10) + ' 최종 확정!' });
      buildStep('GOAL_REACHED', 12, '목적지 ' + endId + ' 도달! 최적 최단 경로 비용 D[' + endId + '] = ' + (Math.round(curD * 10) / 10), u, null, null);
      break;
    }

    var outEdges = adj[u] || [];
    for (var ei = 0; ei < outEdges.length; ei++) {
      var edge = outEdges[ei];
      var v = edge.target;
      var w = edge.weight;
      relaxChecks++;
      var oldD = dist[v];
      var candD = Math.round((curD + w) * 100) / 100;
      var oldStr = (oldD === Infinity) ? '∞' : String(Math.round(oldD * 10) / 10);

      if (candD < oldD) {
        dist[v] = candD;
        prev[v] = u;
        pqPush({ dist: candD, node: v });
        relaxUpdates++;
        heapPushes++;
        var msgOk = '완화 성공: ' + u + '→' + v + ' (w=' + w + ') | D[' + v + ']: ' + oldStr + ' → ' + (Math.round(candD * 10) / 10);
        relaxationLogs.push({ step: steps.length + 1, type: 'RELAX', text: msgOk });
        buildStep('RELAX_SUCCESS', 10, msgOk, u, v, { source: u, target: v, weight: w, updated: true });
      } else {
        var msgKeep = '완화 유지: ' + u + '→' + v + ' (w=' + w + ') | ' + (Math.round(candD * 10) / 10) + ' ≥ 기존 D[' + v + ']=' + oldStr;
        relaxationLogs.push({ step: steps.length + 1, type: 'KEEP', text: msgKeep });
        buildStep('RELAX_SKIP', 9, msgKeep, u, v, { source: u, target: v, weight: w, updated: false });
      }
    }
  }

  for (var si = 0; si < steps.length; si++) {
    steps[si].metadata.progress_pct = Math.round(((si + 1) / Math.max(1, steps.length)) * 1000) / 10;
  }

  var optimalPath = [];
  var optimalEdges = [];
  var totalDistKm = 0;
  if (foundGoal || dist[endId] !== Infinity) {
    var cur = endId;
    while (cur !== null) {
      optimalPath.push(cur);
      cur = prev[cur];
    }
    optimalPath.reverse();
    for (var pi = 0; pi < optimalPath.length - 1; pi++) {
      var oe = edgeLookup[optimalPath[pi] + '->' + optimalPath[pi + 1]];
      if (oe) {
        optimalEdges.push(oe);
        totalDistKm += oe.distance_km || 1.0;
      }
    }
  }

  var adjMatrix = [];
  for (var r = 0; r < V; r++) {
    var rowVals = [];
    for (var c = 0; c < V; c++) {
      if (r === c) rowVals.push(0);
      else {
        var foundE = edgeLookup[nodeIds[r] + '->' + nodeIds[c]];
        rowVals.push(foundE ? foundE.weight : null);
      }
    }
    adjMatrix.push({ node: nodeIds[r], values: rowVals });
  }

  var totalCost = dist[endId] === Infinity ? null : Math.round(dist[endId] * 10) / 10;
  totalDistKm = Math.round(totalDistKm * 10) / 10;
  var estMin = Math.round((totalDistKm / 36.0) * 60.0 * (0.85 + 0.3 * trafficMultiplier) * 10) / 10;
  var totalMs = Math.round(((new Date().getTime() - t0) + 1.2) * 1000) / 1000;

  return {
    status: 'success',
    start: startId,
    end: endId,
    traffic_multiplier: trafficMultiplier,
    nodes: nodes,
    edges: effectiveEdges,
    optimal_path: optimalPath,
    optimal_edges: optimalEdges,
    adjacency_matrix: adjMatrix,
    relaxation_logs: relaxationLogs,
    summary: {
      found: optimalPath.length > 0 && optimalPath[0] === startId,
      node_count: V,
      edge_count: E,
      total_steps: steps.length,
      settled_count: settled.length,
      settled_pct: Math.round((settled.length / Math.max(1, V)) * 1000) / 10,
      total_cost: totalCost,
      total_distance_km: totalDistKm,
      est_time_min: estMin,
      extract_count: extractCount,
      relax_checks: relaxChecks,
      relax_updates: relaxUpdates,
      total_operations: extractCount + relaxChecks + relaxUpdates + heapPushes,
      peak_heap_size: peakHeapSize,
      execution_time_ms: totalMs,
      time_complexity: 'O((V + E) log V)',
      optimality: '최적성 보장 (Optimal)'
    },
    steps: steps
  };
}
