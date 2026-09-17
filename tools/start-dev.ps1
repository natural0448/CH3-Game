param(
    [ValidateSet('all', 'kafka1', 'kafka2', 'kafka3', 'spark-master', 'spark-worker1', 'spark-worker2')]
    [string]$Service = 'all',
    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$sparkRoot = Join-Path (Split-Path -Parent $projectRoot) 'Oder-insight/Spark-exam/spark-4.1.3-bin-hadoop3-1'
$sparkClass = Join-Path $sparkRoot 'bin/spark-class.cmd'
$scriptPath = $PSCommandPath
$powershellPath = Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
$servicePorts = [ordered]@{
    'kafka1' = @(9092, 9093)
    'kafka2' = @(9094, 9095)
    'kafka3' = @(9096, 9097)
    'spark-master' = @(7077, 8080)
    'spark-worker1' = @(7078, 8081)
    'spark-worker2' = @(7079, 8082)
}

function Test-Listening([int]$Port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $connection = $client.ConnectAsync('127.0.0.1', $Port)
        return ($connection.Wait(400) -and $client.Connected)
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Test-ServicePortInUse([string]$Name) {
    foreach ($port in $servicePorts[$Name]) {
        if (Test-Listening $port) {
            Write-Host "$Name port $port is in use; skipped. Verify the existing terminal."
            return $true
        }
    }
    return $false
}

function Confirm-Files {
    $required = @($sparkClass, (Join-Path $sparkRoot 'jars'), (Join-Path $PSScriptRoot 'kafka.ps1'))
    foreach ($nodeNumber in 1..3) {
        $required += Join-Path $projectRoot "infra/kafka/node$nodeNumber.properties"
        $required += Join-Path $projectRoot "data/kafka/node$nodeNumber/meta.properties"
    }
    $required += Join-Path $projectRoot 'infra/runtime/kafka_2.13-4.1.2/libs'
    foreach ($path in $required) {
        if (-not (Test-Path -LiteralPath $path)) { throw "Required path missing: $path" }
    }
    $null = Get-Command java -ErrorAction Stop
}

# One launcher/service owner per checkout. Repeated clicks cannot create duplicate children.
$hasher = [System.Security.Cryptography.SHA256]::Create()
try {
    $rootId = [BitConverter]::ToString($hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($projectRoot.ToLowerInvariant()))).Replace('-', '').Substring(0, 16)
} finally { $hasher.Dispose() }
$mutex = New-Object System.Threading.Mutex($false, "Local\VillageDev-$rootId-$Service")
$locked = $false
try {
    try { $locked = $mutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $locked = $true }
    if (-not $locked) { Write-Host "$Service already has a launcher window. Skipped."; return }
    Confirm-Files
    if ($CheckOnly) {
        Write-Host "Spark: $sparkRoot"
        foreach ($name in $servicePorts.Keys) {
            if (-not (Test-ServicePortInUse $name)) { Write-Host "$name ports are free." }
        }
        Write-Host 'Kafka/Spark files and Java command found. No services were started.'
        return
    }

    if ($Service -eq 'all') {
        foreach ($name in $servicePorts.Keys) {
            if (Test-ServicePortInUse $name) { continue }
            # Visible windows were requested; no hidden background server is created.
            Start-Process -FilePath $powershellPath -WorkingDirectory $projectRoot -WindowStyle Normal -ArgumentList @(
                '-NoProfile', '-NoExit', '-ExecutionPolicy', 'Bypass',
                '-File', ('"{0}"' -f $scriptPath), '-Service', $name
            ) | Out-Null
            Write-Host "Opened $name. Check its window for readiness or errors."
        }
        Write-Host 'Stop Spark jobs first, then Workers/Master and Kafka with Ctrl+C in their windows.'
        return
    }

    $Host.UI.RawUI.WindowTitle = "Game-server | $Service"
    Set-Location -LiteralPath $projectRoot
    Write-Host "Starting $Service. Keep this window open. Stop with Ctrl+C."
    if (Test-ServicePortInUse $Service) { return }
    if ($Service -like 'kafka*') {
        $nodeNumber = [int]$Service.Substring(5)
        & (Join-Path $PSScriptRoot 'kafka.ps1') -Action start -Node $nodeNumber
    } else {
        # Only these child PowerShell environments change, never the user's global settings.
        $env:SPARK_HOME = $sparkRoot
        $env:SPARK_CONF_DIR = Join-Path $sparkRoot 'conf'
        Set-Location -LiteralPath $sparkRoot
        if ($Service -eq 'spark-master') {
            & $sparkClass org.apache.spark.deploy.master.Master --host 127.0.0.1 --port 7077 --webui-port 8080
        } else {
            Write-Host 'Waiting up to 90 seconds for Spark Master port 7077...'
            $deadline = [DateTime]::UtcNow.AddSeconds(90)
            while (-not (Test-Listening 7077)) {
                if ([DateTime]::UtcNow -ge $deadline) { throw 'Spark Master is not ready. Check its window, then run start-dev.cmd again.' }
                Start-Sleep -Seconds 1
            }
            $workerNumber = [int]$Service.Substring($Service.Length - 1)
            $workerPort = 7077 + $workerNumber
            $webPort = 8080 + $workerNumber
            $workPath = Join-Path $sparkRoot "work/worker-$workerNumber"
            & $sparkClass org.apache.spark.deploy.worker.Worker --host 127.0.0.1 --port $workerPort --webui-port $webPort --cores 1 --memory 2g --work-dir $workPath spark://127.0.0.1:7077
        }
    }
    if ($LASTEXITCODE -ne 0) { throw "$Service exited with code $LASTEXITCODE. Check the error above." }
} finally {
    if ($locked) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
