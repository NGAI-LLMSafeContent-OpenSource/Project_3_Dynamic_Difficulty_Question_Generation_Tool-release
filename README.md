# 动态难度题目生成工具

发布方 NGAI-LLMSafeContent；版本 1.0；日期 2026-11-04；Apache-2.0。
源仓库 NGAI-LLMSafeContent/Project_3_Dynamic_Difficulty_Question_Generation_Tool，固定提交 dab4567f79a60434aa08445f24bb550347afba4d。

公开调度器、生成技能、质量检查和浏览器界面，不含原始种子数据、历史生成样本、模型或旧评测结果。独立可选 vllm_router 未纳入最小包，用户可直接配置兼容 OpenAI 的服务。

## 前置条件与最小运行

Python >=3.12；主程序仅使用标准库，无需 pip 安装。根目录执行：

```sh
python tools/release_smoke.py
python ui/server.py --host 127.0.0.1 --port 8766
```

浏览器访问 http://127.0.0.1:8766 。GET /api/health、/api/generation/options、/api/example-samples 可检查运行情况。samples/samples.jsonl 中仅 3 条新编写的中性示例，明确标记为 release_fixture，不声称由模型生成或已通过风险评审。原样例数据相关的历史测试未纳入本包，避免用虚构样例伪造原评测结果。

## 模型与生成配置

完整生成需要自行准备有权使用的种子数据、兼容 OpenAI 的模型服务和凭据。examples/generation.example.json 展示配置结构，设置 api_base、model 和用户环境变量 QUESTION_MODEL_API_KEY 后，运行：

```sh
python agent_framework/scripts/generate_benchmark_data.py --config examples/generation.example.json
```

示例地址是本机占位，未提供模型服务；原始知识库默认路径未随包公开，界面中须替换为自己的路径。提示词代码随自研源码发布，真实模型和数据遵循各自许可，不将凭据/运行结果提交到仓库。

自动验证现有并行调度、断点恢复、JSONL 尾部修复与 API 预览测试，并实际启动本地 HTTP 服务检查页面、健康、选项、示例和空任务列表。测试内部使用自造输入和假模型，不验证实际生成质量、风险检测能力或外部模型推理。

发布文件、源提交与校验见 RELEASE_MANIFEST.json、SHA256SUMS；第三方条件见 THIRD_PARTY_NOTICES.md。
