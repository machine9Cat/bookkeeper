@echo off
chcp 65001 >nul
title 记账小助手 - WSL2 端口转发
echo ========================================
echo  记账小助手 - WSL2 端口转发设置
echo  请以管理员身份运行
echo ========================================
echo.

REM 获取 WSL IP
for /f "tokens=1" %%i in ('wsl hostname -I') do set WSL_IP=%%i
if "%WSL_IP%"=="" (
    echo [错误] 无法获取 WSL IP 地址
    pause
    exit /b 1
)
echo [信息] WSL IP: %WSL_IP%

REM 添加防火墙规则
netsh advfirewall firewall add rule name="Bookkeeper LAN Access (TCP 8000)" dir=in action=allow protocol=TCP localport=8000 >nul 2>&1
echo [信息] 防火墙规则已添加

REM 删除旧规则并添加新规则
netsh interface portproxy delete v4tov4 listenport=8000 >nul 2>&1
netsh interface portproxy add v4tov4 listenport=8000 connectaddress=%WSL_IP% connectport=8000
if %errorlevel% equ 0 (
    echo [成功] 端口转发已设置
) else (
    echo [错误] 端口转发设置失败
    pause
    exit /b 1
)

echo.
echo ======== 当前端口转发规则 ========
netsh interface portproxy show all

echo.
echo ================================
echo  局域网访问地址: http://localhost:8000
echo  同网络设备访问: 使用本机局域网 IP:8000
echo ================================
echo.
pause
