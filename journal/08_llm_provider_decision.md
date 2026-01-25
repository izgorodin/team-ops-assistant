# LLM Provider Decision: NVIDIA NIM + Qwen3

**Date:** 2026-01-25
**Status:** Compliant

## Context

The technical guidelines recommended:
- LangChain/LangGraph for orchestration
- Qwen3 model for LLM operations

## Decision

**Use NVIDIA NIM API with Qwen3-Next-80B-A3B-Instruct model.**

This fully complies with the guidelines:
- LangChain/LangGraph for orchestration ✅
- Qwen3 model ✅ (via NVIDIA NIM)

## Configuration

Single source of truth: `configuration.yaml`

```yaml
llm:
  model: "qwen/qwen3-next-80b-a3b-instruct"
  base_url: "https://integrate.api.nvidia.com/v1"
```

## Why NVIDIA NIM (not Together)

1. **Free for Testing**: NVIDIA NIM provides free API access for development and testing
2. **Same Model Available**: Qwen3-Next-80B-A3B-Instruct available on both platforms
3. **OpenAI-Compatible API**: Seamless integration with `langchain-openai`
4. **Easy Migration**: Can switch to Together or self-hosted NVIDIA for production
5. **Familiar & Convenient**: Developer preference for known tooling

## Model Capabilities

- Reliable tool calling for agent workflows
- Multi-language support (English, Russian)
- Response times within Telegram's 30s webhook limit

## Production Migration Options

When moving to production, several options available:

1. **Stay on NVIDIA NIM** - host on NVIDIA infrastructure
2. **Switch to Together** - change `base_url` to `https://api.together.xyz/v1`
3. **Self-host** - deploy Qwen3 model on own infrastructure

Migration requires only config change - no code changes needed.

## Conclusion

The implementation uses the recommended Qwen3 model, hosted on NVIDIA NIM infrastructure. This meets all technical requirements while providing free testing and easy production migration paths.
