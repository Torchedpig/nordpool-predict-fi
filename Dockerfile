FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN apt-get update && \
    apt-get install -y tzdata && \
    pip install --no-cache-dir -r requirements.txt && \
    rm -rf /var/lib/apt/lists/*

# Timezone for the container (default: Europe/Helsinki)
ENV TZ=Europe/Helsinki

# Copy the rest of the project
COPY . .

# Make entrypoint script executable
RUN chmod +x entrypoint.sh

EXPOSE 80

CMD ["/bin/bash", "./entrypoint.sh"]