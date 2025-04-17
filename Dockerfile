
FROM mcr.microsoft.com/playwright/python:v1.50.0-jammy
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
ENTRYPOINT ["/app/entrypoint.sh"]
