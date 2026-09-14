$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$statePath = Join-Path $PSScriptRoot 'connection.json'
$lock = $null
function Call-Telegram($method, $payload) {
    try {
        $body = [Text.Encoding]::UTF8.GetBytes(($payload | ConvertTo-Json -Depth 8 -Compress))
        $response = Invoke-RestMethod -Uri ('https://api.telegram.org/bot' + $script:token + '/' + $method) -Method Post -ContentType 'application/json; charset=utf-8' -Body $body -TimeoutSec 40
        if (-not $response.ok) { throw 'API failure' }
        return $response.result
    } catch {
        # Never display the exception: its URL may contain the token.
        throw 'Ошибка Telegram. Проверьте интернет, токен и отсутствие другой запущенной копии бота.'
    }
}
function Save-State {
    $state | ConvertTo-Json | Set-Content -LiteralPath ($statePath + '.tmp') -Encoding UTF8
    Move-Item -LiteralPath ($statePath + '.tmp') -Destination $statePath -Force
}
try {
    $lock = [IO.File]::Open((Join-Path $PSScriptRoot 'bot.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    Write-Host 'Администратор БРБ. Для остановки закройте окно или нажмите Ctrl+C.'
    $secret = Read-Host 'Вставьте токен BotFather (ввод скрыт), затем Enter' -AsSecureString
    $credential = New-Object System.Management.Automation.PSCredential('bot', $secret)
    $script:token = $credential.GetNetworkCredential().Password
    if ($script:token -notmatch '^\d+:[A-Za-z0-9_-]+$') { throw 'Неверный формат токена. Запустите программу повторно и скопируйте токен целиком.' }
    $me = Call-Telegram 'getMe' @{}
    if ($me.username -ne 'brb_team_admin_bot') { throw 'Токен принадлежит другому боту. Нужен @brb_team_admin_bot.' }
    $webhook = Call-Telegram 'getWebhookInfo' @{}
    if ($webhook.url) { throw 'У бота уже настроено другое подключение (webhook). Сначала сообщите об этом в рабочем чате Codex.' }
    $state = [pscustomobject]@{ chat_id = $null; offset = 0 }
    if (Test-Path -LiteralPath $statePath) { $state = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json }
    $pairCode = [Guid]::NewGuid().ToString('N')
    $pairExpires = (Get-Date).AddMinutes(15)
    if (-not $state.chat_id) {
        Write-Host "Откройте нужную группу и отправьте следующую строку (действует 15 минут):" -ForegroundColor Cyan
        Write-Host "/connect@brb_team_admin_bot $pairCode" -ForegroundColor Green
    } else { Write-Host 'Группа уже привязана. Отправьте /ping@brb_team_admin_bot в Telegram.' }
    # Read a plain .NET string: Windows PowerShell attaches file-provider
    # metadata to Get-Content output, which ConvertTo-Json can expand deeply.
    $team = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'team.txt'), [Text.Encoding]::UTF8)
    while ($true) {
        try {
            $updates = @(Call-Telegram 'getUpdates' @{ offset = $state.offset; timeout = 25; allowed_updates = @('message') })
            foreach ($update in $updates) {
                $m = $update.message
                $reply = $null
                if ($m -and $m.text -and $m.chat.type -in @('group', 'supergroup')) {
                    if (-not $state.chat_id -and (Get-Date) -lt $pairExpires -and $m.text -ceq "/connect@brb_team_admin_bot $pairCode") {
                        Write-Host ('Запрос подключения группы: ' + $m.chat.title)
                        $confirmation = Read-Host 'Это ваша рабочая группа? Для подключения введите ДА'
                        if ($confirmation -ceq 'ДА') {
                            $state.chat_id = [long]$m.chat.id
                            Save-State
                            $reply = 'Группа подключена. Доступны /ping, /team, /help. Календарь и автоматические рассылки пока не подключены.'
                        }
                    } elseif ($state.chat_id -and [long]$m.chat.id -eq [long]$state.chat_id) {
                        if ($m.text -match '^/(ping|team|help|start)(?:@brb_team_admin_bot)?\s*$') {
                            switch ($Matches[1].ToLowerInvariant()) {
                                'ping' { $reply = 'На связи. Планирование: 2026–2027 годы.' }
                                'team' { $reply = $team }
                                default { $reply = "Администратор БРБ — проверка подключения.`n/ping — проверить связь`n/team — состав команды`n/help — помощь`n`nКалендарь, ИИ-ответы и рассылки будут добавлены следующим этапом." }
                            }
                        }
                    }
                }
                if ($reply) { $null = Call-Telegram 'sendMessage' @{ chat_id = $m.chat.id; text = $reply } }
                $state.offset = [long]$update.update_id + 1
                Save-State
            }
        } catch {
            Write-Host 'Не удалось обработать запрос. Проверьте интернет и права бота. Повтор через 5 секунд.' -ForegroundColor Yellow
            Start-Sleep -Seconds 5
        }
    }
} catch {
    if ($null -eq $lock) { Write-Host 'Не удалось открыть папку или бот уже запущен.' -ForegroundColor Red }
    else { Write-Host $_.Exception.Message -ForegroundColor Red }
} finally {
    $script:token = $null
    $credential = $null
    if ($secret) { $secret.Dispose() }
    if ($lock) { $lock.Dispose() }
}
