# Durable Deployment / 持久部署

## English

Identify the effective Compose project/workdir, files/overrides/profiles, service,
image digest/version and mounts. Validate with `docker compose config --quiet`;
full config/inspect/env can expose secrets. Check targeted fields, hashes,
ownership and permissions. Similar file names do not prove active configuration.

Record invariants: existing patches, command permissions, sanitation, ports,
volume/database attachments and expected message behavior. Library patches can
override upstream fixes; prefer maintained builds/extensions when practical.
Check exact compatibility and pin tested images, not an old library over all upgrades.

Prepare protected config/patch recovery copies and previous immutable image when
needed. Define restoration, downtime and failure threshold. Hashes are not backups,
backups are not tested restores; config/image rollback cannot undo all data writes.

Validate before disruption, change one approved service on one host. Avoid compose
down, whole-stack rebuilds, database recreation, prune and deletion. Startup checks
should fail visibly rather than lose required behavior silently; explain downtime
tradeoff and recovery first. Read-only mounts need correct access and verification
inside the new container. Unused reapply scripts are not durable deployment.
Recreation tests require authorization; restart is not recreation.

For message fixtures test group/direct routes, self-event recording without
reply/command, deduplication and ordinary traffic. Local injection can affect
production even without external messages; obtain approval or isolate services/data.
Cleanup only exact approved fixture identities, never broad ranges. Observe bounded
logs/resource samples and business requests; on failure stop the next host and
recover. Report invariants, persistence evidence, untested upgrades and job cleanup.

## 中文

核对实际 Compose 项目、工作目录、配置及 overrides/profiles、服务、镜像 digest/版本
和挂载。`docker compose config --quiet` 校验，完整配置/inspect/env 可能含秘密。
只看必需字段、哈希、所有者和权限，不能凭类似文件名判断生效配置。

记录已有补丁、命令权限、字符清理、端口、卷/数据库和消息行为。库补丁可能覆盖上游
修复，优先维护的镜像/扩展。检查准确兼容性并固定已测镜像，不旧库覆盖所有升级。
必要时准备受权限保护的配置/补丁恢复副本和旧不可变镜像，明确恢复、停机和失败阈值。
哈希不是备份，备份不是验证过的恢复，配置/镜像回滚不保证撤销数据写入。

校验先于中断，逐台逐服务，不 compose down/整栈重建/重建数据库/prune/删除。
启动检查显式失败比静默丢功能好，但要先说明可用性影响与恢复。只读挂载需正确权限及
容器内验证。旁边放 reapply 脚本不等于部署接入；实际重建需授权，restart 不代替。

消息 fixture 测群聊/私聊、自己消息只记录不触发回复/命令、去重及普通消息。
本地注入也有生产副作用，需授权或隔离环境；仅清理准确测试标识，不能大范围删。
有限观察日志/资源和业务请求；失败停止下一台并恢复，说明保留行为、持久性证据、
未测升级和诊断清理。
