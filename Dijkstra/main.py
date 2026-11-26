import heapq
import math
import random
import time
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(
    title="DijkstraNav Runtime Diagnostic Engine",
    description="다익스트라(Dijkstra SSSP) 네비게이션 길찾기 시각화 및 단계별 히스토그램 스냅샷 엔진",
    version="2.4.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------
class EdgeInput(BaseModel):
    source: str
    target: str
    weight: float = Field(gt=0)
    distance_km: float = Field(default=1.0, gt=0)
    congestion: float = Field(default=0.1, ge=0.0, le=1.0)
    road_name: str = ""


class NodeInput(BaseModel):
    id: str
    label: str
    short_label: str
    map_x: float
    map_y: float
    graph_x: float
    graph_y: float


class DijkstraRequest(BaseModel):
    preset: str = Field(default="centum_ai_hub")
    start: Optional[str] = None
    end: Optional[str] = None
    traffic_multiplier: float = Field(default=1.0, ge=0.5, le=3.0)
    nodes: Optional[List[NodeInput]] = None
    edges: Optional[List[EdgeInput]] = None


class GenerateRequest(BaseModel):
    node_count: int = Field(default=8, ge=6, le=12)
    seed: Optional[int] = None
    traffic_multiplier: float = Field(default=1.0, ge=0.5, le=3.0)


# ---------------------------------------------------------
# 도로망 프리셋 데이터 (Stitch 디자인 기반)
# ---------------------------------------------------------
PRESETS: Dict[str, Dict[str, Any]] = {
    "centum_ai_hub": {
        "id": "centum_ai_hub",
        "name": "센텀-AI허브 도심 도로망 (8정점)",
        "default_start": "V0",
        "default_end": "V7",
        "nodes": [
            {"id": "V0", "label": "센텀 중앙로터리", "short_label": "Centum", "map_x": 120, "map_y": 240, "graph_x": 50, "graph_y": 125},
            {"id": "V1", "label": "테크노밸리 북로", "short_label": "테크노북로", "map_x": 260, "map_y": 110, "graph_x": 140, "graph_y": 55},
            {"id": "V2", "label": "판교 나들목 IC", "short_label": "판교 IC남로", "map_x": 320, "map_y": 380, "graph_x": 140, "graph_y": 195},
            {"id": "V3", "label": "바이오캠퍼스 교차로", "short_label": "바이오교차", "map_x": 340, "map_y": 240, "graph_x": 180, "graph_y": 125},
            {"id": "V4", "label": "북부 순환 고가", "short_label": "북부고가", "map_x": 460, "map_y": 90, "graph_x": 270, "graph_y": 55},
            {"id": "V5", "label": "글로벌 R&D 사거리", "short_label": "글로벌 R&D", "map_x": 590, "map_y": 240, "graph_x": 290, "graph_y": 125},
            {"id": "V6", "label": "스마트 물류 터미널", "short_label": "스마트물류", "map_x": 820, "map_y": 190, "graph_x": 380, "graph_y": 70},
            {"id": "V7", "label": "AI R&D Hub 미래관", "short_label": "AI R&D Hub", "map_x": 980, "map_y": 270, "graph_x": 410, "graph_y": 175},
        ],
        "edges": [
            {"source": "V0", "target": "V1", "weight": 8.4, "distance_km": 3.1, "congestion": 0.72, "road_name": "센텀북대로"},
            {"source": "V0", "target": "V2", "weight": 6.2, "distance_km": 2.9, "congestion": 0.35, "road_name": "남부순환로"},
            {"source": "V0", "target": "V3", "weight": 4.2, "distance_km": 2.4, "congestion": 0.15, "road_name": "중앙대로 직진"},
            {"source": "V1", "target": "V4", "weight": 5.5, "distance_km": 2.8, "congestion": 0.85, "road_name": "북부고가 진입로"},
            {"source": "V1", "target": "V3", "weight": 3.0, "distance_km": 1.6, "congestion": 0.25, "road_name": "테크노 연결로"},
            {"source": "V2", "target": "V3", "weight": 2.4, "distance_km": 1.5, "congestion": 0.20, "road_name": "IC 연결도로"},
            {"source": "V2", "target": "V5", "weight": 6.8, "distance_km": 3.5, "congestion": 0.78, "road_name": "남측 외곽로"},
            {"source": "V3", "target": "V5", "weight": 3.8, "distance_km": 2.8, "congestion": 0.18, "road_name": "글로벌 R&D 직진로"},
            {"source": "V4", "target": "V5", "weight": 4.6, "distance_km": 2.5, "congestion": 0.40, "road_name": "고가 하행선"},
            {"source": "V4", "target": "V6", "weight": 6.5, "distance_km": 3.9, "congestion": 0.55, "road_name": "동부 간선로"},
            {"source": "V5", "target": "V6", "weight": 4.4, "distance_km": 3.8, "congestion": 0.22, "road_name": "물류터미널 우회로"},
            {"source": "V5", "target": "V7", "weight": 9.2, "distance_km": 4.9, "congestion": 0.88, "road_name": "도심 혼잡 직선로"},
            {"source": "V6", "target": "V7", "weight": 3.1, "distance_km": 3.4, "congestion": 0.12, "road_name": "AI허브 진입로"},
        ],
    },
    "urban_rush_hour": {
        "id": "urban_rush_hour",
        "name": "출퇴근 혼잡 우회망 (10정점)",
        "default_start": "V0",
        "default_end": "V9",
        "nodes": [
            {"id": "V0", "label": "강남역 사거리", "short_label": "강남역", "map_x": 100, "map_y": 240, "graph_x": 42, "graph_y": 125},
            {"id": "V1", "label": "역삼 테헤란로", "short_label": "역삼", "map_x": 240, "map_y": 130, "graph_x": 115, "graph_y": 55},
            {"id": "V2", "label": "양재 시민의숲", "short_label": "양재", "map_x": 240, "map_y": 355, "graph_x": 115, "graph_y": 195},
            {"id": "V3", "label": "선릉 교차로", "short_label": "선릉", "map_x": 400, "map_y": 225, "graph_x": 185, "graph_y": 125},
            {"id": "V4", "label": "삼성 무역센터", "short_label": "삼성", "map_x": 540, "map_y": 100, "graph_x": 255, "graph_y": 50},
            {"id": "V5", "label": "도곡 타워로", "short_label": "도곡", "map_x": 520, "map_y": 365, "graph_x": 255, "graph_y": 200},
            {"id": "V6", "label": "잠실 종합운동장", "short_label": "종합운동장", "map_x": 690, "map_y": 195, "graph_x": 325, "graph_y": 115},
            {"id": "V7", "label": "수서 환승센터", "short_label": "수서", "map_x": 720, "map_y": 350, "graph_x": 335, "graph_y": 195},
            {"id": "V8", "label": "석촌 호수로", "short_label": "석촌", "map_x": 865, "map_y": 140, "graph_x": 390, "graph_y": 75},
            {"id": "V9", "label": "판교 테크노 허브", "short_label": "테크노허브", "map_x": 1020, "map_y": 255, "graph_x": 425, "graph_y": 150},
        ],
        "edges": [
            {"source": "V0", "target": "V1", "weight": 7.5, "distance_km": 1.8, "congestion": 0.90, "road_name": "테헤란 정체구간"},
            {"source": "V0", "target": "V2", "weight": 3.4, "distance_km": 2.2, "congestion": 0.25, "road_name": "강남대로 남행"},
            {"source": "V0", "target": "V3", "weight": 6.2, "distance_km": 2.6, "congestion": 0.70, "road_name": "언주로"},
            {"source": "V1", "target": "V3", "weight": 2.8, "distance_km": 1.4, "congestion": 0.30, "road_name": "선릉로"},
            {"source": "V1", "target": "V4", "weight": 6.4, "distance_km": 2.5, "congestion": 0.80, "road_name": "봉은사로"},
            {"source": "V2", "target": "V3", "weight": 4.1, "distance_km": 2.1, "congestion": 0.35, "road_name": "도곡로"},
            {"source": "V2", "target": "V5", "weight": 3.2, "distance_km": 2.4, "congestion": 0.20, "road_name": "남부순환 우회"},
            {"source": "V3", "target": "V4", "weight": 3.9, "distance_km": 1.9, "congestion": 0.45, "road_name": "테헤란 동행"},
            {"source": "V3", "target": "V6", "weight": 5.6, "distance_km": 3.1, "congestion": 0.60, "road_name": "영동대로"},
            {"source": "V4", "target": "V6", "weight": 3.1, "distance_km": 1.7, "congestion": 0.25, "road_name": "탄천교"},
            {"source": "V4", "target": "V8", "weight": 7.8, "distance_km": 3.8, "congestion": 0.82, "road_name": "올림픽대로"},
            {"source": "V5", "target": "V7", "weight": 3.5, "distance_km": 2.7, "congestion": 0.18, "road_name": "양재대로"},
            {"source": "V6", "target": "V8", "weight": 3.3, "distance_km": 2.1, "congestion": 0.30, "road_name": "백제고분로"},
            {"source": "V6", "target": "V9", "weight": 7.9, "distance_km": 4.6, "congestion": 0.75, "road_name": "송파대로"},
            {"source": "V7", "target": "V9", "weight": 4.2, "distance_km": 3.6, "congestion": 0.15, "road_name": "분당수서고속화"},
            {"source": "V8", "target": "V9", "weight": 4.8, "distance_km": 3.9, "congestion": 0.40, "road_name": "위례서로"},
        ],
    },
}


# ---------------------------------------------------------
# 랜덤 도로망 생성기
# ---------------------------------------------------------
def generate_random_road_network(node_count: int = 8, seed: Optional[int] = None) -> Dict[str, Any]:
    rng = random.Random(seed)
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    cols = max(3, math.ceil(node_count / 2))
    landmarks = [
        "중앙로터리", "테크노북로", "IC 나들목", "바이오교차로", "북부고가",
        "R&D 사거리", "물류터미널", "AI 허브", "스마트타워", "에코파크",
        "환승센터", "미래관",
    ]

    for i in range(node_count):
        col = i // 2 if i < node_count - 1 else cols - 1
        if i == 0:
            mx, my = 110, 240
            gx, gy = 45, 125
        elif i == node_count - 1:
            mx, my = 1000, 245
            gx, gy = 415, 125
        else:
            step_x = (880 - 210) / max(1, (node_count - 2) / 2)
            layer = (i - 1) // 2
            is_top = (i % 2 == 1)
            mx = round(230 + layer * min(190, step_x) + rng.uniform(-25, 25))
            my = round((125 if is_top else 355) + rng.uniform(-35, 35))
            gx = round(45 + (mx - 110) * (370 / 890))
            gy = round(35 + (my - 80) * (180 / 320))

        name = landmarks[i % len(landmarks)]
        nodes.append({
            "id": f"V{i}",
            "label": f"{name} ({i}구역)",
            "short_label": name,
            "map_x": mx,
            "map_y": my,
            "graph_x": gx,
            "graph_y": gy,
        })

    edge_set = set()

    def add_edge(u_idx: int, v_idx: int):
        if u_idx == v_idx or (u_idx, v_idx) in edge_set:
            return
        edge_set.add((u_idx, v_idx))
        u_n, v_n = nodes[u_idx], nodes[v_idx]
        pixel_dist = math.hypot(v_n["map_x"] - u_n["map_x"], v_n["map_y"] - u_n["map_y"])
        dist_km = round(max(0.8, pixel_dist / 95.0), 1)
        congestion = round(rng.uniform(0.1, 0.92), 2)
        weight = round(dist_km * (1.2 + congestion * 1.4), 1)
        edges.append({
            "source": u_n["id"],
            "target": v_n["id"],
            "weight": weight,
            "distance_km": dist_km,
            "congestion": congestion,
            "road_name": f"도로 {u_n['id']}-{v_n['id']}",
        })

    # 전방향 연결성 보장
    for i in range(node_count - 1):
        add_edge(i, i + 1)
        if i + 2 < node_count:
            add_edge(i, i + 2)
        if i + 3 < node_count and rng.random() < 0.55:
            add_edge(i, i + 3)

    return {
        "id": "custom_random",
        "name": f"랜덤 생성 도로망 ({node_count}정점)",
        "default_start": "V0",
        "default_end": f"V{node_count - 1}",
        "nodes": nodes,
        "edges": edges,
    }


# ---------------------------------------------------------
# 다익스트라 알고리즘 + 단계별 히스토그램 스냅샷 엔진
# ---------------------------------------------------------
def run_dijkstra_engine(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    start_id: str,
    end_id: str,
    traffic_multiplier: float = 1.0,
) -> Dict[str, Any]:
    t0 = time.perf_counter()

    node_ids = [n["id"] for n in nodes]
    node_map = {n["id"]: n for n in nodes}
    if start_id not in node_map or end_id not in node_map:
        raise ValueError(f"유효하지 않은 출발지({start_id}) 또는 목적지({end_id})입니다.")

    # 교통 혼잡도 배율 반영
    effective_edges: List[Dict[str, Any]] = []
    adj: Dict[str, List[Dict[str, Any]]] = {nid: [] for nid in node_ids}
    for e in edges:
        cong = float(e.get("congestion", 0.1))
        base_w = float(e["weight"])
        # 혼잡도가 높을수록 배율 영향 증가
        eff_w = round(base_w * (1.0 + (traffic_multiplier - 1.0) * (0.4 + cong)), 1)
        eff_w = max(0.5, eff_w)
        edge_obj = {
            **e,
            "base_weight": base_w,
            "weight": eff_w,
        }
        effective_edges.append(edge_obj)
        if e["source"] in adj:
            adj[e["source"]].append(edge_obj)

    V = len(node_ids)
    E = len(effective_edges)
    theoretical_max_ops = max(1, round((V + E) * math.log2(max(2, V))))

    dist: Dict[str, float] = {nid: math.inf for nid in node_ids}
    prev: Dict[str, Optional[str]] = {nid: None for nid in node_ids}
    settled: List[str] = []
    settled_set = set()
    dist[start_id] = 0.0

    # Min-Heap: (dist, node_id)
    pq: List[tuple] = [(0.0, start_id)]

    # 누적 카운터
    extract_count = 0
    relax_checks = 0
    relax_updates = 0
    heap_pushes = 1
    peak_heap_size = 1

    steps: List[Dict[str, Any]] = []
    relaxation_logs: List[Dict[str, Any]] = []

    def build_step(
        action: str,
        active_line: int,
        message: str,
        current_node: Optional[str] = None,
        target_node: Optional[str] = None,
        active_edge: Optional[Dict[str, Any]] = None,
        relaxed_edges: Optional[List[str]] = None,
    ):
        nonlocal peak_heap_size
        peak_heap_size = max(peak_heap_size, len(pq))
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 3)

        # 현재 큐에 대기 중인 정점 집합
        queued_nodes = {item[1] for item in pq if item[1] not in settled_set}

        # 거리 분포 히스토그램 계산
        finite_vals = [d for d in dist.values() if not math.isinf(d)]
        max_finite = max(finite_vals) if finite_vals else 1.0
        if max_finite <= 0:
            max_finite = 1.0

        distance_bars = []
        for nid in node_ids:
            d_val = dist[nid]
            is_inf = math.isinf(d_val)
            if nid == current_node and action in ("EXTRACT_MIN", "RELAX_SUCCESS", "RELAX_SKIP"):
                st = "EXTRACTING"
            elif nid in settled_set:
                st = "SETTLED"
            elif nid in queued_nodes:
                st = "QUEUED"
            else:
                st = "UNVISITED"

            distance_bars.append({
                "node": nid,
                "label": node_map[nid]["short_label"],
                "distance": None if is_inf else round(d_val, 1),
                "is_inf": is_inf,
                "ratio": 0.0 if is_inf else round(min(1.0, d_val / max_finite), 3),
                "state": st,
                "prev": prev[nid],
            })

        heap_snapshot = []
        for idx, (h_d, h_n) in enumerate(pq):
            heap_snapshot.append({
                "index": idx,
                "dist": round(h_d, 1),
                "node": h_n,
                "parent_idx": None if idx == 0 else (idx - 1) // 2,
                "is_stale": (h_n in settled_set) or (h_d > dist[h_n]),
            })

        heap_depth = 0 if len(pq) == 0 else math.floor(math.log2(len(pq))) + 1
        cumulative_ops = extract_count + relax_checks + relax_updates + heap_pushes

        step_obj = {
            "step_id": len(steps) + 1,
            "action": action,
            "active_line": active_line,
            "message": message,
            "current_node": current_node,
            "target_node": target_node,
            "active_edge": active_edge,
            "distances": {nid: (None if math.isinf(dist[nid]) else round(dist[nid], 1)) for nid in node_ids},
            "prev": dict(prev),
            "settled": list(settled),
            "queued": sorted(list(queued_nodes)),
            "pq": heap_snapshot,
            "heap_depth": heap_depth,
            "histogram": {
                "distance_bars": distance_bars,
                "state_counts": {
                    "settled": len(settled_set),
                    "queued": len(queued_nodes),
                    "unvisited": max(0, V - len(settled_set) - len(queued_nodes)),
                },
                "ops_bars": {
                    "extract_min": extract_count,
                    "relax_checks": relax_checks,
                    "relax_updates": relax_updates,
                    "heap_pushes": heap_pushes,
                },
            },
            "metadata": {
                "elapsed_ms": elapsed_ms,
                "time_complexity": {
                    "notation": "O((V + E) log V)",
                    "cumulative_operations": cumulative_ops,
                    "theoretical_max": theoretical_max_ops,
                    "savings_pct": round(max(0.0, (1.0 - (cumulative_ops / max(1, theoretical_max_ops * 2))) * 100), 1),
                },
                "space_complexity": {
                    "notation": "O(V + E)",
                    "current_heap_size": len(pq),
                    "peak_heap_size": peak_heap_size,
                    "est_memory_kb": round((V * 64 + E * 48 + len(pq) * 32) / 1024, 2),
                },
                "settled_pct": round((len(settled_set) / max(1, V)) * 100, 1),
            },
        }
        steps.append(step_obj)

    # Step 1: 초기화
    build_step(
        action="INIT",
        active_line=4,
        message=f"초기화 완료: D[{start_id}] = 0.0 설정 및 Min-Heap에 (0.0, {start_id}) 삽입",
        current_node=start_id,
    )

    found_goal = False

    while pq:
        cur_d, u = heapq.heappop(pq)
        extract_count += 1

        if u in settled_set or cur_d > dist[u]:
            relaxation_logs.append({
                "step": len(steps) + 1,
                "type": "STALE",
                "text": f"힙에서 ({round(cur_d, 1)}, {u}) 추출 — 이미 더 짧은 경로({round(dist[u], 1)})로 확정되어 건너뜀",
            })
            build_step(
                action="SKIP_STALE",
                active_line=7,
                message=f"오래된 힙 항목 ({round(cur_d, 1)}, {u}) 무시 (cur_d > dist[{u}])",
                current_node=u,
            )
            continue

        settled.append(u)
        settled_set.add(u)

        build_step(
            action="EXTRACT_MIN",
            active_line=6,
            message=f"Min-Heap 최솟값 추출: {u} ({node_map[u]['short_label']}) 확정 — D[{u}] = {round(cur_d, 1)}",
            current_node=u,
        )

        if u == end_id:
            found_goal = True
            relaxation_logs.append({
                "step": len(steps) + 1,
                "type": "GOAL",
                "text": f"목적지 {end_id} ({node_map[end_id]['label']}) 최단 거리 {round(cur_d, 1)} 최종 확정!",
            })
            build_step(
                action="GOAL_REACHED",
                active_line=12,
                message=f"목적지 {end_id} 도달! 최적 최단 경로 비용 D[{end_id}] = {round(cur_d, 1)}",
                current_node=u,
            )
            break

        for edge in adj[u]:
            v = edge["target"]
            w = edge["weight"]
            relax_checks += 1
            old_d = dist[v]
            cand_d = round(cur_d + w, 2)

            if cand_d < old_d:
                dist[v] = cand_d
                prev[v] = u
                heapq.heappush(pq, (cand_d, v))
                relax_updates += 1
                heap_pushes += 1

                old_str = "∞" if math.isinf(old_d) else str(round(old_d, 1))
                log_text = f"완화 성공: {u}→{v} (w={w}) | D[{v}]: {old_str} → {round(cand_d, 1)}"
                relaxation_logs.append({"step": len(steps) + 1, "type": "RELAX", "text": log_text})
                build_step(
                    action="RELAX_SUCCESS",
                    active_line=10,
                    message=log_text,
                    current_node=u,
                    target_node=v,
                    active_edge={"source": u, "target": v, "weight": w, "updated": True},
                )
            else:
                old_str = "∞" if math.isinf(old_d) else str(round(old_d, 1))
                log_text = f"완화 유지: {u}→{v} (w={w}) | {round(cand_d, 1)} ≥ 기존 D[{v}]={old_str}"
                relaxation_logs.append({"step": len(steps) + 1, "type": "KEEP", "text": log_text})
                build_step(
                    action="RELAX_SKIP",
                    active_line=9,
                    message=log_text,
                    current_node=u,
                    target_node=v,
                    active_edge={"source": u, "target": v, "weight": w, "updated": False},
                )

    # 진행률(%) 백필
    total_steps = max(1, len(steps))
    for idx, st in enumerate(steps):
        st["metadata"]["progress_pct"] = round(((idx + 1) / total_steps) * 100, 1)

    # 최단 경로 역추적
    optimal_path: List[str] = []
    optimal_edges: List[Dict[str, Any]] = []
    total_distance_km = 0.0
    if found_goal or not math.isinf(dist[end_id]):
        curr: Optional[str] = end_id
        while curr is not None:
            optimal_path.append(curr)
            curr = prev[curr]
        optimal_path.reverse()

        edge_lookup = {(e["source"], e["target"]): e for e in effective_edges}
        for i in range(len(optimal_path) - 1):
            e = edge_lookup.get((optimal_path[i], optimal_path[i + 1]))
            if e:
                optimal_edges.append(e)
                total_distance_km += float(e.get("distance_km", 1.0))

    total_cost = None if math.isinf(dist[end_id]) else round(dist[end_id], 1)
    total_distance_km = round(total_distance_km, 1)
    est_minutes = round((total_distance_km / 36.0) * 60.0 * (0.85 + 0.3 * traffic_multiplier), 1)
    total_duration_ms = round((time.perf_counter() - t0) * 1000, 3)

    # 인접 행렬 생성
    adj_matrix = []
    edge_lookup_all = {(e["source"], e["target"]): e["weight"] for e in effective_edges}
    for r_id in node_ids:
        row = []
        for c_id in node_ids:
            if r_id == c_id:
                row.append(0)
            else:
                row.append(edge_lookup_all.get((r_id, c_id), None))
        adj_matrix.append({"node": r_id, "values": row})

    return {
        "status": "success",
        "start": start_id,
        "end": end_id,
        "traffic_multiplier": traffic_multiplier,
        "nodes": nodes,
        "edges": effective_edges,
        "optimal_path": optimal_path,
        "optimal_edges": optimal_edges,
        "adjacency_matrix": adj_matrix,
        "relaxation_logs": relaxation_logs,
        "summary": {
            "found": len(optimal_path) > 0 and optimal_path[0] == start_id,
            "node_count": V,
            "edge_count": E,
            "total_steps": len(steps),
            "settled_count": len(settled_set),
            "settled_pct": round((len(settled_set) / max(1, V)) * 100, 1),
            "total_cost": total_cost,
            "total_distance_km": total_distance_km,
            "est_time_min": est_minutes,
            "extract_count": extract_count,
            "relax_checks": relax_checks,
            "relax_updates": relax_updates,
            "total_operations": extract_count + relax_checks + relax_updates + heap_pushes,
            "peak_heap_size": peak_heap_size,
            "execution_time_ms": total_duration_ms,
            "time_complexity": "O((V + E) log V)",
            "optimality": "최적성 보장 (Optimal)",
        },
        "steps": steps,
    }


# ---------------------------------------------------------
# API Routes
# ---------------------------------------------------------
@app.get("/health")
def health_check():
    return {
        "status": "online",
        "service": "DijkstraNav SSSP Engine",
        "version": "2.4.0",
        "algorithm": "Dijkstra (Min-Heap PriorityQueue)",
        "timestamp": time.time(),
    }


@app.get("/api/presets")
def get_presets():
    return {
        "status": "success",
        "presets": [
            {
                "id": p["id"],
                "name": p["name"],
                "node_count": len(p["nodes"]),
                "edge_count": len(p["edges"]),
                "default_start": p["default_start"],
                "default_end": p["default_end"],
            }
            for p in PRESETS.values()
        ],
    }


@app.post("/api/dijkstra/run")
def api_run_dijkstra(req: DijkstraRequest):
    if req.nodes and req.edges:
        nodes = [n.model_dump() for n in req.nodes]
        edges = [e.model_dump() for e in req.edges]
        start_id = req.start or nodes[0]["id"]
        end_id = req.end or nodes[-1]["id"]
    else:
        preset = PRESETS.get(req.preset)
        if not preset:
            raise HTTPException(status_code=404, detail=f"알 수 없는 프리셋: {req.preset}")
        nodes = preset["nodes"]
        edges = preset["edges"]
        start_id = req.start or preset["default_start"]
        end_id = req.end or preset["default_end"]

    try:
        return run_dijkstra_engine(nodes, edges, start_id, end_id, req.traffic_multiplier)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@app.post("/api/dijkstra/generate")
def api_generate_and_run(req: GenerateRequest):
    net = generate_random_road_network(req.node_count, req.seed)
    return run_dijkstra_engine(
        net["nodes"],
        net["edges"],
        net["default_start"],
        net["default_end"],
        req.traffic_multiplier,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
