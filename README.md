# ASF + Caddy Docker Deploy · WorkBuddy Skill

![License: MIT](https://img.shields.io/badge/license-MIT-green)
![GitHub Stars](https://img.shields.io/github/stars/DC1024/asf-caddy-docker-deploy-skills?style=social)
![Last Commit](https://img.shields.io/github/last-commit/DC1024/asf-caddy-docker-deploy-skills)

[English](README.en.md) | **中文**

> **本项目是 [sffxzzp/asfcn](https://github.com/sffxzzp/asfcn) 的 AI Skill 化封装** ——
> 镜像、反代架构与 Caddy 配置原型均来自 asfcn 上游项目，本仓库仅在其基础上：
> 1. 把部署流程封装成可被 AI Agent 调用的 **WorkBuddy Skill**；
> 2. 沉淀一份修复版 `Caddyfile`（解决 asfcn 内置配置导致 Akamai 400 / bot 断连的问题）；
> 3. 补齐 docker-compose 模板、SSH 远程脚本与完整排障指南。
>
> **致敬上游**：所有核心能力归功于 [`sffxzzp/asfcn`](https://github.com/sffxzzp/asfcn) 作者 🙏。

---

## 这是什么

**这不是一个独立软件，而是一个 AI Skill** —— 一个让 AI 助手（WorkBuddy / Claude / 任何支持 Skill 协议的 Agent）「学会」在任意 Docker 环境部署 ASF 的能力包。

### 它怎么用

你不需要手动跑脚本。只要在支持 Skill 的 AI 助手对话里说一句：

> 「帮我在我的 NAS 上部署 ASF 挂卡，用 asfcn 镜像」

AI 助手会自动加载本 Skill，然后按 `SKILL.md` 里的流程，**调用 Skill 内置的 assets / references / scripts** 完成以下操作：

| 阶段 | AI 会做什么 | 用到的 Skill 资源 |
|---|---|---|
| 1. 环境探测 | SSH 进目标机器，查 Docker / 端口 / 防火墙 | `scripts/ssh_remote.py` |
| 2. 配置生成 | 按你的 NAS 路径生成 compose 与 Caddyfile | `assets/docker-compose.yml`、`assets/Caddyfile` |
| 3. 部署上线 | pull 镜像 → 起容器 → reload Caddy | `references/deployment-guide.md` |
| 4. 排障验证 | 查日志确认 bot 已连上 Steam，处理 400 断连 | `references/deployment-guide.md` 的踩坑点 |

**Skill 的意义**：把「踩了一周的坑」固化成 AI 可读的指令，下次换一台机器、换一个用户，AI 都能一次跑通，而不是每次都从零摸索。

---

## 它解决什么问题

用 `sffxzzp/asfcn` 一体化镜像（ASF + Caddy 反代）在 Docker 上部署 ASF，内置 Steam 社区与 GitHub 反代，使 ASF 在受限网络环境下也能正常工作。

### 为什么需要反代

- 部分网络环境会对 `store.steampowered.com`、`steamcommunity.com` 做 **SNI 检测阻断**（直连返回 000）
- asfcn 镜像把 Steam/GitHub 域名写入容器 `/etc/hosts` 指向 127.0.0.1，让它们走容器内 Caddy 反代
- Caddy 监听 443，用自签证书反代到 Akamai edgesuite 节点和 GitHub IP

---

## 目录结构

```
asf-caddy-docker-deploy-skills/
├── SKILL.md                      # Skill 入口（AI 读这个决定怎么执行）
├── README.md                     # 中文说明（你正在看的这个）
├── README.en.md                  # English version
├── assets/                       # AI 调用时直接复制/改写的产物文件
│   ├── Caddyfile                 #   修复版反代配置（核心产出）
│   └── docker-compose.yml        #   asfcn 一体化 compose 模板
├── references/                   # AI 查阅的背景知识
│   └── deployment-guide.md       #   完整部署流程、原理、验证清单、踩坑点
└── scripts/                      # AI 调用的工具脚本
    └── ssh_remote.py             #   paramiko 远程执行 + SFTP（无 sshpass 环境用）
```

> **Skill 协议说明**：`SKILL.md` 是 AI 的「操作手册」，`assets/` 是 AI 会复制到目标机器的成品文件，`references/` 是 AI 遇到问题时查阅的知识库，`scripts/` 是 AI 调用的工具。人类用户只需说话，AI 自动编排这些资源。

---

## ⚠️ 最重要的坑（asfcn 上游问题，本 Skill 已修复）

asfcn 内置 Caddyfile 的 `(rev)` 段**没有设置 `header_up Host`**，导致 Caddy 用上游 Akamai edgesuite 域名做 Host 头，Akamai 返回 **400**，ASF 的 bot 反复 Disconnected。

修复：在 `(rev)` 段加一行
```caddy
header_up Host {host}
```

详见 `references/deployment-guide.md` 的「关键踩坑点」。本仓库 `assets/Caddyfile` 已包含此修复，AI 部署时直接用修复版，无需用户手动改。

---

## 快速开始（两种方式）

### 方式 A：通过 AI 助手调用 Skill（推荐）

在支持 WorkBuddy Skill 的 AI 助手对话里说：

> 「在我的 NAS（192.168.x.x）上部署 ASF，用 asfcn 镜像，bot 名叫 mybot」

AI 会自动加载本 Skill 并完成全部部署。

### 方式 B：手动按文件操作（适合不用 AI 的用户）

```bash
docker pull registry.cn-hangzhou.aliyuncs.com/sffxzzp/asfcn:latest
```

把 `assets/Caddyfile` 和 `assets/docker-compose.yml` 拷到目标机器，改好路径后：

```bash
docker compose up -d
docker exec asf caddy reload --config /app/Caddyfile
```

---

## 凭证说明

- Skill 和镜像都**不提供** Steam 账号密码、bot 名、IPC 自定义密码的默认值，100% 由使用者自己填
- 镜像提供一个通用 IPC 默认密码 `asfcnasfcn`，强烈建议部署后改掉（见 `IPC.config`）
- 每个要挂卡的 Steam 账号需在 `config/` 下建 `<bot名>.json`（含明文 Steam 密码，务必只留在服务器本地）

---

## 致谢

本 Skill 建立在以下开源项目之上，致敬所有作者：

- **ASF 本体**：[JustArchiNET/ArchiSteamFarm](https://github.com/JustArchiNET/ArchiSteamFarm) —— 核心挂卡程序
- **上游镜像**：[sffxzzp/asfcn](https://github.com/sffxzzp/asfcn) —— ASF + Caddy 一体化镜像的本体，本 Skill 的部署对象
- **反代方案**：[caddyserver/caddy](https://github.com/caddyserver/caddy) —— 反代服务器，负责 Steam/GitHub 域名转发
- **反代思路**：[qingdog/Steamcommunity_302](https://github.com/qingdog/Steamcommunity_302)（Dogfight360 的 S302）—— 本 Skill 反代思路的灵感来源
- **远程工具依赖**：[paramiko/paramiko](https://github.com/paramiko/paramiko) —— `scripts/ssh_remote.py` 使用的 Python SSH 库

本仓库仅在上述项目基础上做 Skill 化封装与 Caddyfile 修复，不重新分发任何上游二进制或镜像。

## 许可证

本仓库（Skill 内容：SKILL.md、文档、Caddyfile、docker-compose 模板、脚本）采用 **MIT License**，详见 [LICENSE](LICENSE)。

> 说明：本仓库是独立的 Skill 化封装作品，不含上游 [sffxzzp/asfcn](https://github.com/sffxzzp/asfcn) 的任何代码或二进制，仅在其镜像部署流程基础上做封装与 Caddyfile 修复。MIT 许可仅适用于本仓库的原创内容，不覆盖 asfcn 镜像本身（asfcn 未声明开源协议）。
