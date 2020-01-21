FROM python:3.7-alpine

RUN apk add tzdata

WORKDIR /app

COPY . /app

RUN pip3 install -r requirements.txt

CMD [ "python3", "/app/pfSenseInfluxCollector.py", "--config", "/app/config/settings.conf"]