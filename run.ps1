Write-Host "Starting Ollama service..." -ForegroundColor Green
docker compose up -d ollama

Write-Host "Waiting for Ollama to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

Write-Host "Pulling gemma3:1b model..." -ForegroundColor Green
docker exec -it ollama ollama pull gemma3:1b

Write-Host "Starting the application..." -ForegroundColor Green
docker compose up app

Write-Host "Done!" -ForegroundColor Green
