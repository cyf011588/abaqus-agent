# 示例任务

> 以下命令都在仓库根目录下运行。先 `Copy-Item .env.example .env` 并填好 key。

## 0. 不依赖 key 的两条命令（可先跑）

```powershell
# 把历史 .workbuddy/memory 结论灌进长期记忆
python -m agent.seed_memory cantilever --preview

# 演示模式：真实执行工具，录屏用（不需要大模型 / key）
python -m agent --dry-run "悬臂梁，L=100，生成并校验"
```

## 1. 查一下有哪些技能、哪些闸门

```
python -m agent "我现在有哪些参数化建模技能？cantilever 有哪些校验闸门？"
```

期望：agent 调 `list_skills` + `list_checks`，把技能和闸门列出来。

## 2. 先查知识，再生成（标准链路）

```
python -m agent "用 cantilever 生成一版悬臂梁：L=100、W=10、H=10、端部均布 1000N，
先生成，再跑结构校验。"
```

期望：agent 先用 `search_knowledge` 查几何约定，再 `generate_model`，
最后 `run_check`（check_inp），并汇报节点数、单元数与校验结果。

## 3. 批量扫描一个参数

```
python -m agent "用 cantilever 扫梁长 80、100、120，每个都跑结构校验，给我汇总表。"
```

期望：一次 `batch_run` 内部循环完成三组生成 + 校验，避免机械地重复调用几十次。

## 4. 查历史算例 / 记忆

```
python -m agent "我之前生成过哪些算例？"
```

期望：agent 读 `data/memory.db` 的 `cases` 表回答（前提是之前跑过 `generate_model`）。

## 5. 让 agent 记住一条结论

```
python -m agent "记住：cantilever 的长宽比超过 20 时，沿长度方向要加密网格才保精度。"
```

期望：`remember` 写入 `facts`，下次会话启动时自动进入 system prompt。

---

## 说明

- `submit_job` 会真实调用 `abq2020` 并阻塞等待，完整推覆可能跑数小时，演示时慎用；
  只做「生成 + 校验」也足以展示 agent 的工具调用、知识与记忆能力。
- 若只想验证工具层（不经过大模型），可直接：

```powershell
python -c "from agent import tools; print(tools.list_skills())"
python -c "from agent import tools; print(tools.search_knowledge('cantilever', '网格'))"
python -c "from agent import tools; print(tools.generate_model('cantilever', {'L':100,'W':10,'H':10}, job='DEMO'))"
```
