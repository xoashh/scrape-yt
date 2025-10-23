FROM apify/actor-python:latest

# Copy local files to container
COPY . .

# Install Python dependencies including Playwright
RUN pip install --upgrade pip && pip install -r requirements.txt

# Install Playwright browsers with dependencies
RUN python -m playwright install --with-deps chromium

# Command to run your scraper
CMD ["python", "main.py"]
