# Chronica MCP Server
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY run_server.py .

# Set Python path
ENV PYTHONPATH=/app/src

# Run MCP server
CMD ["python", "run_server.py"]
