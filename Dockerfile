FROM python:3.12-alpine

WORKDIR /app

COPY . /app

RUN chmod -R 755 /app

ENV PORT=8085
EXPOSE 8085

CMD ["python", "server.py"]
