FROM python:3.11-slim-bullseye

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# The port Gunicorn will listen on inside the container.
# Coolify will map traffic from the outside world (port 443) to this port.
EXPOSE 8015

# Command to run the Gunicorn production server for our FastAPI app.
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8015", "app.main:app"]