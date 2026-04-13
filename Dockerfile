# step 1: Start with the official python 3.11 image 
FROM python:3.11-slim

# Step 2: Set a "working directory" inside the container
# All our commands will be run from here
WORKDIR /app

# Step 3: Copy just the requirements file in first
COPY requirements.txt .

# Step 4: Install all your Python libraries
RUN pip install  --no-cache-dir -r requirements.txt

# Step 5: Copy your *entire* app code into the  container
# This copies the '/app' folder into the container's '/app' folder
COPY ./app ./app
COPY ./templates ./templates

# Step 6: Expose port 8000
# This tells Docker that your app *inside* the container
# will listen on port 8000
EXPOSE 8000

# Step 7: The command to run the app
# This is what runs when the container starts.
# --host 0.0.0.0 is critical: it tells Uvicorn to listen
# on all network interface, not just localhost.
CMD [ "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]