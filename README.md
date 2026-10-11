# server-ops

[中文](#中文) | [English](#english)

## 中文

面向 **Linux / SSH / Docker Compose** 的 agent 运维 skill，重点解决诊断进程遗留、
容器补丁重建后丢失，以及“容器健康但业务不正常”的验收问题。不是全能运维平台，
不会因安装而获得服务器访问或修改权限。

新增下载故障取证和部署前置检查：403 不自动推断 IP 被封，替代品依赖查当前官方资料，
不因下载失败擅自迁到用户电脑。完成状态拆成安装、启动、连接、业务，并单列清理。

### 安装与调用

将仓库克隆到 agent 支持的 skills 目录，命名 `server-ops`，或复制 `SKILL.md`、
`agents/`、`scripts/`、`references/` 和 `LICENSE`。发现可能需重新加载。

```text
使用 $server-ops 排查我授权的 SSH 别名对应的 Docker 服务。
先有限诊断，确认你的查询任务结束；修改前说明范围、停机和恢复方案。
```

适用已有认证的授权服务器。历史聊天中的 IP/密码不是新连接授权。
使用密钥/agent 和已核验主机密钥，不存储密码、不自动接纳陌生主机。

### 有期限的诊断助手

本地 Python 3.9+ 和 OpenSSH；远端 Linux、/proc、Python 3.9+。无第三方 Python 依赖，
不写远端脚本、不安装服务。首次使用请读 `references/diagnostics.md`。

```sh
python scripts/ssh_diagnose.py --host approved-alias --seconds 15 --max-bytes 65536 -- docker logs --since 10m --tail 100 service-name
python -m unittest discover -s scripts -p "test_*.py" -v
python -B scripts/ops_status.py /path/to/private-record.json
```

远端独立 guardian 管执行期限、同时读取两路输出并在完成/超时/超限时清理同组任务。
回执说明命令结果和组清理；没有回执就不声称清理成功。它**不是只读沙箱**：执行任何
命令前仍需审核与授权。默认无后台监控，支持 1-120 秒诊断。

### 限制与测试

无法保证清理主动脱组子进程、不可中断内核任务、daemon 接手工作、guardian 被强杀
或关机情形。业务输出可能含秘密，分享前需脱敏。SSH 认证日志不在进程内存限额保证
内；本地配置和远端 runner 必须可信。当前没有针对生产服务器进行任何测试。

自动化测试分为跨平台请求/传输测试及 Linux 进程集成测试：正常退出、失败、卡住、
输出暴涨、遗留同组子进程、relay 被杀。Windows 会明确跳过 Linux 项目，CI 在 Linux
运行。尚无独立 agent 行为评测，也未进行真实 SSH/Docker 集成测试，不能承诺零风险。

离线状态工具检查声明的证据关联并推导完成/部分完成，不核验证据真伪，不自动探活；
格式见 `references/preflight.md`。`references/evaluation-cases.md` 提供 7 个合成行为
验收案例，尚未执行独立 agent 评测。没有联网下载脚本，不会自动处理 CDN 限制。

MIT 许可证，harvey500。公开材料仅包含通用脱敏案例，不包含真实主机或凭据。

## English

An agent skill for **Linux / SSH / Docker Compose** operations: bounded diagnostics,
durable deployments and business verification. Installation does not authorize
server access or changes. It is not a general infrastructure platform.

Download/preflight guidance avoids inferring IP bans from 403s, checks current
dependencies and preserves the intended architecture. Installation, startup,
connection, business verification and cleanup are reported separately.

Clone into your host's supported skill directory as `server-ops`, or keep SKILL.md,
agents/, scripts/, references/ and LICENSE together. Host discovery may need reload.

```text
Use $server-ops to diagnose this authorized SSH alias and Docker service.
Bound and clean up diagnostic jobs; explain scope, downtime and recovery before changes.
```

Local Python 3.9+ and OpenSSH; remote Linux, /proc and Python 3.9+. Existing key/agent
authentication and verified host keys are required. No third-party Python packages,
remote script files or service installation. Read references/diagnostics.md before
using the helper; commands and tests are shown above.

A detached remote guardian enforces deadlines, concurrently drains bounded output
and cleans its command group on success/timeout/overflow. JSON receipts separate
command outcome from cleanup. Lost receipt never means verified cleanup. It is not
a read-only sandbox; commands still need review and authorization. No background
monitoring by default; diagnostics last 1-120 seconds.

Cannot contain escaping descendants, uninterruptible kernel tasks, daemon-side
operations, guardian SIGKILL or host shutdown. Outputs may include application
secrets. SSH transport/authentication output is not covered by a process-memory
cap; trust local configuration and the remote runner. No production server was used.

Tests cover portable request/transport contracts plus Linux normal/failing/hung
commands, output floods, background group children and killed relays. Windows
explicitly skips Linux tests; Linux CI runs them. Independent agent behavioral
evaluation and actual SSH/Docker integration have not been performed.

The offline ops_status.py checks declared evidence links and completion, not truth
or live health. Its schema is in references/preflight.md. Seven synthetic semantic
cases in references/evaluation-cases.md remain unevaluated by an independent agent.
No network download helper or automatic CDN workaround is provided.

MIT, harvey500. Published material contains no real host addresses or credentials.
