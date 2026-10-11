# Preflight And Completion / 前置检查与完成状态

Read one language version. No vendor-specific installation claim is bundled;
requirements change and must be checked at task time.

## English

### Download Evidence, Not A Guessed Cause

Record source provenance, retrieval time/timezone, request method, sanitized URL
without credentials/query secrets, status/error category and redacted redirect
chain. Keep a small relevant header/error excerpt privately only when useful.
Never store authorization/cookies or signed URLs in published evidence. Distinguish
DNS, connection, TLS, HTTP rejection, missing file and wrong artifact/architecture.

A 403 means this request was refused. Three files on the same origin share failure
conditions; they are not independent proof of IP blocking. A 404 does not alone
prove the official service is down. HEAD may differ from GET. When permitted, use
a bounded GET/range request (and a byte limit even when the server ignores Range),
current official release metadata and a small controlled comparison. Do not spray
headers/proxies, brute-force artifact URLs, disable TLS verification or evade
access controls. Respect blocks, documented restrictions and retry-after.

Within the authorized task, consider the current official installer/package,
compatible release artifact, or user-approved download on a trusted local machine
followed by transfer to the SAME server. Verify integrity/provenance before
execution; a self-computed SHA-256 establishes transfer consistency, not authenticity.
Use publisher signatures/checksums when available and explain missing verification.
Do not add unofficial mirrors, tunnels, VPNs or paid hosts without authorization.
Stop repeated attempts that produce no new evidence; report exact remaining gaps.

### Capability Preflight And Architecture Preservation

Check distro/version, CPU architecture, libc/package format, runtime versions,
privileges, filesystem space/inodes, memory and relevant display/kernel/device
requirements. Query only what the chosen component needs. Distinguish installed,
available and actually usable. Docker failure can arise from daemon state,
permissions, cgroups/storage/network or host constraints; it does not by itself
prove a "stripped kernel". Compare a candidate replacement's current official
dependencies; shared dependencies can preserve a blocker, but do not invent them.

Retain the requested product/deployment goal. Local download plus server transfer
is different from running the service on the user's laptop. Moving runtime,
opening inbound ports, changing network trust or removing an existing component
requires a concrete tradeoff and authorization. Do not uninstall a working piece
until compatibility and recovery are established, even if a suggested replacement
turns out unsuitable. A blocked login/QR/second factor can legitimately require
the user; hand off only the precise user action, not unrelated diagnosis.

### Four Independent Completion States

Installed: artifact/version and required dependencies observed.
Started: process/listener and startup evidence observed.
Connected: the intended account/backend connection observed, not merely a port.
Business: an authorized representative operation and its negative invariants pass.
No state is inferred from another; "healthy" does not imply account or business.
Mark non-applicable stages with a rationale, not as passes. Include diagnostic
cleanup separately and disclose any unverified parts.

Optional offline record checker:

```sh
python -B scripts/ops_status.py /path/to/private-record.json
```

Input schema (all four stages required, status = passed/failed/unknown/not_applicable):

```json
{
  "evidence": [{"id": "E1", "verified": true, "locator": "private-session:check-1"}],
  "stages": {
    "installed": {"status": "passed", "evidence": ["E1"]},
    "started": {"status": "unknown", "evidence": []},
    "connected": {"status": "not_applicable", "evidence": [], "rationale": "No account/backend in this task"},
    "business": {"status": "unknown", "evidence": []}
  },
  "cleanup": {"status": "unknown", "evidence": []}
}
```

Each passed/failed stage needs existing, declared verified evidence references.
For cleanup, not_applicable is valid only when no diagnostic jobs were launched,
with that rationale. `business` cannot be not_applicable for this completion
contract; a local-only installation is partial, not a business-verified deployment.
Exit 0 = declared complete; 1 = partial; 2 = malformed/inconsistent record.
The checker emits only statuses/IDs/error codes, never locators/raw record data.
It is NOT a truth verifier. Keep records private; do not commit real observations.

## 中文

### 下载证据与前置能力

记录来源、时间时区、请求方式、脱敏 URL（不含凭据/秘密参数）、状态/错误类别和
脱敏跳转链；只在私有记录保留少量相关响应头/错误，不存认证头、Cookie 或签名链接。
区分 DNS、连接、TLS、HTTP 拒绝、文件不存在、架构/格式错误。

403 只证明请求被拒绝，同源三文件不是独立 IP 封禁证据；404 不证明服务整体下线。
HEAD/GET 可不同，获许可时有限 GET/Range 且服务忽略 Range 时也限制字节。
核对当前官方发布资料、少量对照，不喷请求头/代理、不猜大量 URL、不关 TLS、不绕封。
遵守限制和 retry-after，无新证据就停止重复尝试。

原任务授权内考虑官方安装器、兼容 artifact 或用户认可的可信本地下载再传到同一服务器。
执行前验证来源/完整性，自算 SHA-256 证明传输一致而非来源可信，优先发布方签名/校验值，
缺失时明确。非官方镜像、隧道、VPN 或收费主机需授权。

核对系统版本、架构、libc/格式、运行时、权限、空间/inode、内存及相关显示/内核/设备
条件，只查组件必需项。区分已安装、可获得和实际可用。Docker 失败不自动等于内核阉割，
也可能是 daemon、权限、cgroups/存储/网络。替代品依赖查当前官方资料，不凭记忆。

本地下载传服务器不等于迁到用户电脑运行。迁运行环境、开入站端口、改网络信任或移除
组件需说明代价并获授权；不在兼容/恢复未确认时先卸载。登录/扫码等确需用户时，仅交接
准确必需动作，不把未完成排查全部丢回用户。

### 分层状态与记录

安装看版本/依赖；启动看进程/监听；连接看实际账号/后端；业务看获授权真实操作及负面
约束。互不推导，healthy 不等于已连接/业务可用。不适用必须说明理由，不能冒充通过。
清理单独报告。上述离线记录格式须包含四层和 cleanup；通过/失败需存在且声明已核验的
证据 ID。清理不适用只在未启动诊断任务时成立，业务不能不适用；仅安装属于部分完成。
退出 0 声明完成、1 部分、2 记录格式/关联不一致。工具不核验证据真假，只输出状态、ID
和错误码，不输出 locator/原始数据。真实记录保密，不提交仓库。
