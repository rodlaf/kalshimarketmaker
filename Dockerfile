# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Make port 8080 available to the world outside this container
EXPOSE 8080

# Run mm.py when the container launches
CMD ["python", "mm.py", "--config", "config.yaml", "--config-name", "default", "--log-level", "INFO", "--trade-side", "yes"]