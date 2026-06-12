# 记账小助手 - WSL2 端口转发（管理员身份运行）
# 解决局域网其他设备无法访问 WSL2 内服务的问题
# 用法: PowerShell(管理员) > powershell -ExecutionPolicy Bypass -File wsl-port-forward.ps1

# 设置 UTF-8 编码，防止中文/emoji 乱码
$OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8
chcp 65001 >$null

$port = 8000
$ruleName = "Bookkeeper LAN Access (TCP $port)"

# 获取 WSL 实例的 IP 地址
$wslIp = (wsl.exe hostname -I).Trim().Split(' ')[0]
if (-not $wslIp) {
    Write-Host "[ERROR] 无法获取 WSL IP 地址" -ForegroundColor Red
    exit 1
}
Write-Host "[INFO] WSL IP: $wslIp" -ForegroundColor Cyan

# 1. 检查/创建防火墙入站规则
$existingRule = netsh advfirewall firewall show rule name="$ruleName" 2>$null
if (-not ($existingRule -match $ruleName)) {
    netsh advfirewall firewall add rule name="$ruleName" dir=in action=allow protocol=TCP localport=$port
    Write-Host "[OK] 防火墙规则已添加" -ForegroundColor Green
} else {
    Write-Host "[OK] 防火墙规则已存在" -ForegroundColor Green
}

# 2. 设置端口转发（Windows -> WSL）
netsh interface portproxy delete v4tov4 listenport=$port 2>$null
netsh interface portproxy add v4tov4 listenport=$port connectaddress=$wslIp connectport=$port
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] 端口转发已设置: :$port -> $wslIp`:$port" -ForegroundColor Green
} else {
    Write-Host "[ERROR] 端口转发设置失败" -ForegroundColor Red
    exit 1
}

# 3. 显示当前转发规则
Write-Host ""
Write-Host "=== 当前端口转发规则 ===" -ForegroundColor Yellow
netsh interface portproxy show all

# 4. 获取 Windows 主机 IP
$hostIp = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
    $_.IPAddress -notmatch '^127\.' -and $_.InterfaceAlias -notmatch 'Loopback|vEthernet.*WSL'
} | Select-Object -First 1).IPAddress
if ($hostIp) {
    Write-Host ""
    Write-Host "局域网访问地址: http://${hostIp}:$port" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "如需删除转发规则，执行:" -ForegroundColor Yellow
Write-Host "   netsh interface portproxy delete v4tov4 listenport=$port"
