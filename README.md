# Extreme V3 Integrated Frame Pipeline

这是 Extreme V3 C++20 无渲染游戏优化 Code Agent 用例的最终整理仓库。

仓库同时保存：

- 可编辑、可构建的 mini-engine 源码；
- Perfetto SDK、Linux trace processor 和辅助脚本；
- 独立隐藏 Code Grade 与基线附件；
- 出题、逐帧行为、评分和 pilot 文档；
- 已验证的 Linux amd64 平台上传包。

## 目录

```text
challenges/nav_rollback/          用例源码、Agent 脚本、公开任务和评分器
  grader/test_by_code.py          独立 Code Grade
  grader/test_files/              隐藏配置与原始基线源码包
docs/                             用例、逐帧内容、评分和 pilot 文档
release/linux-amd64/              当前正式平台上传文件
scripts/bootstrap_perfetto.py     固定版本 Perfetto 安装脚本
third_party/perfetto/             Perfetto v57.2 C++ SDK
tools/perfetto/                   Linux amd64 trace processor
```

## 快速验证

从仓库根目录进入用例：

```text
cd challenges/nav_rollback
python scripts/lb.py doctor
python scripts/lb.py build --release
python scripts/lb.py verify
```

Profile 模式：

```text
python scripts/lb.py build --profile
python scripts/lb.py profile --tag baseline --scenario mixed
python scripts/lb.py report artifacts/baseline/profile.pftrace
```

`lb.py` 会从仓库根目录发现随附的 Perfetto SDK 和 trace processor。正式评测目标
为 Linux amd64；其他平台可使用 `scripts/bootstrap_perfetto.py --tools --platform
<platform>` 安装对应工具。

## 重新生成平台包

```text
python challenges/nav_rollback/authoring/package_dsbench.py --target linux-amd64
```

新包生成在 `challenges/nav_rollback/dist/`。生成后必须重新校验 manifest，不能直接
覆盖 `release/linux-amd64/` 中已冻结的版本。

## 当前冻结版本

| 项目 | SHA-256 |
|---|---|
| workspace.zip | `b82e97567b1695ea081b466aef410fc00d3af417fcaf80b8fda23273e95c9ba8` |
| test_by_code.py | `800e6fa91cfdfec510bc39407e5ddb00d6c82f59c9e5256eb229cc6f53143304` |
| baseline_source.zip | `692b13570958db6e467a4e262a187f730e746e18d25878e44860ddc5bdd446ce` |
| grader_config.json | `4bc6eaeb2eecc84e5e6d79cacc19a064b1999c2b82e3c36e0cd49b7ca46d249d` |

原始 logic hash：

```text
d5367c4725e51c316eb202da4abed994531527ef7f17d740d3f03660fd03bcc6
```

## 保密边界

`docs/EXTREME_V3_COMPLETE_CASE_SPEC_CN.md`、中文评分文档和
`grader/test_files/` 含隐藏参数与门槛，只供出题方使用。发给被测 Agent 的内容
应来自 `release/linux-amd64/workspace.zip` 和公开 `TASK_PROMPT.md`，不能把整个
仓库交给候选。

## 版本说明

该提交是整理快照，不包含任何历史 build 目录、Perfetto trace、Agent artifacts、
临时评测 workspace、Python cache 或原 DSBenchWin 仓库的 Git 历史。

