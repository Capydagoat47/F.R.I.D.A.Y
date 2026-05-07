@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=%~dp0friday_env\Scripts\python.exe"
set "NGROK_EXE=C:\Users\forho\AppData\Local\Microsoft\WinGet\Packages\Ngrok.Ngrok_Microsoft.Winget.Source_8wekyb3d8bbwe\ngrok.exe"

echo Starting FRIDAY local server...
start "FRIDAY Server" cmd /k ""%PYTHON_EXE%" "%~dp0server.py""

echo Waiting for local server...
timeout /t 5 /nobreak >nul

echo Starting ngrok public tunnel...
start "FRIDAY Ngrok" cmd /k ""%NGROK_EXE%" http 5000"

echo Waiting for public link...
timeout /t 8 /nobreak >nul

powershell -NoProfile -Command ^
  "try { " ^
  "  $response = Invoke-WebRequest -Uri 'http://127.0.0.1:4040/api/tunnels' -UseBasicParsing; " ^
  "  $json = $response.Content | ConvertFrom-Json; " ^
  "  $url = $json.tunnels[0].public_url; " ^
  "  if ($url) { " ^
  "    Write-Host ''; " ^
  "    Write-Host 'Public FRIDAY link:' -ForegroundColor Cyan; " ^
  "    Write-Host $url -ForegroundColor Green; " ^
  "    Start-Process $url; " ^
  "  } else { " ^
  "    Write-Host 'Ngrok started, but no public URL was found yet.' -ForegroundColor Yellow; " ^
  "  } " ^
  "} catch { " ^
  "  Write-Host 'Could not fetch the ngrok public link yet.' -ForegroundColor Red; " ^
  "}"

echo.
echo Keep both FRIDAY Server and FRIDAY Ngrok windows open.
pause
