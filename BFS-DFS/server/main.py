import time
import random
from collections import deque
from typing import List, Dict, Any, Optional, Tuple
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(
    title="ALGO-MAZE Dual Path Runtime Diagnostic Engine",
    description="BFS vs DFS Maze Solver - Step-by-step histogram snapshot engine",
    version="2.4.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class MazeConfig(BaseModel):
    width: int = Field(default=21, ge=7, le=51)
    height: int = Field(default=21, ge=7, le=51)
    algorithm: str = Field(default="recursive_backtracker")
    seed: Optional[int] = None

class SolveRequest(BaseModel):
    grid: List[List[int]]
    start: List[int] = Field(default=[0, 0])
    end: Optional[List[int]] = None
    diagonal: bool = False
    heuristic: str = "none"

def generate_perfect_maze(rows: int, cols: int, seed: Optional[int] = None) -> List[List[int]]:
    if seed is not None:
        random.seed(seed)
    r_dim = rows if rows % 2 == 1 else rows + 1
    c_dim = cols if cols % 2 == 1 else cols + 1
    maze = [[1 for _ in range(c_dim)] for _ in range(r_dim)]
    start_r, start_c = 0, 0
    maze[start_r][start_c] = 0
    stack = [(start_r, start_c)]
    visited = {(start_r, start_c)}
    directions = [(-2, 0), (2, 0), (0, -2), (0, 2)]
    while stack:
        cr, cc = stack[-1]
        neighbors = []
        for dr, dc in directions:
            nr, nc = cr + dr, cc + dc
            if 0 <= nr < r_dim and 0 <= nc < c_dim and (nr, nc) not in visited:
                neighbors.append((nr, nc, dr, dc))
        if neighbors:
            nr, nc, dr, dc = random.choice(neighbors)
            maze[cr + dr // 2][cc + dc // 2] = 0
            maze[nr][nc] = 0
            visited.add((nr, nc))
            stack.append((nr, nc))
        else:
            stack.pop()
    maze[r_dim - 1][c_dim - 1] = 0
    if maze[r_dim - 2][c_dim - 1] == 1 and maze[r_dim - 1][c_dim - 2] == 1:
        maze[r_dim - 2][c_dim - 1] = 0
    return maze

def solve_dual_maze(grid: List[List[int]], start: List[int], end: List[int]):
    rows = len(grid)
    cols = len(grid[0])
    sr, sc = start[0], start[1]
    er, ec = end[0], end[1]
    directions = [(-1, 0, "UP"), (1, 0, "DOWN"), (0, -1, "LEFT"), (0, 1, "RIGHT")]

    # BFS
    bfs_start_time = time.perf_counter()
    queue = deque([(sr, sc, 0)])
    bfs_visited = {(sr, sc): None}
    bfs_history = []
    bfs_peak_queue = 1
    bfs_dir_counts = {"UP": 0, "DOWN": 0, "LEFT": 0, "RIGHT": 0}
    bfs_found = False
    while queue:
        curr_r, curr_c, wave = queue.popleft()
        current_queue_snapshot = [[r, c] for (r, c, _) in list(queue)[:10]]
        bfs_step = {
            "node": [curr_r, curr_c],
            "wave_level": wave,
            "queue_size": len(queue),
            "queue_sample": current_queue_snapshot,
            "queue_head": [curr_r, curr_c],
            "queue_tail": [queue[-1][0], queue[-1][1]] if queue else [curr_r, curr_c],
            "visited_count": len(bfs_visited),
            "is_goal": (curr_r == er and curr_c == ec),
            "dir_counts": dict(bfs_dir_counts)
        }
        bfs_history.append(bfs_step)
        if curr_r == er and curr_c == ec:
            bfs_found = True
            break
        for dr, dc, dname in directions:
            nr, nc = curr_r + dr, curr_c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                if grid[nr][nc] == 0 and (nr, nc) not in bfs_visited:
                    bfs_visited[(nr, nc)] = (curr_r, curr_c)
                    queue.append((nr, nc, wave + 1))
                    bfs_dir_counts[dname] += 1
                    bfs_peak_queue = max(bfs_peak_queue, len(queue))
    bfs_duration_ms = round((time.perf_counter() - bfs_start_time) * 1000, 3)
    bfs_path = []
    if bfs_found:
        curr = (er, ec)
        while curr is not None:
            bfs_path.append(list(curr))
            curr = bfs_visited.get(curr)
        bfs_path.reverse()

    # DFS
    dfs_start_time = time.perf_counter()
    stack = [(sr, sc, 0)]
    dfs_visited = {(sr, sc): None}
    dfs_history = []
    dfs_peak_stack = 1
    dfs_dir_counts = {"UP": 0, "DOWN": 0, "LEFT": 0, "RIGHT": 0}
    dfs_backtracks = 0
    dfs_found = False
    while stack:
        curr_r, curr_c, depth = stack.pop()
        current_stack_snapshot = [[r, c] for (r, c, _) in list(stack)[-10:]]
        dfs_step = {
            "node": [curr_r, curr_c],
            "depth": depth,
            "stack_size": len(stack),
            "stack_sample": current_stack_snapshot,
            "stack_top": [curr_r, curr_c],
            "stack_base": [sr, sc],
            "visited_count": len(dfs_visited),
            "is_goal": (curr_r == er and curr_c == ec),
            "is_backtrack": False,
            "backtrack_count": dfs_backtracks,
            "dir_counts": dict(dfs_dir_counts)
        }
        if curr_r == er and curr_c == ec:
            dfs_found = True
            dfs_history.append(dfs_step)
            break
        valid_neighbors = []
        for dr, dc, dname in directions:
            nr, nc = curr_r + dr, curr_c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                if grid[nr][nc] == 0 and (nr, nc) not in dfs_visited:
                    valid_neighbors.append((nr, nc, depth + 1, dname))
        if valid_neighbors:
            for nr, nc, ndepth, dname in valid_neighbors:
                dfs_visited[(nr, nc)] = (curr_r, curr_c)
                stack.append((nr, nc, ndepth))
                dfs_dir_counts[dname] += 1
                dfs_peak_stack = max(dfs_peak_stack, len(stack))
        else:
            dfs_backtracks += 1
            dfs_step["is_backtrack"] = True
            dfs_step["backtrack_count"] = dfs_backtracks
        dfs_history.append(dfs_step)
    dfs_duration_ms = round((time.perf_counter() - dfs_start_time) * 1000, 3)
    dfs_path = []
    if dfs_found:
        curr = (er, ec)
        while curr is not None:
            dfs_path.append(list(curr))
            curr = dfs_visited.get(curr)
        dfs_path.reverse()

    # Synchronized Steps
    max_steps = max(len(bfs_history), len(dfs_history))
    synchronized_steps = []
    total_cells = rows * cols
    for step_idx in range(max_steps):
        b_st = bfs_history[min(step_idx, len(bfs_history) - 1)]
        d_st = dfs_history[min(step_idx, len(dfs_history) - 1)]
        progress = round(((step_idx + 1) / max_steps) * 100, 1)
        bfs_ops = b_st["visited_count"] + (step_idx + 1)
        dfs_ops = d_st["visited_count"] + (step_idx + 1)
        histogram_snapshot = {
            "step_id": step_idx + 1,
            "progress_pct": progress,
            "exploration_bars": {
                "bfs": {
                    "visited_cells": b_st["visited_count"],
                    "visited_pct": round((b_st["visited_count"] / total_cells) * 100, 1),
                    "buffer_size": b_st["queue_size"],
                    "wave_level": b_st["wave_level"],
                    "directions": b_st["dir_counts"]
                },
                "dfs": {
                    "visited_cells": d_st["visited_count"],
                    "visited_pct": round((d_st["visited_count"] / total_cells) * 100, 1),
                    "buffer_size": d_st["stack_size"],
                    "stack_depth": d_st["depth"],
                    "backtracks": d_st["backtrack_count"],
                    "directions": d_st["dir_counts"]
                }
            },
            "buffer_ratio": {
                "bfs_queue_ratio": round(b_st["queue_size"] / max(1, bfs_peak_queue), 3),
                "dfs_stack_ratio": round(d_st["stack_size"] / max(1, dfs_peak_stack), 3)
            }
        }
        metadata = {
            "step_id": step_idx + 1,
            "bfs_done": step_idx >= len(bfs_history) - 1,
            "dfs_done": step_idx >= len(dfs_history) - 1,
            "time_complexity": {
                "bfs": {"notation": "O(V + E)", "cumulative_operations": bfs_ops, "theoretical_max": total_cells * 4},
                "dfs": {"notation": "O(V + E)", "cumulative_operations": dfs_ops, "theoretical_max": total_cells * 4}
            },
            "space_complexity": {
                "bfs": {"notation": "O(V) [Queue Capacity]", "current_buffer_nodes": b_st["queue_size"], "peak_buffer_nodes": bfs_peak_queue, "est_memory_kb": round((b_st["queue_size"] * 64 + b_st["visited_count"] * 32) / 1024, 2)},
                "dfs": {"notation": "O(h) [Stack Depth]", "current_buffer_nodes": d_st["stack_size"], "peak_buffer_nodes": dfs_peak_stack, "est_memory_kb": round((d_st["stack_size"] * 48 + d_st["visited_count"] * 24) / 1024, 2)}
            }
        }
        synchronized_steps.append({"step_id": step_idx + 1, "bfs_state": b_st, "dfs_state": d_st, "histogram": histogram_snapshot, "metadata": metadata})

    summary = {
        "dimensions": f"{rows}x{cols}",
        "total_cells": total_cells,
        "bfs": {"found": bfs_found, "path_length": len(bfs_path), "visited_cells": len(bfs_visited), "visited_pct": round((len(bfs_visited) / total_cells) * 100, 1), "peak_queue_nodes": bfs_peak_queue, "execution_time_ms": bfs_duration_ms, "optimality": "Optimal (Shortest Path)"},
        "dfs": {"found": dfs_found, "path_length": len(dfs_path), "visited_cells": len(dfs_visited), "visited_pct": round((len(dfs_visited) / total_cells) * 100, 1), "peak_stack_depth": dfs_peak_stack, "backtracks": dfs_backtracks, "execution_time_ms": dfs_duration_ms, "optimality": f"+{round(((len(dfs_path) - len(bfs_path)) / max(1, len(bfs_path))) * 100, 1)}% longer (Non-Optimal)"},
        "comparison": {
            "exploration_efficiency": {"bfs_visited": len(bfs_visited), "dfs_visited": len(dfs_visited), "less_visited_algorithm": "DFS" if len(dfs_visited) < len(bfs_visited) else "BFS", "diff_pct": round(abs(len(bfs_visited) - len(dfs_visited)) / max(1, len(bfs_visited)) * 100, 1)},
            "path_optimality": {"bfs_length": len(bfs_path), "dfs_length": len(dfs_path), "diff_steps": len(dfs_path) - len(bfs_path)},
            "memory_efficiency": {"bfs_peak_nodes": bfs_peak_queue, "dfs_peak_nodes": dfs_peak_stack, "ratio": round(bfs_peak_queue / max(1, dfs_peak_stack), 2)}
        }
    }
    return {"grid": grid, "start": start, "end": end, "bfs_path": bfs_path, "dfs_path": dfs_path, "summary": summary, "steps": synchronized_steps}

@app.get("/health")
def health_check():
    return {"status": "online", "service": "ALGO-MAZE Dual Path Engine", "version": "2.4.0", "supported_algorithms": ["BFS", "DFS"], "timestamp": time.time()}

@app.post("/api/maze/generate")
def api_generate_maze(config: MazeConfig):
    start_time = time.perf_counter()
    grid = generate_perfect_maze(config.height, config.width, config.seed)
    return {"status": "success", "width": len(grid[0]), "height": len(grid), "grid": grid, "generation_time_ms": round((time.perf_counter() - start_time) * 1000, 2)}

@app.post("/api/maze/solve")
def api_solve_maze(req: SolveRequest):
    rows = len(req.grid)
    cols = len(req.grid[0])
    end = req.end if req.end is not None else [rows - 1, cols - 1]
    return {"status": "success", **solve_dual_maze(req.grid, req.start, end)}

@app.post("/api/maze/dual-run")
def api_dual_run(config: MazeConfig):
    grid = generate_perfect_maze(config.height, config.width, config.seed)
    start = [0, 0]
    end = [len(grid) - 1, len(grid[0]) - 1]
    return {"status": "success", **solve_dual_maze(grid, start, end)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
