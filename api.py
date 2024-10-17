from fastapi import FastAPI, Header, HTTPException, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import re
import uvicorn
from asyncio import sleep
import asqlite
import json

@asynccontextmanager
async def lifespan(app: FastAPI):
	global grid
	pool = await asqlite.create_pool('grid.db')
	async with pool.acquire() as conn:
		await conn.execute('CREATE TABLE IF NOT EXISTS grid (color TEXT)')
		result = await conn.fetchone('SELECT color FROM grid')
		if not result:
			grid = [['#000000' for _ in range(20)] for _ in range(20)]
			await conn.execute('INSERT INTO grid VALUES (?)',json.dumps(grid))
		else:
			grid = json.loads(result[0])
	yield
	async with pool.acquire() as conn:
		await conn.execute('UPDATE grid SET color = ?',json.dumps(grid))

limiter = Limiter(get_remote_address)
app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded,_rate_limit_exceeded_handler) #type: ignore

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"]
)

@app.post('/api/changegrid')
@limiter.limit('5/second')
async def change_grid(request: Request, row: int = Header(...), column: int = Header(...), color: str = Header(...)):
	if not re.match(r'^#(?:[0-9a-fA-F]{3}){1,2}$',color):
		raise HTTPException(status_code=400,detail={'error':'Hex not valid'})
	if not (0 <= row <= 20) or not (0 <= column <= 20):
		raise HTTPException(status_code=400,detail={'error':'Out of range'})
	grid[row][column] = color
	return {'status':'ok'}

@app.websocket('/api/ws')
async def websocket_endpoint(websocket: WebSocket):
	await websocket.accept()
	print('Got WebSocket connection')
	try:
		while True:
			await sleep(1)
			await websocket.send_json({'grid':grid})
	except: ...
	finally:
		print('Connection lost')

if __name__ == '__main__':
	print('Starting API.')
	uvicorn.run(app=app,host='0.0.0.0',port=7171)