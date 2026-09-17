param(
    [ValidateSet('init', 'start', 'status', 'create-topic', 'describe-topic', 'group')]
    [string]$Action = 'status',
    [ValidateRange(1, 3)][int]$Node = 1,
    [string]$Group = 'village-watch-v1'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimePath = Join-Path $projectRoot 'infra/runtime/kafka_2.13-4.1.2'
$dataPath = Join-Path $projectRoot 'data/kafka'
$manifestPath = Join-Path $dataPath 'cluster.json'
$bootstrap = '127.0.0.1:9092,127.0.0.1:9094,127.0.0.1:9096'
if (-not (Test-Path -LiteralPath "$runtimePath/libs")) { throw 'Install Kafka 4.1.2 in infra/runtime first.' }

function Invoke-KafkaJava([string]$Class, [string[]]$Arguments) {
    & java '-Xms128m' '-Xmx384m' "-Dlog4j2.configurationFile=$runtimePath/config/tools-log4j2.yaml" `
        '-cp' "$runtimePath/libs/*" $Class @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Kafka command failed: $Class (exit $LASTEXITCODE)" }
}

switch ($Action) {
    'init' {
        New-Item -ItemType Directory -Force -Path $dataPath | Out-Null
        if (Test-Path -LiteralPath $manifestPath) {
            $cluster = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
        } else {
            foreach ($nodeNumber in 1..3) {
                $nodePath = Join-Path $dataPath "node$nodeNumber"
                if ((Test-Path -LiteralPath $nodePath) -and (Get-ChildItem -LiteralPath $nodePath -Force)) {
                    throw 'Existing Kafka data found without a manifest. Refusing to format it.'
                }
            }
            $ids = @()
            foreach ($index in 1..4) {
                $id = @(Invoke-KafkaJava 'kafka.tools.StorageTool' @('random-uuid') | Where-Object { $_ -match '^[A-Za-z0-9_-]{22}$' })
                if ($id.Count -ne 1) { throw 'Failed to generate one Kafka UUID.' }
                $ids += $id[0]
            }
            $cluster = [pscustomobject]@{
                cluster_id = $ids[0]
                initial_controllers = "1@127.0.0.1:9093:$($ids[1]),2@127.0.0.1:9095:$($ids[2]),3@127.0.0.1:9097:$($ids[3])"
            }
            $cluster | ConvertTo-Json | Set-Content -LiteralPath $manifestPath -Encoding utf8
        }
        foreach ($nodeNumber in 1..3) {
            $metadata = Join-Path $dataPath "node$nodeNumber/meta.properties"
            if (Test-Path -LiteralPath $metadata) {
                $props = ConvertFrom-StringData (Get-Content -LiteralPath $metadata -Raw)
                if ($props['cluster.id'] -ne $cluster.cluster_id -or $props['node.id'] -ne "$nodeNumber") {
                    throw "Existing node $nodeNumber belongs to a different cluster."
                }
                Write-Output "Node $nodeNumber already formatted; retained."
                continue
            }
            Invoke-KafkaJava 'kafka.tools.StorageTool' @('format', '--cluster-id', $cluster.cluster_id,
                '--config', "$projectRoot/infra/kafka/node$nodeNumber.properties",
                '--initial-controllers', $cluster.initial_controllers)
        }
    }
    'start' {
        if (-not (Test-Path -LiteralPath "$dataPath/node$Node/meta.properties")) { throw 'Run -Action init once first.' }
        New-Item -ItemType Directory -Force -Path "$dataPath/logs/node$Node" | Out-Null
        & java '-Xms128m' '-Xmx384m' "-Dkafka.logs.dir=$dataPath/logs/node$Node" `
            "-Dlog4j2.configurationFile=$runtimePath/config/log4j2.yaml" '-cp' "$runtimePath/libs/*" `
            'kafka.Kafka' "$projectRoot/infra/kafka/node$Node.properties"
        if ($LASTEXITCODE -ne 0) { throw "Kafka node $Node exited with $LASTEXITCODE" }
    }
    'status' {
        Invoke-KafkaJava 'org.apache.kafka.tools.MetadataQuorumCommand' @('--bootstrap-server', $bootstrap, 'describe', '--status')
    }
    'create-topic' {
        Invoke-KafkaJava 'org.apache.kafka.tools.TopicCommand' @('--bootstrap-server', $bootstrap, '--create', '--if-not-exists',
            '--topic', 'game.events.v1', '--partitions', '3', '--replication-factor', '3', '--config', 'min.insync.replicas=2')
    }
    'describe-topic' {
        Invoke-KafkaJava 'org.apache.kafka.tools.TopicCommand' @('--bootstrap-server', $bootstrap, '--describe', '--topic', 'game.events.v1')
    }
    'group' {
        Invoke-KafkaJava 'org.apache.kafka.tools.consumer.group.ConsumerGroupCommand' @('--bootstrap-server', $bootstrap, '--describe', '--group', $Group)
    }
}
