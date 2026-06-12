"""WebDAV 备份模块"""
import os
import asyncio
import gzip
import re
import shutil
from datetime import datetime
import aiohttp
import base64


async def backup_to_webdaV(db_path: str, config: dict) -> dict:
    """备份数据库到 WebDAV（gzip 压缩后上传）"""
    try:
        if not os.path.exists(db_path):
            return {"status": "error", "message": "数据库文件不存在"}

        # 读取并压缩数据库文件
        with open(db_path, "rb") as f:
            db_data = f.read()
        compressed = gzip.compress(db_data)
        ratio = (1 - len(compressed) / len(db_data)) * 100 if db_data else 0

        # 生成备份文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"bookkeeper_backup_{timestamp}.db.gz"
        remote_url = config["webdav_url"].rstrip("/") + config["remote_path"].rstrip("/") + "/" + filename

        # 认证头
        auth_str = base64.b64encode(
            f"{config['webdav_user']}:{config['webdav_password']}".encode()
        ).decode()
        headers = {
            "Authorization": f"Basic {auth_str}",
            "Content-Type": "application/octet-stream",
        }

        # 确保远程目录存在
        dir_url = config["webdav_url"].rstrip("/") + config["remote_path"].rstrip("/") + "/"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.request("MKCOL", dir_url, headers=headers) as resp:
                    pass
            except:
                pass

            # PUT 上传压缩文件
            async with session.put(remote_url, data=compressed, headers=headers) as resp:
                if resp.status in (200, 201, 204):
                    log_file = os.path.join(os.path.dirname(db_path), "backup_log.txt")
                    with open(log_file, "a") as f:
                        f.write(f"{datetime.now()}: 备份成功 -> {filename} ({len(compressed)} bytes, 压缩比 {ratio:.0f}%)\n")

                    return {
                        "status": "success",
                        "message": f"备份成功: {filename} (压缩 {ratio:.0f}%)",
                        "file_size": len(compressed),
                        "original_size": len(db_data),
                        "timestamp": datetime.now().isoformat()
                    }
                else:
                    return {"status": "error", "message": f"上传失败: HTTP {resp.status}"}

    except Exception as e:
        return {"status": "error", "message": f"备份失败: {str(e)}"}


async def restore_from_webdaV(db_path: str, config: dict) -> dict:
    """从 WebDAV 恢复备份（自动解压 .gz）"""
    try:
        dir_url = config["webdav_url"].rstrip("/") + config["remote_path"].rstrip("/") + "/"
        auth_str = base64.b64encode(
            f"{config['webdav_user']}:{config['webdav_password']}".encode()
        ).decode()
        headers = {"Authorization": f"Basic {auth_str}"}

        async with aiohttp.ClientSession() as session:
            # PROPFIND 列出文件
            propfind_body = """<?xml version="1.0" encoding="utf-8"?>
            <D:propfind xmlns:D="DAV:">
                <D:prop><D:displayname/><D:getcontentlength/></D:prop>
            </D:propfind>"""

            async with session.request(
                "PROPFIND", dir_url,
                headers={**headers, "Depth": "1"},
                data=propfind_body
            ) as resp:
                if resp.status != 207:
                    return {"status": "error", "message": f"无法列出远程文件: HTTP {resp.status}"}
                text = await resp.text()

            # 匹配 .db 和 .db.gz 文件
            files = re.findall(r'<D:displayname>(bookkeeper_backup_\d+_\d+\.db(?:\.gz)?)</D:displayname>', text)
            if not files:
                return {"status": "error", "message": "未找到备份文件"}

            latest = sorted(files)[-1]
            remote_url = dir_url + latest

            # 下载最新备份
            async with session.get(remote_url, headers=headers) as resp:
                if resp.status != 200:
                    return {"status": "error", "message": f"下载失败: HTTP {resp.status}"}
                data = await resp.read()

            # 如果是 .gz 则解压
            if latest.endswith(".gz"):
                data = gzip.decompress(data)

            # 备份当前数据库
            if os.path.exists(db_path):
                backup_path = f"{db_path}.bak.{datetime.now().strftime('%Y%m%d%H%M%S')}"
                shutil.copy2(db_path, backup_path)

            # 写入恢复的数据库
            with open(db_path, "wb") as f:
                f.write(data)

            return {
                "status": "success",
                "message": f"恢复成功: {latest}",
                "file_size": len(data),
                "timestamp": datetime.now().isoformat()
            }

    except Exception as e:
        return {"status": "error", "message": f"恢复失败: {str(e)}"}


async def get_backup_status(db_path: str) -> dict:
    """获取备份状态"""
    log_file = os.path.join(os.path.dirname(db_path), "backup_log.txt")
    last_backup = None
    if os.path.exists(log_file):
        with open(log_file) as f:
            lines = f.readlines()
            if lines:
                last_backup = lines[-1].strip()

    return {
        "db_size": os.path.getsize(db_path) if os.path.exists(db_path) else 0,
        "last_backup": last_backup
    }
