FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py config.py ./
COPY prompts ./prompts
COPY schemas ./schemas

CMD ["python", "app.py"]
