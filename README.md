# 动态难度题目生成工具

组合种子、伴随内容和模型生成结果，构建不同难度的题目并进行质量检查。

发布单位：NGAI-LLMSafeContent。发布分支：`release/1.0`；更新日期：2026-11-21；自研代码许可：Apache-2.0，第三方保留原许可。

## 功能

- H1–H4难度调度、并行生成、断点恢复与尾部修复
- 模型引导拼接、桥接/配对检查及最终guard
- Web任务管理、样例预览和本地vLLM路由

## 安装与快速开始

Python 3.12；主流程使用标准库。本地vLLM部署另需uv、GPU/CUDA和合法模型，或配置兼容服务。

从公开仓下载同一发布分支：

```bash
git clone --branch release/1.0 https://github.com/NGAI-LLMSafeContent-OpenSource/Project_3_Dynamic_Difficulty_Question_Generation_Tool-release.git
cd Project_3_Dynamic_Difficulty_Question_Generation_Tool-release
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell改用 .venv\Scripts\Activate.ps1
```

以下命令均以仓库根目录为起点，注释中的外部条件需先准备：

```bash
python ui/server.py --host 127.0.0.1 --port 8766
# 编辑examples/generation.example.json中的模型、地址和API环境变量
python agent_framework/scripts/generate_benchmark_data.py --config examples/generation.example.json
```

## 使用与输出

浏览器访问 `http://127.0.0.1:8766`。示例配置显式启用 `llm_composer.enabled=true`，使用中性自编种子；原始配置保留在 `configs/h1h4_generation.json`。输出写入配置的runs目录，UI可查询任务和预览样例。本地模型路由入口在 `vllm_router/main.py`。

## 配置与外部依赖

真实种子、生成/审核模型、GPU和历史样本需自备。当前示例只验证流程，不宣称难度、风险与生成质量已经真实模型验收。

真实凭据只在自己的运行环境或平台Secrets中配置，不提交.env、用户上传、模型权重或运行结果。原仓文件中的内网服务地址经发布负责人确认按原样保留，使用者应在本地配置自己的可达服务。

## 验证与已知问题

完成对应依赖准备后运行：

```bash
python tools/release_check.py
```

检查包含发布文件完整性、原仓文件一致性与声明的最小测试。它不会自动下载模型或申请API，也不代表全部真实业务/准确率验收。保留的原仓错误、未运行项及外部依赖见 [KNOWN_ISSUES.md](KNOWN_ISSUES.md)。

## 发布版本与文件清单

本版本以原开发仓主分支提交 `dab4567f79a60434aa08445f24bb550347afba4d` 为源。功能实现与对应原文件保持一致；README、许可说明和发布辅助材料单独登记。当前功能的必要源码、配置、界面与运行资源保留，明确弃用的原型、历史结果和开发缓存不捆绑。

- [逐文件发布清单](RELEASE_FILES.md)
- [原仓文件与Git对象对应关系](SOURCE_ALIGNMENT.json)
- [完整文件SHA-256及权限](RELEASE_MANIFEST.json)，校验表为SHA256SUMS

校验值按Git存储字节生成；若原.gitattributes规定检出换行转换，请用Git对象或发布检查脚本校验，避免将LF/CRLF误认为源码变化。各公开平台release/1.0使用同一个提交，平台生成的运行分支不属于此发布清单。

## 反馈、贡献与许可证

请通过 [公开仓Issues](https://github.com/NGAI-LLMSafeContent-OpenSource/Project_3_Dynamic_Difficulty_Question_Generation_Tool-release/issues) 提交复现步骤、环境和日志摘要，勿附真实凭据或用户数据。代码问题由课题维护者在原开发仓处理，发布负责人同步审核后的版本；不要仅修一个平台造成分歧。

自研代码采用[Apache-2.0](LICENSE)。模型、数据集、外部服务和第三方代码遵循各自许可与使用条件，见[第三方说明](THIRD_PARTY_NOTICES.md)。
