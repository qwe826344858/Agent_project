#!/usr/bin/env python3
"""通过 paramiko SSH 执行远程命令"""
import sys
import paramiko

def run(cmd: str):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect("192.168.2.66", username="yunxigu", password="yunxigu2025")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=120)
    out = stdout.read().decode()
    err = stderr.read().decode()
    code = stdout.channel.recv_exit_status()
    client.close()
    if out:
        print(out, end="")
    if err:
        print(err, end="", file=sys.stderr)
    sys.exit(code)

if __name__ == "__main__":
    run(sys.argv[1])
