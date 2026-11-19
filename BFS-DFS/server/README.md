# ALGO-MAZE BFS vs DFS — Cloud Run Server

> FastAPI-based BFS/DFS Maze Solving Engine deployed on Google Cloud Run.

## Architecture

```
GAS Web App (index.html + Code.gs)
        |
        v
FastAPI (Cloud Run)
  +-- GET  /health
  +-- POST /api/maze/generate
  +-- POST /api/maze/solve
  +-- POST /api/maze/dual-run
```

## Run Locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8080
```

## Run with Docker

```bash
docker build -t algo-maze .
docker run -p 8080:8080 algo-maze
```

## Deploy to Cloud Run

```bash
gcloud run deploy algo-maze \
  --source . \
  --region asia-northeast3 \
  --allow-unauthenticated
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Server status check |
| POST | `/api/maze/generate` | Generate maze (Recursive Backtracker) |
| POST | `/api/maze/solve` | Solve existing maze with BFS + DFS |
| POST | `/api/maze/dual-run` | Generate + solve in one call |

## Algorithms

- **BFS** (Breadth-First Search): FIFO Queue, guarantees shortest path `O(V+E)` / `O(V)`
- **DFS** (Depth-First Search): LIFO Stack, path exists guarantee, not optimal `O(V+E)` / `O(h)`

## Stack

- Python 3.11 / FastAPI 0.110+ / Uvicorn 0.28+ / Pydantic v2
- Google Cloud Run
