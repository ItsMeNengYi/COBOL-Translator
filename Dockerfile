FROM python:3.11-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y gnucobol build-essential 

WORKDIR /app

COPY requirements.txt /app/
RUN --mount=type=cache,id=pip-cache,target=/root/.cache/pip \
    pip install --default-timeout=1000 -r requirements.txt
# RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

EXPOSE 8501

CMD ["bash", "./run.sh"]