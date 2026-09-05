FROM python:3.11-slim

WORKDIR /app
COPY src ./src
COPY run_dev_replay.py ./
ENV PYTHONPATH=/app/src
CMD ["python", "-u", "run_dev_replay.py"]
