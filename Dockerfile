FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Render assigns PORT via environment variable
ENV PORT=10000

# Run with gunicorn (production WSGI server)
CMD ["gunicorn", "server:app", "--bind", "0.0.0.0:10000", "--workers", "1", "--timeout", "120"]
