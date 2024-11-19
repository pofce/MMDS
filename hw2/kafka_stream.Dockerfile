FROM python:3.9-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r /app/requirements.txt

RUN chmod +x /app/kafka_stream.py

CMD ["python", "kafka_stream.py"]
