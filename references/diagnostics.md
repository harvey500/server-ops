# Bounded Diagnostics / 有界诊断

Read one language version. Examples use placeholders, not real hosts.

## English

### Helper Requirements And Contract

Local: Python 3.9+, OpenSSH client, key/agent authentication and a verified
known_hosts entry. Remote: Linux with /proc and Python 3.9+. No Paramiko, pip
dependency, remote installation or persistent script file. The helper sends its
reviewed Python runner as code and the argv request via SSH stdin. No automatic
shell/sudo; pipelines require explicitly reviewed `sh -c` argv.

```sh
python scripts/ssh_diagnose.py --host approved-alias --seconds 15 --max-bytes 65536 -- docker logs --since 10m --tail 100 service-name
```

Bounds: 1-120 seconds, 1-262144 bytes per output stream, TERM grace 0.2-5 seconds.
A detached guardian owns a separate command session; its leader stays alive until
cleanup to reserve the process-group identity. Guardian ignores HUP, handles TERM
and times out independently of SSH. It drains stdout/stderr concurrently. Normal
completion also cleans remaining descendants; timeout/overflow terminate the job.

JSON receipt: job ID, reason, command exit, bounded outputs, group identity,
escalation and group cleanup. Exit codes: 0 success/clean; 1 command failed;
2 usage/transport/runner failure; 124 deadline; 125 output cap; 126 uncertain cleanup;
130 interruption. Receipts are not saved automatically. Outputs can contain secrets;
review/redact before sharing. Do not publish real logs.

Not a read-only sandbox: temporary processes/pipes/memory are used, but no remote
persistent files. Cannot contain setsid escapes, daemon-side Docker/systemd work,
externally scheduled tasks, uninterruptible I/O or survive guardian SIGKILL/host
shutdown. Lost receipt means cleanup unconfirmed; wait for deadline and inspect
within authorization. Do not retry side-effecting commands on lost response.
Verification excludes exited zombies, not a whole-host guarantee.

### Collect Evidence And Handle Old Jobs

- Use targeted ps/systemctl/docker fields, not secret-bearing args/env dumps.
- Sample current CPU/memory/disk/inodes/I/O briefly; distinguish one-core and
  whole-host percentages from cumulative CPU time.
- Finite logs, stats --no-stream, journalctl limits still need wall-clock bounds.
  No logs -f/watch/tail -f by default. Target paths/bytes, never grep all of /.
- Trace endpoint/proxy/listener/dependencies/event parsing/action/storage.
  Query aggregates/fixture IDs, not arbitrary customer messages. Independent
  signals support a hypothesis; concurrent changes weaken attribution.
- Before stopping old PIDs check boot context, start time, command role,
  parent/group and task ownership. If unclear, ask. Stop confirmed diagnostic
  tasks, not daemon/business services, then re-sample and verify business health.

## 中文

本地需 Python 3.9+、OpenSSH、已有密钥/agent 及核验过的 known_hosts。远端需 Linux、
/proc、Python 3.9+。无 Paramiko/pip 依赖、不安装远端工具、不写持久脚本，通过 SSH
传 runner 代码和 argv 请求。不自动 shell/sudo，管道须明确审核 `sh -c`。

期限 1-120 秒，每流 1-262144 字节，TERM 宽限 0.2-5 秒。脱离 relay 的 guardian
自行计时、忽略 HUP、处理 TERM；独立 command session 的 leader 留至清理，以保留
组身份。同时读取 stdout/stderr；正常结束也清理同组子进程，超时/超限终止。

JSON 包含 job ID、原因、命令退出、输出、组身份、升级终止和清理结果。退出码
0 成功且清理；1 命令失败；2 用法/传输/runner 失败；124 超时；125 超限；126 清理
不确定；130 中断。不自动保存；输出可能含业务秘密，展示前审核脱敏，不发布真日志。

不是只读沙箱，会创建临时进程、管道、内存，不写远端持久文件。主动 setsid 脱组、
daemon 接手工作、外部计划任务、不可中断 I/O 不受保证；guardian SIGKILL/关机也不能
保证收尾。丢回执就标清理未确认，等期限后按授权复核，不因响应丢失重试有副作用命令。
清理验证不计已退出 zombie，不代表整机没有任务。

目标化查询字段，不输出含秘密参数/环境。短时采样当前 CPU/内存/磁盘/inode/I/O，
区分单核与整机、当前与累计。有限日志/stats/journal 也要限时，不默认跟随或扫根目录。
逐层核对入口、代理、监听、依赖、事件、业务和存储；查聚合/测试标识而非无关用户消息。
旧 PID 核对开机上下文、启动时间、角色、父进程/组和归属；不明就询问，只停诊断任务，
不动 daemon/业务服务。然后分别复测资源和业务。
