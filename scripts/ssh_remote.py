#!/usr/bin/env python3
"""paramiko 远程 SSH 执行 + 文件传输工具 (Windows 本机无 sshpass 时用)

用法:
  python ssh_remote.py <host> <port> <user> <password> <command> [timeout]
      执行远程命令并打印 stdout/stderr
  python ssh_remote.py <host> <port> <user> <password> --upload <local> <remote>
      本地上传到远程 (SFTP)
  python ssh_remote.py <host> <port> <user> <password> --download <remote> <local>
      远程下载到本地 (SFTP)

注意:
  - 依赖 paramiko (pip install paramiko)
  - 远程需 root / sudo 时, 命令里包 `sudo -S bash -c '...'` 并在 stdin 喂密码
  - 大文件 (如 ASF.db 数百 KB) 的 base64 中转会超过 PTY 缓冲, 用 SFTP 而非 base64
"""
import sys
import paramiko


def ssh_connect(host, port, user, password, timeout=30):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, port=int(port), username=user,
                   password=password, timeout=timeout, allow_agent=False)
    return client


def run_cmd(host, port, user, password, cmd, timeout=30):
    client = ssh_connect(host, port, user, password)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    client.close()
    sys.stdout.write(out)
    if err:
        sys.stderr.write(err)


def upload(host, port, user, password, local, remote):
    client = ssh_connect(host, port, user, password)
    sftp = client.open_sftp()
    sftp.put(local, remote)
    sftp.close()
    client.close()
    print(f"uploaded {local} -> {remote}")


def download(host, port, user, password, remote, local):
    client = ssh_connect(host, port, user, password)
    sftp = client.open_sftp()
    sftp.get(remote, local)
    sftp.close()
    client.close()
    print(f"downloaded {remote} -> {local}")


if __name__ == "__main__":
    args = sys.argv[1:]
    host, port, user, password = args[0], args[1], args[2], args[3]
    rest = args[4:]
    if rest[0] == "--upload":
        upload(host, port, user, password, rest[1], rest[2])
    elif rest[0] == "--download":
        download(host, port, user, password, rest[1], rest[2])
    else:
        cmd = rest[0]
        timeout = int(rest[1]) if len(rest) > 1 else 30
        run_cmd(host, port, user, password, cmd, timeout)
