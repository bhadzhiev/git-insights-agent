# OpenRouter.ai Integration Guide

This guide explains how to use OpenRouter.ai with the Git Batch Analyzer for AI-powered code analysis.

## What is OpenRouter.ai?

OpenRouter.ai provides unified access to multiple AI models (GPT-4, Claude, Llama, etc.) through a single API. This gives you:

- **Model Choice**: Access to 20+ different AI models
- **Cost Optimization**: Compare prices and choose the best model for your needs
- **Reliability**: Fallback options if one model is unavailable
- **Unified API**: OpenAI-compatible interface for easy integration

## Setup

1. **Get an API Key**
   - Visit [OpenRouter.ai](https://openrouter.ai/)
   - Sign up for an account
   - Go to [API Keys](https://openrouter.ai/keys) and create a new key
   - Your key will start with `sk-or-v1-`

2. **Configure Git Batch Analyzer**
   ```yaml
   llm:
     provider: "openrouter"
     model: "anthropic/claude-3.5-sonnet"  # Choose your preferred model
     temperature: 0.3
     api_key: "sk-or-v1-your-api-key-here"
     max_tokens: 4000
   ```

## Recommended Models for Code Analysis

### Best Overall Quality
- **`anthropic/claude-3.5-sonnet`** - Excellent for complex code analysis and architectural insights
- **`openai/gpt-4-turbo`** - Strong performance with good speed

### Cost-Effective Options
- **`anthropic/claude-3-haiku`** - Fast and affordable, good for basic analysis
- **`openai/gpt-3.5-turbo`** - Reliable and cost-effective

### Open Source Alternatives
- **`meta-llama/llama-3.1-70b-instruct`** - High-quality open source model
- **`mistralai/mixtral-8x7b-instruct`** - Good balance of quality and speed

### Large Context Models (for big codebases)
- **`google/gemini-pro-1.5`** - Handles very large contexts well
- **`anthropic/claude-3-opus`** - Premium model with excellent reasoning

## Configuration Options

```yaml
llm:
  provider: "openrouter"
  model: "anthropic/claude-3.5-sonnet"
  temperature: 0.3              # 0.0-2.0, lower = more focused
  api_key: "sk-or-v1-..."       # Your OpenRouter API key
  base_url: "https://openrouter.ai/api/v1"  # Auto-set for openrouter
  max_tokens: 4000              # Limit response length
```

### Temperature Guidelines
- **0.0-0.3**: Very focused, deterministic analysis (recommended for code)
- **0.4-0.7**: Balanced creativity and focus
- **0.8-1.0**: More creative, varied responses
- **1.1-2.0**: Highly creative (not recommended for code analysis)

### Max Tokens Guidelines
- **1000-2000**: Brief summaries and insights
- **3000-4000**: Detailed analysis (recommended)
- **5000+**: Comprehensive reports (may be slower/more expensive)

## Example Configurations

### Your SAP Integrations Repository
```yaml
repositories:
  - url: "https://bhadzhiev@git.eu-west-1.codecatalyst.aws/v1/linkin/SAP/sap-integrations"
    branch: "develop"

period_days: 14
stale_days: 30
output_file: "sap-integrations-analysis.md"

llm:
  provider: "openrouter"
  model: "anthropic/claude-3.5-sonnet"
  temperature: 0.3
  api_key: "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"
  max_tokens: 4000
```

### Budget-Conscious Setup
```yaml
llm:
  provider: "openrouter"
  model: "anthropic/claude-3-haiku"
  temperature: 0.4
  api_key: "sk-or-v1-your-api-key"
  max_tokens: 2000
```

### High-Quality Analysis
```yaml
llm:
  provider: "openrouter"
  model: "anthropic/claude-3.5-sonnet"
  temperature: 0.2
  api_key: "sk-or-v1-your-api-key"
  max_tokens: 6000
```

## Usage

1. **Create your configuration file** (e.g., `config.yaml`)
2. **Run the analyzer**:
   ```bash
   python -m git_batch_analyzer --config config.yaml
   ```

## Pricing Considerations

OpenRouter charges per token used. Approximate costs (as of 2024):

- **Claude 3 Haiku**: ~$0.25 per 1M input tokens
- **GPT-3.5 Turbo**: ~$0.50 per 1M input tokens  
- **Claude 3.5 Sonnet**: ~$3.00 per 1M input tokens
- **GPT-4 Turbo**: ~$10.00 per 1M input tokens

For typical repository analysis (10-50 files), expect costs of $0.01-$0.50 per analysis.

## Troubleshooting

### Common Issues

1. **Invalid API Key**
   - Ensure your key starts with `sk-or-v1-`
   - Check that the key is active in your OpenRouter dashboard

2. **Model Not Available**
   - Some models may have usage limits or be temporarily unavailable
   - Try a different model from the same provider

3. **Rate Limits**
   - OpenRouter has rate limits per model
   - Consider using a different model or waiting before retrying

4. **High Costs**
   - Use `max_tokens` to limit response length
   - Choose more cost-effective models like Claude 3 Haiku
   - Reduce the number of files analyzed with `top_k_files`

### Getting Help

- [OpenRouter Documentation](https://openrouter.ai/docs)
- [OpenRouter Discord](https://discord.gg/openrouter)
- [Model Pricing](https://openrouter.ai/models)

## Security Notes

- **Never commit API keys** to version control
- Consider using environment variables: `OPENROUTER_API_KEY`
- Rotate API keys regularly
- Monitor usage in your OpenRouter dashboard