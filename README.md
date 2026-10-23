<div align="center">

# RoleVault
### 让每一次记住都有理由，让每一次遗忘都有依据。

**Role-Isolated Memory Governance · V2.7 Fusion**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Core tests](https://img.shields.io/badge/111_core_tests-passing-2A9D8F)](#本地运行)
[![Demo](https://img.shields.io/badge/Decision_Lab-synthetic-1D5365)](app/decision-lab.html)

[核心源码](src/rolevault/) · [决策实验室](app/decision-lab.html) · [测试](tests/) · [使用说明](#本地运行)

</div>

## 竞赛公开材料

- [最新作品介绍 PDF（18 页）](competition-materials/RoleVault_V27_R6_18P.pdf)
- [材料清单、SHA-256 与验证结果](competition-materials/README.md)
- [公开证据摘要](competition-materials/evidence/PUBLIC_EVIDENCE.md)

---

## 为什么需要 RoleVault？

长期记忆的关键不只是保存信息，还包括**哪些值得记、谁有权修改、旧消息何时失效、用户要求遗忘后如何防止旧数据复活**。

| 风险 | 设计机制 |
|---|---|
| 不可信文本冒充记忆所有人 | 可信来源与角色授权检查 |
| 旧消息覆盖新事实 | 时态判断、有效日期、冲突处理 |
| 密钥被写进长期记忆 | 存储前拒绝敏感信息 |
| 删除后再次恢复旧事实 | 遗忘标记与旧消息回放抑制 |
| 看不到系统如何决定 | 审计动作、状态哈希与读回校验 |

## 核心决策流程

**可信身份 → 数据允许 → 时态检查 → 确认/澄清 → 记忆更新、拒绝或遗忘 → 读回核验**

代码结构：
- [V2.7 时态网关](src/rolevault/fusion_temporal_gateway_v27.py)
- [记忆核心](src/rolevault/)
- [离线合成场景实验室](app/decision-lab.html)
- [核心回归测试](tests/)

## 本地运行

Python 3.10+，核心实现不需要第三方依赖。

    $env:PYTHONPATH = "src"
    python -m unittest discover -s tests -v

打开浏览器合成实验室：

    python -m http.server 8000 --directory app

访问 http://127.0.0.1:8000/decision-lab.html 。此实验室**不连接真实 AI，也不连接真实 TeleAgent**。

**公开精简版已通过 111 项核心测试。**

## 真实性与隐私

- 此仓库公开的是记忆治理**参考实现**，不是 TeleAgent 原生后端。
- 本地角色隔离演示不等于跨真实受信账号的安全测试。
- 不宣称外部缓存已被删除，也不把合成场景写成真实评委测试。
- 不发布个人记忆、USER.md、真实会话日志、快照、API Key、原始比赛视频。

---

<div align="center"><sub>RoleVault · Memory with provenance · 2026</sub></div>
