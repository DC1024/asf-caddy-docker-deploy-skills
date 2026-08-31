---
name: asf-caddy-deploy
description: 在任意 Docker 环境（NAS、服务器）部署 ArchiSteamFarm（ASF）挂卡工具，并内置 Steam 社区与 GitHub 反代以绕过 CN 网络 SNI 阻断。使用 sffxzzp/asfcn 一体化镜像（ASF + Caddy）。本 skill 应在用户要求部署 ASF、在 NAS/服务器上跑 ASF 挂卡、或需要 steam302/steamcommunity_302 反代使 ASF 正常工作时使用。包含修复版 Caddyfile（解决 Akamai 400 导致的 bot 反复断连）、docker-compose 模板、远程 SSH 文件传输脚本、完整部署与排障参考。
agent_created: true
---

# ASF + Caddy 反代部署

## Overview

在 Docker 环境（NAS/服务器）部署 ArchiSteamFarm 挂卡工具，并用 Caddy 反代 Steam 社区/GitHub，
绕过 CN 网络的 SNI 阻断（`store.steampowered.com`、`steamcommunity.com` 直连返回 000）。
核心方案：`sffxzzp/asfcn` 一体化镜像，**必须持久化修复版 Caddyfile**，否则 bot 因
Akamai 400 反复 Disconnected。

## 何时使用

- 用户要在 NAS（如极空间 Z4Pro）、服务器上部署 ASF 挂卡
- 需要 steam302 / steamcommunity_302 反代让 ASF 正常工作
- 迁移已有 ASF 配置（bot、数据库）到新机器
- ASF bot 反复 Disconnected，怀疑是反代/Akamai 问题

## 部署流程

### Step 1 — 拉取镜像
从阿里云源拉取（amd64，约 386MB，CN 友好）：
```bash
docker pull registry.cn-hangzhou.aliyuncs.com/sffxzzp/asfcn:latest
```

### Step 2 — 准备数据目录
宿主机建目录，从旧环境复制（如需迁移）：
```
<data_dir>/config/   # ASF.json, <bot>.json, <bot>.db, ASF.db, IPC.config, <bot>.keys.*
<data_dir>/logs/
<data_dir>/plugins/
<data_dir>/Caddyfile  # 用 assets/Caddyfile 修复版
```

### Step 3 — 编写 compose 并启动
用 `assets/docker-compose.yml`（替换数据路径），`docker compose up -d`。
要点：**`/app/Caddyfile` 必须 bind mount**（镜像 entrypoint 会覆盖内置文件）。

### Step 4 — 持久化修复版 Caddyfile
把 `assets/Caddyfile` 写入宿主机 `<data_dir>/Caddyfile`（bind mount 实时同步进容器），然后：
```bash
docker exec asf caddy reload --config /app/Caddyfile
```
**不要用 `docker cp` 覆盖挂载文件**（报 device or resource busy）。

### Step 5 — 配置 bot 与 IPC 密码（使用者必须自己做）
skill 只搭好容器和反代，**没有内置账号密码**。以下两项必须使用者亲手配置：

**① 改 IPC 登录密码（推荐）** — asfcn 镜像默认 `asfcnasfcn`，所有人一样，务必改掉：
编辑 `config/IPC.config`，把 `IPCPassword` 改成自己的强密码，然后重启容器：
```bash
docker restart asf
```
登录 ASF-ui（`http://<host>:1242`）：用户名 `ASF`，密码就是你刚设置的。

**② 创建挂卡 bot（无默认值）** — 每个要挂卡的 Steam 账号建一个 `<bot名>.json`（文件名即 bot 名）：
```json
{
  "SteamLogin": "你的Steam账号名",
  "SteamPassword": "你的Steam密码",
  "Enabled": true,
  "FarmingPreferences": 3
}
```
- Steam 密码是**明文**存在此文件，必须留在服务器本地，**切勿放入 skill 或分享**
- 多个账号就建多个 json，如 `DC.json`、`alt.json`
- 建好后重启容器让 ASF 加载新 bot

### Step 6 — 验证
按 `references/deployment-guide.md` 的「验证清单」逐项检查。关键项：
- bot 日志出现 `OnLoggedOn() Successfully logged on as <steamid>/<name>`、`Init() Success`、`StartFarming()`
- 容器内 curl `https://steamcommunity.com` 返回 200（非 400）
- ASF-ui 可访问 `http://<host>:1242`，用自己设置的 IPC 密码登录

## 关键踩坑点（务必读）

1. **Akamai 400 → bot 反复断连**：asfcn 内置 Caddyfile 的 `(rev)` 段没设 `header_up Host`，
   Akamai 返回 400。`assets/Caddyfile` 已修复（加了 `header_up Host {host}`）。改后 400→200。
2. **Caddyfile 持久化**：bind mount `/app/Caddyfile` + `caddy reload` 生效。
3. **远程传文件**：小文件 base64 中转；大文件（ASF.db 数百 KB）base64 会超 PTY 缓冲，
   必须走 SFTP。用 `scripts/ssh_remote.py`。
4. **无 sshpass 的 Windows 本机**：用 paramiko 连远程（`scripts/ssh_remote.py`）。
5. **docker exec 找不到脚本**：用 `docker exec -i <c> sh -c "echo <b64> | base64 -d | sh"`。
6. **paramiko 超时**：curl/du 等耗时命令加 `--max-time`，或分步执行。

## Resources

### assets/
- `Caddyfile` — 修复版反代配置（Steam 社区/商店/API + GitHub），**这是本 skill 的核心产出**
- `docker-compose.yml` — ASF + Caddy 一体化 compose 模板

### references/
- `deployment-guide.md` — 完整部署流程、原理、方案对比、验证清单、已知局限

### scripts/
- `ssh_remote.py` — paramiko 远程 SSH 执行命令 + SFTP 上传/下载，无 sshpass 环境用
