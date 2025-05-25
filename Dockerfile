FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project
COPY . .

# Make entrypoint script executable
RUN chmod +x entrypoint.sh

EXPOSE 80

CMD ["/bin/bash", "./entrypoint.sh"]