# ASF + Caddy 反代部署参考

本文档记录在任意 Docker 环境（NAS、服务器）上部署 ArchiSteamFarm + Steam/GitHub 反代的完整流程、
踩坑点与验证方法。核心结论：**用 `sffxzzp/asfcn` 一体化镜像，必须持久化修复版 Caddyfile，否则
bot 会因 Akamai 400 反复 Disconnected。**

## 1. 背景与原理

**为什么 ASF 需要反代？**
- 部分网络环境对 `store.steampowered.com`、`steamcommunity.com` 做 **SNI 检测阻断**（直连返回 000），
  但 `cdn.steamstatic.com`、`help.steampowered.com` 可通。
- ASF 启动要先通过 HTTP API 拿 CM 服务器列表（走反代），再直连 CM（steamserver.net:443，多数网络可直连）。

**asfcn 一体化镜像原理**
- entrypoint 把 `steamcommunity.com`、`store.steampowered.com`、`api.steampowered.com`、
  `github.com` 写入容器 `/etc/hosts` 指向 `127.0.0.1`。
- 容器内 Caddy 监听 443，用自签证书反代到 Akamai edgesuite 节点和 GitHub IP。
- 默认 IPC 密码：`asfcnasfcn`。

## 2. 方案对比

| 方案 | 说明 | 适用 |
|------|------|------|
| **sffxzzp/asfcn 一体化镜像（推荐）** | ASF + Caddy 一个容器，零配置启动 | 大多数情况 |
| S302 容器 + ASF 分离 | 两个容器，反向代理独立跑 | 需要单独管理反代时 |

## 3. 部署步骤

### 3.1 拉镜像
```bash
docker pull registry.cn-hangzhou.aliyuncs.com/sffxzzp/asfcn:latest
```
amd64 约 386MB，走阿里云源，拉取顺畅。

### 3.2 准备目录与配置
宿主机建数据目录，从旧环境（如有）复制：
```
<data_dir>/config/   # ASF.json, <bot>.json, <bot>.db, ASF.db, IPC.config, <bot>.keys.*
<data_dir>/logs/
<data_dir>/plugins/
<data_dir>/Caddyfile  # 用 assets/Caddyfile 的修复版
```

### 3.3 配置复用（迁移）
- **小文件**（json/key/keys）：用 base64 中转写远程（见 4.3）。
- **大文件**（ASF.db 数百 KB）：base64 大串会超 PTY 缓冲，**必须走 SFTP** 中转
  （源机下载 → 本机 → 目标机上传）。

### 3.4 启动 compose
用 `assets/docker-compose.yml`，替换数据路径后：
```bash
docker compose -f asf.yaml up -d
```

### 3.5 验证反代（必须做）
```bash
# 容器内
docker exec <container> sh -c "wget -qO- --no-check-certificate https://steamcommunity.com -S 2>&1 | head -5"
docker exec <container> sh -c "wget -qO- --no-check-certificate https://github.com -S 2>&1 | head -5"
# 期望: steamcommunity 200 / github 200
```

## 4. 关键踩坑点

### 4.1 ⚠️ Akamai 400 → bot 反复 Disconnected（最重要）
asfcn 内置 Caddyfile 的 `(rev)` 段**没有设置 `header_up Host`**，Caddy 会用上游
`steam...akamaihd.net.edgesuite.net` 域名做 Host 头，Akamai 返回 **400**。
修复：在 `(rev)` 段加一行
```caddy
header_up Host {host}
```
修复后 steamcommunity 从 400 → 200，bot 立即稳定登录。

### 4.2 Caddyfile 持久化
镜像 entrypoint 会覆盖内置 Caddyfile。必须 **bind mount** `/app/Caddyfile` 到宿主机文件，
这样：
- 修改宿主机文件实时同步进容器
- 生效命令：`docker exec <container> caddy reload --config /app/Caddyfile`

**不要**用 `docker cp` 覆盖挂载的文件，会报 "device or resource busy"。

### 4.3 远程文件写入（无 sshpass）
用 paramiko，小文件用 PTY + `sudo -S bash` + base64：
```python
stdin, stdout, stderr = ssh.exec_command("sudo -S bash -c 'echo <b64> | base64 -d > /path/file'", get_pty=True)
stdin.write(password + "\n")
```
大文件改用 SFTP（`ssh_remote.py --upload`）。

### 4.4 docker exec 找不到脚本
如果执行 `docker exec <c> sh /tmp/t.sh` 报文件不存在，说明脚本写到了**宿主机**而非容器内。
用：
```bash
docker exec -i <container> sh -c "echo '<b64>' | base64 -d | sh"
```

### 4.5 paramiko 命令超时
curl 测试、du 扫描等耗时命令容易超时。给命令加 `--max-time`、`--connect-timeout`，或分步执行。

## 5. 配置 bot 与 IPC 密码（首次部署必做）

> 容器和反代搭好后，**还没有任何账号密码生效**。ASF 不会自动挂卡，以下必须手动配置。

### 5.1 改 IPC 登录密码（ASF-ui 密码）
asfcn 镜像默认 IPC 密码是 `asfcnasfcn`（所有使用者一样），**务必改成自己的**。
编辑 `config/IPC.config`：
```json
{
  "Kestrel": {
    "KnownNetworks": [
      { "IP": "192.168.0.0", "CIDR": 16 }
    ],
    "IPCPassword": "改成你自己的强密码"
  }
}
```
保存后重启容器生效：`docker restart asf`。
登录 `http://<host>:1242`：用户名默认 `ASF`，密码为刚设置的值。

### 5.2 创建挂卡 bot
每个要挂卡的 Steam 账号，在 `config/` 下建一个 `<bot名>.json`（**文件名就是 bot 名**）：

**最小配置**（必须）：
```json
{
  "SteamLogin": "Steam账号名",
  "SteamPassword": "Steam密码",
  "Enabled": true
}
```

**常用字段参考**：
| 字段 | 作用 | 建议值 |
|------|------|--------|
| `SteamLogin` | Steam 账号名 | 必填 |
| `SteamPassword` | Steam 密码（明文） | 必填 |
| `Enabled` | 是否启用该 bot | `true` |
| `FarmingPreferences` | 挂卡策略 | `3`（挂全部可挂卡） |
| `Paused` | 暂停挂卡 | `false` |

示例 `mybot.json`：
```json
{
  "SteamLogin": "your_steam_username",
  "SteamPassword": "你的Steam密码",
  "Enabled": true,
  "FarmingPreferences": 3
}
```

**注意事项**：
- **多个账号**：多建几个 json 即可（`mybot.json`、`alt.json`...），ASF 自动为每个文件起一个 bot
- **明文密码风险**：`SteamPassword` 是明文的，此文件**只留在服务器本地**，绝不要进 skill、进 git、或对外分享
- 建好 json 后重启容器（`docker restart asf`）让 ASF 加载新 bot
- 若之前迁移过旧配置，直接复用已有 `<bot>.json` 和 `<bot>.db`（免重新验证令牌）

### 5.3 密码/凭证没有默认值
Skill 和镜像**都不提供** Steam 账号密码、bot 名、IPC 自定义密码的默认值——这些 100% 由使用者自己填。
镜像只提供一个通用 IPC 默认密码 `asfcnasfcn`，强烈建议改掉。

## 6. 更新机制：镜像固定 + ASF 内部自更新（推荐）

> 适用场景：镜像被改过（如本 skill 的修复版 Caddyfile）、或不想每次升级都拉新镜像。
> 原理：ASF 本体自带 `AutoUpdates`，能从 GitHub 下载新版并替换自身程序文件；
> 镜像固定不动，所有定制永久保留。

### 6.1 为什么不能直接拉新镜像
asfcn 镜像把 ASF + Caddy 打包在一起，`pull :latest` 换新镜像会**整层覆盖**容器，
修复版 Caddyfile 等定制全部丢失。而 ASF 自更新只替换 `/asf` 下的程序文件，
不碰 Caddyfile、config、plugins。

### 6.2 第一步：持久化 `/asf` 程序目录（关键前提）
ASF 程序本体在容器内 `/asf`（约 51M，非 `/app`）。自更新下载的新程序写入 `/asf`，
若只在容器可写层，容器一重建就丢。必须 bind mount：

```yaml
volumes:
  - /path/to/asf/asf:/asf
```

首次挂载先复制容器内目录到宿主机（源目录须为空或不存在）：
```bash
docker cp asf:/asf /path/to/asf/asf
docker compose up -d --force-recreate
```

### 6.3 第二步：配置 ASF.json 启用自更新
编辑 `config/ASF.json`：
```json
{
  "AutoUpdates": true,
  "UpdatePeriod": 24,
  "UpdateCheckingPeriod": 24,
  "UpdateChannel": 0
}
```
| 字段 | 作用 | 建议值 |
|------|------|--------|
| `AutoUpdates` | 总开关，允许自更新 | `true` |
| `UpdatePeriod` | 更新检查周期（小时） | `24`（每天查一次） |
| `UpdateCheckingPeriod` | 更新检查前置周期 | 与 `UpdatePeriod` 相同 |
| `UpdateChannel` | 更新通道，`0`=Stable `1`=Experimental | `0`（稳定版） |

改完 `docker restart asf` 生效。

### 6.4 第三步：验证自更新链路
```bash
# ① IPC 确认能力位 (CanUpdate=true, AutoRestart=true, UpdatePeriod=24)
curl -H "X-ApiKey: <IPCPassword>" http://<host>:1242/api/asf | grep -E 'CanUpdate|AutoRestart|UpdatePeriod'
# ② 手动触发检查（已是最新版会返回 "V6.x.x.x ≥ V" 拒绝，证明链路完整）
curl -X POST -H "Content-Type: application/json" -H "X-ApiKey: <IPCPassword>" http://<host>:1242/api/asf/update
```
注意：IPC 触发更新**必须带 `Content-Type: application/json` 头**，否则返回 415。

### 6.5 自更新的网络链路（CN 环境实测可用）
- ASF 更新检查走 `api.github.com`（容器内可直连）
- 新版下载走 `github.com`：entrypoint 把 github.com 劫持到 127.0.0.1 → 容器内 Caddy 443 反代 → GitHub IP
- 前提：Caddyfile 含 `github.com` 反代段（本 skill 的 `assets/Caddyfile` 已含）；hosts 劫持 + Caddy 反代缺一不可
- 实测：GitHub API 直连 0.55s，下载 1.68s，链路通畅

## 7. 验证清单

| 检查项 | 方法 | 期望 |
|--------|------|------|
| 容器健康 | `docker ps` | Up (healthy) |
| 443 独占 | `ss -tlnp \| grep :443` | docker-proxy 独占，无冲突 |
| bot 登录 | ASF 日志 `docker logs <c>` | `OnLoggedOn() Successfully logged on as <steamid>/<name>`、`Init() Success`、`StartFarming()` |
| steamcommunity | 容器内 curl | 200 |
| store.steampowered | 容器内 curl | 200 |
| api.steampowered | 容器内 curl | 404（正常，需带参数） |
| github.com | 容器内 curl | 200 |
| raw.githubusercontent | 容器内 curl | 301（偶发 000，待观察） |
| ASF-ui | 浏览器 `http://<host>:1242` | 200，可登录 |

## 8. 已知局限
- `raw.githubusercontent.com` 反代偶发不稳定（一次 000 一次 301）。ASF 自更新（走 github.com）
  不受影响；需要拉 raw.githubusercontent 内容时再调整。
- 自签证书，浏览器访问 ASF-ui 之外的 https 反代站点会提示不安全（正常）。
