FROM python:3.11-bookworm

RUN apt-get update && apt-get install -y gnucobol build-essential 

WORKDIR /app

CMD ["bash", "./run.sh"]