from fastapi import FastAPI, Header, HTTPException, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import re
import uvicorn
from asyncio import sleep

active_connections: dict[str,WebSocket] = {}

limiter = Limiter(get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded,_rate_limit_exceeded_handler) #type: ignore

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"]
)

grid = [['#000000' for _ in range(20)] for _ in range(20)]

@app.post('/api/changegrid')
@limiter.limit('5/second')
async def change_grid(request: Request, row: int = Header(...), column: int = Header(...), color: str = Header(...)):
	if not re.match(r'^#(?:[0-9a-fA-F]{3}){1,2}$',color):
		raise HTTPException(status_code=400,detail={'error':'Hex not valid'})
	grid[row][column] = color
	return {'status':'ok'}

@app.websocket('/api/ws')
async def websocket_endpoint(websocket: WebSocket):
	if not websocket.client:
		return await websocket.close()
	await websocket.accept()
	active_connections[websocket.client.host] = websocket
	print(f'Got WebSocket connection. Users: {len(active_connections)}')
	try:
		while True:
			await sleep(1)
			for _,conn in list(active_connections.items()).copy():
				try:
					await conn.send_json({'grid':grid})
				except Exception as e:
					active_connections.pop(websocket.client.host,None)
					print(e)
	finally:
		active_connections.pop(websocket.client.host,None)
		print(f'Connection lost. Users {len(active_connections)}')
		await websocket.close()

if __name__ == '__main__':
	print('Starting API.')
	uvicorn.run(app=app,host='0.0.0.0',port=7171)