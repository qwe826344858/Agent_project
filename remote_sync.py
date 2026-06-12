#!/usr/bin/env python3
"""通过 paramiko SFTP 同步前端代码到远程机器"""
import os
import paramiko

LOCAL_BASE = "/home/peiqi/tmp/Agent/apps/frontend"
REMOTE_BASE = "/Users/yunxigu/cc_project/Agent_project/apps/frontend"
EXCLUDES = {".git", "node_modules", ".next", "__pycache__", ".turbo"}

def sync():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect("192.168.2.66", username="yunxigu", password="yunxigu2025")
    sftp = client.open_sftp()

    count = 0
    for root, dirs, files in os.walk(LOCAL_BASE):
        # 排除目录
        dirs[:] = [d for d in dirs if d not in EXCLUDES]

        for f in files:
            local_path = os.path.join(root, f)
            rel_path = os.path.relpath(local_path, LOCAL_BASE)
            remote_path = os.path.join(REMOTE_BASE, rel_path).replace("\\", "/")

            # 确保远程目录存在
            remote_dir = os.path.dirname(remote_path)
            try:
                sftp.stat(remote_dir)
            except FileNotFoundError:
                # 递归创建目录
                parts = remote_dir.split("/")
                for i in range(2, len(parts) + 1):
                    d = "/".join(parts[:i])
                    try:
                        sftp.stat(d)
                    except FileNotFoundError:
                        sftp.mkdir(d)

            sftp.put(local_path, remote_path)
            count += 1

    sftp.close()
    client.close()
    print(f"同步完成：{count} 个文件")

if __name__ == "__main__":
    sync()
