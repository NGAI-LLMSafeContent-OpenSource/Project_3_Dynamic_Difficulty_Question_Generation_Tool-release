# Dynamic Difficulty Question Generation Skills

The Agent composes these skills in order:

```text
harmful_sample_collection_skill
-> risk_classification_skill
-> harmless_content_generation_skill
-> difficulty_assignment_skill
-> model_guided_output_splicing_skill
-> span_formatting_recording_skill
-> quality_validation_skill
```

The public directory names follow the project description. `pipeline.py` wires the skills together and preserves the generated sample contract used by the Agent framework.
