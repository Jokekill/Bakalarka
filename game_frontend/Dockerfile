# Use a slim Python base image
FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the application code (main.py and app/ package)
COPY . /app

# Expose port 8081 for the game frontend
EXPOSE 8081

# Run the NiceGUI application
CMD ["python", "main.py"]
