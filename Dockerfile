FROM python:3.11-alpine

WORKDIR /app

RUN pip install fastapi[standard] asqlite slowapi uvicorn
RUN pip install uvicorn[standard]

COPY . .

EXPOSE 7171

CMD ["fastapi", "run", "app/api.py", "--port", "7171"]
