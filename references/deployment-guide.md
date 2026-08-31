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

## 6. 验证清单

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

## 7. 已知局限
- `raw.githubusercontent.com` 反代偶发不稳定（一次 000 一次 301）。若 ASF 设 `UpdatePeriod=0`
  禁用自动更新则影响不大；需要拉 GitHub 内容时再调整。
- 自签证书，浏览器访问 ASF-ui 之外的 https 反代站点会提示不安全（正常）。
