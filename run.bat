@echo off
echo Starting Ollama service...
docker compose up -d ollama

echo Waiting for Ollama to be ready...
timeout /t 30 /nobreak > nul

echo Pulling gemma3:1b model...
docker exec -it ollama ollama pull gemma3:1b

echo Starting the application...
docker compose up app --build

echo Done! Check the Collection folders for output JSON files.