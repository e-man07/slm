FROM python:3.11-slim

WORKDIR /app

RUN apt-get update -qq && apt-get install -y -qq git > /dev/null 2>&1 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY anchor_patterns.md .

EXPOSE 8080

CMD ["python", "app.py"]
