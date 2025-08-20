from fastapi import FastAPI, Header, HTTPException, Request, WebSocket, Response
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, PlainTextResponse
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
	global grid, website_html, zip_bomb, favicon
	with open('index.html','r') as f:
		website_html = f.read()
	with open('funnyfile.gzip','rb') as f:
		zip_bomb = f.read()
	with open('favicon.ico','rb') as f:
		favicon = f.read()
	async with asqlite.create_pool('grid.db') as pool:
		async with pool.acquire() as conn:
			await conn.execute('CREATE TABLE IF NOT EXISTS grid (color TEXT)')
			result = await conn.fetchone('SELECT color FROM grid')
			if not result:
				grid = [['#000000' for _ in range(20)] for _ in range(20)]
				await conn.execute('INSERT INTO grid VALUES (?)',(json.dumps(grid),))
				await conn.commit()
			else:
				grid = json.loads(result[0])
		yield
		async with pool.acquire() as conn:
			await conn.execute('UPDATE grid SET color = ?',(json.dumps(grid),))
			await conn.commit()

limiter = Limiter(get_remote_address)
app = FastAPI(lifespan=lifespan,openapi_url=None)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded,_rate_limit_exceeded_handler) #type: ignore

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"]
)

@app.get('/',response_class=HTMLResponse)
async def website():
	return website_html

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

@app.get('/favicon.ico')
async def icon(request: Request):
	return Response(content=favicon,media_type='image/x-icon')

#don't send zipbomb to good bots that respect robots.txt
@app.get('/robots.txt',response_class=PlainTextResponse)
async def robots(request: Request):
	return """User-agent: *
Disallow: /
Allow: /$
			"""

#f*ck everyone else
@app.api_route('/{path:path}',methods=['GET','POST','PUT','PATCH','DELETE'],response_class=HTMLResponse)
async def zipbomb(request: Request, path: str):
	headers = {
			"Content-Encoding": "gzip",
			"Content-Length": str(len(zip_bomb)),
			"Content-Type": "text/plain; charset=utf-8"
			}
	return StreamingResponse(stream_bomb(),headers=headers)

async def stream_bomb():
	for i in range(0, len(zip_bomb), 8192):
		yield zip_bomb[i:i+8192]
