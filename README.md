# ASF + Caddy Docker Deploy Skills

在任意 Docker 环境（NAS、服务器）部署 ArchiSteamFarm（ASF）挂卡工具，并内置 Steam 社区与 GitHub 反代以绕过 CN 网络 SNI 阻断。

这是一个 **WorkBuddy Skill**，核心价值在于沉淀了 asfcn 一体化镜像部署的完整流程与关键排障经验（尤其是 Akamai 400 问题）。

## 这是什么

用 `sffxzzp/asfcn` 一体化镜像（ASF + Caddy 反代）在 Docker 上部署 ASF，内置 Steam 社区与 GitHub 反代，使 ASF 在 CN 网络下能正常工作。

### 为什么需要反代

- CN 网络对 `store.steampowered.com`、`steamcommunity.com` 做 **SNI 检测阻断**（直连返回 000）
- asfcn 镜像把 Steam/GitHub 域名写入容器 `/etc/hosts` 指向 127.0.0.1，让它们走容器内 Caddy 反代
- Caddy 监听 443，用自签证书反代到 Akamai edgesuite 节点和 GitHub IP

## 目录结构

```
asf-caddy-docker-deploy-skills/
├── SKILL.md                      # Skill 主流程
├── assets/
│   ├── Caddyfile                 # 修复版反代配置（核心产出）
│   └── docker-compose.yml        # asfcn 一体化 compose 模板
├── references/
│   └── deployment-guide.md       # 完整部署流程、原理、验证清单、踩坑点
└── scripts/
    └── ssh_remote.py             # paramiko 远程执行 + SFTP（无 sshpass 环境用）
```

## 快速开始

```bash
docker pull registry.cn-hangzhou.aliyuncs.com/sffxzzp/asfcn:latest
```

编写 compose（见 `assets/docker-compose.yml`），`/app/Caddyfile` 必须 bind mount，然后：
```bash
docker compose up -d
docker exec asf caddy reload --config /app/Caddyfile
```

## ⚠️ 最重要的坑

asfcn 内置 Caddyfile 的 `(rev)` 段**没有设置 `header_up Host`**，导致 Caddy 用上游 Akamai edgesuite 域名做 Host 头，Akamai 返回 **400**，ASF 的 bot 反复 Disconnected。

修复：在 `(rev)` 段加一行
```caddy
header_up Host {host}
```

详见 `references/deployment-guide.md` 的「关键踩坑点」。

## 凭证说明

- Skill 和镜像都**不提供** Steam 账号密码、bot 名、IPC 自定义密码的默认值，100% 由使用者自己填。
- 镜像提供一个通用 IPC 默认密码 `asfcnasfcn`，强烈建议部署后改掉（见 `IPC.config`）。
- 每个要挂卡的 Steam 账号需在 `config/` 下建 `<bot名>.json`（含明文 Steam 密码，务必只留在服务器本地）。

## 许可证

MIT
