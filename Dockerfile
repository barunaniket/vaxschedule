FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV HOST=0.0.0.0 \
    DATABASE=/app/data/vaccination.db
RUN mkdir -p /app/data
EXPOSE 5000
CMD ["python", "run.py", "--seed"]
