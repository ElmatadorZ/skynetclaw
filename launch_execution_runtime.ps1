# ==========================================
#  launch_execution_runtime.ps1
#  OX-EXECUTION-RECOVERY-FINAL — GPU execution runtime
# ==========================================
# Starts the llama.cpp GPU server that backs THE HOUSE execution path.
# Model: Qwen2.5-14B (served under the alias "ElmatadorZ"). Stock-llama.cpp
# compatible; the bigger 14B understands tools / search / analysis far better
# than the 7B while still fitting the RTX 3060 (12GB) with flash-attention.
# Endpoint: http://127.0.0.1:8080/v1  (OpenAI-compatible, connection 'execution').

$ErrorActionPreference = "Stop"
$Root  = "C:\Users\judgm\llamacpp_test"
$Exe   = Join-Path $Root "llama-server.exe"
$Model = Join-Path $Root "qwen25-14b.gguf"   # fallback to 7B if 14B missing
if (-not (Test-Path $Model)) { $Model = Join-Path $Root "qwen25-7b.gguf" }
$Alias = "ElmatadorZ"
$Port  = 8080
$Ctx   = 16384   # 14B + flash-attn KV fits 12GB at 16k; covers ~12k council prompts

if (-not (Test-Path $Exe))   { Write-Host "MISSING: $Exe" -ForegroundColor Red; exit 1 }
if (-not (Test-Path $Model)) { Write-Host "MISSING: $Model" -ForegroundColor Red; exit 1 }

# --parallel 1: THE HOUSE serves one request at a time, but llama-server defaults
# to 4 slots, each reserving a full n_ctx KV cache (~4x KV VRAM). That pushed the
# 14B+16k to 95% of the 12GB card (measured 11.6GB) and caused intermittent OOM
# crashes (the ':8080 dies repeatedly' root cause). One slot keeps the full 16k
# context per request and frees ~2.4GB of headroom → durable stability.
Write-Host "Launching execution runtime: $Alias (Qwen2.5-14B) on GPU (-ngl 99, --jinja, -fa, -c $Ctx, --parallel 1) :$Port"
& $Exe -m $Model -ngl 99 --jinja --flash-attn on --host 127.0.0.1 --port $Port -c $Ctx --parallel 1 --alias $Alias --no-warmup
