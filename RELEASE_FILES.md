# 发布文件清单

原仓：`NGAI-LLMSafeContent/Project_3_Dynamic_Difficulty_Question_Generation_Tool`；源提交：`dab4567f79a60434aa08445f24bb550347afba4d`；分支：`release/1.0`。

本清单逐文件列出发布内容。原有非README实现/配置/资源保持Git对象字节和模式一致；README与发布新增材料单独登记。RELEASE_MANIFEST.json和SHA256SUMS由发布器生成，不形成自引用哈希。

## 来自原仓、原样保留的文件

- `.gitignore`
- `agent_framework/pyproject.toml`
- `agent_framework/scripts/compare_generation_models.py`
- `agent_framework/scripts/generate_benchmark_data.py`
- `agent_framework/scripts/run_resumable_generation.py`
- `agent_framework/scripts/score_benchmark_results.py`
- `agent_framework/uv.lock`
- `configs/h1h4_generation.json`
- `skills/README.md`
- `skills/__init__.py`
- `skills/common/__init__.py`
- `skills/common/io_utils.py`
- `skills/common/models.py`
- `skills/common/utils.py`
- `skills/difficulty_assignment_skill/README.md`
- `skills/difficulty_assignment_skill/__init__.py`
- `skills/difficulty_assignment_skill/difficulty.py`
- `skills/harmful_sample_collection_skill/README.md`
- `skills/harmful_sample_collection_skill/__init__.py`
- `skills/harmful_sample_collection_skill/buffer_pool.py`
- `skills/harmful_sample_collection_skill/extractors.py`
- `skills/harmful_sample_collection_skill/matcher.py`
- `skills/harmless_content_generation_skill/README.md`
- `skills/harmless_content_generation_skill/__init__.py`
- `skills/harmless_content_generation_skill/companion_generator.py`
- `skills/model_guided_output_splicing_skill/README.md`
- `skills/model_guided_output_splicing_skill/__init__.py`
- `skills/model_guided_output_splicing_skill/assembler.py`
- `skills/model_guided_output_splicing_skill/composer.py`
- `skills/pipeline.py`
- `skills/quality_validation_skill/README.md`
- `skills/quality_validation_skill/__init__.py`
- `skills/quality_validation_skill/final_guard.py`
- `skills/quality_validation_skill/quality_gate.py`
- `skills/risk_classification_skill/README.md`
- `skills/risk_classification_skill/__init__.py`
- `skills/risk_classification_skill/label_engine.py`
- `skills/span_formatting_recording_skill/README.md`
- `skills/span_formatting_recording_skill/__init__.py`
- `skills/span_formatting_recording_skill/span_recorder.py`
- `tests/test_continuous_generation.py`
- `tests/test_example_samples.py`
- `ui/app.js`
- `ui/backend.py`
- `ui/index.html`
- `ui/server.py`
- `ui/styles.css`
- `vllm_router/.env.example`
- `vllm_router/main.py`
- `vllm_router/pyproject.toml`

## README及发布新增材料

- `KNOWN_ISSUES.md`
- `LICENSE`
- `README.md`
- `RELEASE_FILES.md`
- `SOURCE_ALIGNMENT.json`
- `THIRD_PARTY_NOTICES.md`
- `examples/generation.example.json`
- `examples/seed.example.json`
- `release_checks.json`
- `requirements.txt`
- `tools/release_check.py`

## 生成的校验文件

- `RELEASE_MANIFEST.json`
- `SHA256SUMS`

## 排除范围

明确弃用的历史原型、旧版本快照、缓存、数据库、用户配置和预跑产物未发布。模型、原始数据/知识库和外部服务按README准备，不以缩减/改写同路径数据文件冒充完整交付。源码原有错误保留，见KNOWN_ISSUES.md。
