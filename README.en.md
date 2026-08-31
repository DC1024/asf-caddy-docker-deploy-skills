# ASF + Caddy Docker Deploy · WorkBuddy Skill

[English](README.en.md) | **[中文](README.md)**

> **This project is an AI-Skill packaging of [sffxzzp/asfcn](https://github.com/sffxzzp/asfcn)** —
> the image, reverse-proxy architecture, and the Caddy configuration prototype all come from the asfcn upstream. This repository only:
> 1. Wraps the deployment workflow into a **WorkBuddy Skill** that AI agents can invoke;
> 2. Ships a fixed `Caddyfile` (fixes the Akamai 400 / bot disconnect caused by asfcn's built-in config);
> 3. Adds a docker-compose template, an SSH remote script, and a complete troubleshooting guide.
>
> **Credit to upstream**: all core capabilities belong to the [`sffxzzp/asfcn`](https://github.com/sffxzzp/asfcn) author 🙏.

---

## What Is This

**This is not standalone software — it is an AI Skill**: a capability pack that teaches an AI assistant (WorkBuddy / Claude / any Skill-protocol-compatible agent) how to deploy ASF on any Docker environment.

### How It Is Used

You don't run scripts by hand. Just tell a Skill-aware AI assistant:

> "Deploy ASF card-farming on my NAS using the asfcn image"

The AI loads this Skill and, following the workflow in `SKILL.md`, **uses the Skill's built-in assets / references / scripts** to carry out:

| Phase | What the AI does | Skill resources used |
|---|---|---|
| 1. Env probe | SSH into the target machine, check Docker / ports / firewall | `scripts/ssh_remote.py` |
| 2. Config generation | Generate compose & Caddyfile for your NAS paths | `assets/docker-compose.yml`, `assets/Caddyfile` |
| 3. Deploy | Pull image → start container → reload Caddy | `references/deployment-guide.md` |
| 4. Verify / troubleshoot | Check logs to confirm bots connect to Steam, handle 400 disconnects | `references/deployment-guide.md` gotchas |

**Why a Skill**: it turns "a week of trial and error" into AI-readable instructions. On the next machine, for the next user, the AI gets it right the first time instead of starting from scratch.

---

## What Problem It Solves

Deploys ASF with the `sffxzzp/asfcn` all-in-one image (ASF + Caddy reverse proxy) on Docker, with built-in Steam Community and GitHub reverse proxying so ASF works even under restricted network environments.

### Why Reverse Proxy Is Needed

- Some network environments apply **SNI-based blocking** to `store.steampowered.com` and `steamcommunity.com` (direct connections return 000)
- The asfcn image writes Steam/GitHub domains into the container's `/etc/hosts` pointing to 127.0.0.1, routing them through the in-container Caddy reverse proxy
- Caddy listens on 443 and reverse-proxies to Akamai edgesuite nodes and GitHub IPs with a self-signed certificate

---

## Directory Structure

```
asf-caddy-docker-deploy-skills/
├── SKILL.md                      # Skill entry point (the AI reads this to decide how to proceed)
├── README.md                     # Chinese documentation (you are reading this)
├── README.en.md                  # English version
├── assets/                       # Deliverable files the AI copies/rewrites when deploying
│   ├── Caddyfile                 #   Fixed reverse-proxy config (core deliverable)
│   └── docker-compose.yml        #   asfcn all-in-one compose template
├── references/                   # Background knowledge the AI consults
│   └── deployment-guide.md       #   Full deployment flow, principles, verification checklist, gotchas
└── scripts/                      # Tool scripts the AI invokes
    └── ssh_remote.py             #   paramiko remote execution + SFTP (for environments without sshpass)
```

> **Skill protocol note**: `SKILL.md` is the AI's "operator's manual", `assets/` are the final files the AI copies onto the target machine, `references/` is the knowledge base the AI consults when it hits a problem, and `scripts/` are the tools the AI invokes. Human users just talk — the AI orchestrates these resources automatically.

---

## ⚠️ The Biggest Pitfall (an asfcn upstream issue — fixed in this Skill)

The `(rev)` snippet in asfcn's built-in Caddyfile **does not set `header_up Host`**, so Caddy sends the upstream Akamai edgesuite domain as the Host header, Akamai responds **400**, and ASF bots repeatedly Disconnect.

Fix: add one line to the `(rev)` snippet
```caddy
header_up Host {host}
```

See the "Key Gotchas" section of `references/deployment-guide.md`. The `assets/Caddyfile` in this repo already includes the fix, so the AI deploys with the fixed version — no manual patching needed.

---

## Quick Start (Two Ways)

### Option A: Invoke the Skill via an AI assistant (recommended)

Say to a WorkBuddy Skill-aware assistant:

> "Deploy ASF on my NAS (192.168.x.x) with the asfcn image, bot name mybot"

The AI loads this Skill and completes the whole deployment automatically.

### Option B: Manual operation from the files (for users not using AI)

```bash
docker pull registry.cn-hangzhou.aliyuncs.com/sffxzzp/asfcn:latest
```

Copy `assets/Caddyfile` and `assets/docker-compose.yml` to the target machine, adjust the paths, then:

```bash
docker compose up -d
docker exec asf caddy reload --config /app/Caddyfile
```

---

## Credentials

- The Skill and the image provide **no defaults** for Steam account passwords, bot names, or IPC custom passwords — 100% supplied by the user
- The image ships a generic IPC default password `asfcnasfcn`; strongly recommended to change it after deployment (see `IPC.config`)
- Each Steam account to farm needs a `<bot-name>.json` in `config/` (contains the Steam password in plaintext — keep it on the server only)

---

## Acknowledgements

- **Upstream project**: [sffxzzp/asfcn](https://github.com/sffxzzp/asfcn) — the ASF + Caddy all-in-one image
- **ASF itself**: [JustArchiNET/ArchiSteamFarm](https://github.com/JustArchiNET/ArchiSteamFarm)
- **Reverse proxy**: [caddyserver/caddy](https://github.com/caddyserver/caddy)

This repository only does Skill packaging and a Caddyfile fix on top of the projects above; it does not redistribute any upstream binaries or images.

## License

This repository (Skill content: SKILL.md, docs, Caddyfile, docker-compose template, scripts) is licensed under the **MIT License** — see [LICENSE](LICENSE).

> Note: this repository is an independent Skill-packaging work. It contains no code or binaries from the upstream [sffxzzp/asfcn](https://github.com/sffxzzp/asfcn); it only wraps the asfcn image's deployment flow and ships a Caddyfile fix. The MIT license applies solely to this repository's original content and does not cover the asfcn image itself (asfcn declares no open-source license).
