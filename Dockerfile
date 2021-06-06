FROM python:3.9

LABEL maintainer="Armaan Tobaccowalla"

WORKDIR /app/

COPY requirements.txt /app/

RUN pip install -r requirements.txt

COPY . /app/

CMD ["python", "/app/pfSenseInfluxCollector.py", "--config", "/app/config/settings.conf"]
