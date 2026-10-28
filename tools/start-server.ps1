# Start the local translation server (llama.cpp) on 127.0.0.1:8080.
# Listens on localhost only; 4 parallel slots; whole model on the GPU.
# Model: path in model.txt (one line, relative to this folder) if present,
# otherwise the Sakura translation model.
$root = $PSScriptRoot
$exe  = Join-Path $root 'llama\llama-server.exe'
$model = Join-Path $root 'models\sakura-14b-qwen2.5-v1.0-iq4xs.gguf'
$pick = Join-Path $root 'model.txt'
if (Test-Path $pick) { $model = Join-Path $root ((Get-Content $pick -TotalCount 1).Trim()) }
Write-Host "model: $model"
& $exe -m $model --host 127.0.0.1 --port 8080 -ngl 99 -c 8192 -np 4 --cont-batching --log-disable
