FROM python:3.12.1-alpine3.19
WORKDIR /app
RUN apk add --no-cache curl

COPY requirements.txt requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

ENV SERVER_PORT=8080
CMD ["sh", "-c", "exec python3 -m uvicorn app:app --host=0.0.0.0 --port=${SERVER_PORT}"]