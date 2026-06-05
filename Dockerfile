# Use the official pre-configured Playwright & Python production image
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Set up the internal work folder
WORKDIR /app

# Copy dependencies and install them cleanly
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all script modules over
COPY . .

# Expose the network port FastAPI listens on
EXPOSE 10000

# Fire up the Uvicorn lightweight web server gateway
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
