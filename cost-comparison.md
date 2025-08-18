# OpenRouter Model Cost Comparison for Code Analysis

## Top Cost-Effective Models (as of 2024)

### 🥇 **Claude 3 Haiku** (RECOMMENDED)
- **Input**: $0.25 per 1M tokens
- **Output**: $1.25 per 1M tokens
- **Strengths**: 
  - Excellent code understanding
  - Very fast processing
  - Great at pattern recognition
  - Good for commit analysis and summaries
- **Estimated cost per analysis**: $0.01-$0.05
- **Best for**: Regular automated analysis, cost-conscious users

### 🥈 **GPT-3.5 Turbo**
- **Input**: $0.50 per 1M tokens  
- **Output**: $1.50 per 1M tokens
- **Strengths**:
  - Reliable and well-tested
  - Good general code knowledge
  - Consistent performance
- **Estimated cost per analysis**: $0.02-$0.08
- **Best for**: Users familiar with GPT models

### 🥉 **Llama 3.1 8B Instruct**
- **Input**: $0.05 per 1M tokens
- **Output**: $0.05 per 1M tokens
- **Strengths**:
  - Extremely cheap
  - Open source
  - Decent for basic analysis
- **Estimated cost per analysis**: $0.001-$0.01
- **Best for**: High-volume analysis, budget-conscious

## Cost Estimation for Your Repository

### Typical Analysis Scenario:
- **Repository size**: Medium (50-200 files)
- **Analysis period**: 7-14 days
- **Commit volume**: 10-50 commits
- **Input tokens**: ~5,000-15,000 tokens
- **Output tokens**: ~1,000-3,000 tokens

### Cost Breakdown:

| Model | Input Cost | Output Cost | Total per Analysis |
|-------|------------|-------------|-------------------|
| Claude 3 Haiku | $0.004-$0.012 | $0.001-$0.004 | **$0.005-$0.016** |
| GPT-3.5 Turbo | $0.008-$0.024 | $0.002-$0.005 | **$0.010-$0.029** |
| Llama 3.1 8B | $0.001-$0.002 | $0.000-$0.000 | **$0.001-$0.002** |

## Recommendations by Use Case

### 🎯 **For Your SAP Repository** (Recommended: Claude 3 Haiku)
```yaml
llm:
  provider: "openrouter"
  model: "anthropic/claude-3-haiku"
  temperature: 0.4
  max_tokens: 2500
```
**Why**: Best balance of cost (~$0.01 per analysis) and quality for enterprise code analysis.

### 💰 **Ultra Budget** (Llama 3.1 8B)
```yaml
llm:
  provider: "openrouter"
  model: "meta-llama/llama-3.1-8b-instruct"
  temperature: 0.5
  max_tokens: 2000
```
**Why**: Extremely cheap (~$0.002 per analysis) but still capable for basic insights.

### ⚖️ **Balanced** (GPT-3.5 Turbo)
```yaml
llm:
  provider: "openrouter"
  model: "openai/gpt-3.5-turbo"
  temperature: 0.3
  max_tokens: 3000
```
**Why**: Familiar model with good performance (~$0.02 per analysis).

## Cost Optimization Tips

1. **Reduce `max_tokens`**: Lower values = lower costs
2. **Limit `top_k_files`**: Analyze fewer files per run
3. **Shorter `period_days`**: Less commit history = fewer tokens
4. **Use caching**: Avoid re-analyzing the same data
5. **Batch analysis**: Run less frequently but cover more time

## Monthly Cost Estimates

### Daily Analysis (30 runs/month):
- **Claude 3 Haiku**: $0.15-$0.48/month
- **GPT-3.5 Turbo**: $0.30-$0.87/month
- **Llama 3.1 8B**: $0.03-$0.06/month

### Weekly Analysis (4 runs/month):
- **Claude 3 Haiku**: $0.02-$0.06/month
- **GPT-3.5 Turbo**: $0.04-$0.12/month
- **Llama 3.1 8B**: $0.004-$0.008/month

**Conclusion**: Even with daily analysis, costs are very manageable. Claude 3 Haiku offers the best value for professional code analysis.