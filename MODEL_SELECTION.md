# Model Selection System

## Overview

The model selection system allows users to choose which models run in each position of the sequential refinement pipeline (A → B → C). Each position has specific recommendations based on the role it plays.

## Architecture

### Backend Components

#### 1. Configuration (`services/api/app/models_config.py`)

Central configuration defining:
- **Available Models**: 14 models across 4 providers (OpenAI, Anthropic, Gemini, xAI)
- **Position Definitions**: Draft (A), Refine (B), Validate/Synthesis (C)
- **Recommendations**: Which models are best suited for each position
- **Tool Support**: Which models support function calling

**Example Model Entry:**
```python
{
    "id": "anthropic:claude-3-5-sonnet-latest",
    "name": "Claude 3.5 Sonnet",
    "provider": "anthropic",
    "description": "Best Claude model for coding, analysis, and complex tasks",
    "supports_tools": True,
    "recommended_for": ["refine", "synthesis"],
}
```

**Default Selections:**
- Position A (Draft): `openai:gpt-4o-mini` - Fast initial response
- Position B (Refine): `anthropic:claude-3-5-sonnet-latest` - Deep analysis
- Position C (Validate): `gemini:gemini-2.0-flash` - Final validation

#### 2. API Endpoints (`services/api/app/routes/models.py`)

Three endpoints for model discovery:

**GET `/v1/models`**
- Lists all available models
- Optional `?position=a` query param to filter by position
- Returns model metadata including tool support

**GET `/v1/models/{model_id}`**
- Get details for a specific model
- Model ID format: `provider:model`

**GET `/v1/models/positions/list`**
- Returns position definitions (A/B/C)
- Includes default model selections
- Provides descriptions of each position's role

### Frontend Components

#### 1. TypeScript Types (`apps/web/src/lib/api.ts`)

Added types:
```typescript
export type ModelInfo = {
  id: string;
  name: string;
  provider: string;
  description: string;
  supports_tools: boolean;
  recommended_for: string[];
};

export type Position = {
  slot: string;        // "a", "b", "c"
  role: string;        // "draft", "refine", "synthesis"
  name: string;        // Display name
  description: string; // Role description
};
```

API functions:
- `listModels(position?: string): Promise<ModelsResponse>`
- `getPositions(): Promise<PositionsResponse>`

#### 2. Home Page UI (`apps/web/src/app/page.tsx`)

**Features:**
- Dynamic model selection dropdowns for each position
- Filters models to show recommendations per position
- Visual indicator for models that support tools (green "tools" badge)
- Position descriptions to guide selection
- Persists selections and passes to run creation

**UI Flow:**
1. Page loads → Fetches positions and models from API
2. Displays three dropdowns (A, B, C)
3. Each dropdown shows recommended models for that position
4. User selects models → Creates run with `selected_models` parameter

## Position Roles

### Position A: Draft
**Role**: Creates the initial response to the user's query.

**Recommended Models:**
- GPT-4o Mini (fast, affordable)
- Claude 3.5 Haiku (quick responses)
- Gemini 1.5 Flash (efficient)
- Gemini 2.0 Flash (latest fast model)

**Strategy**: Use faster, more affordable models that can generate comprehensive initial drafts.

### Position B: Refine
**Role**: Analyzes Position A's output and produces an improved version.

**Recommended Models:**
- Claude 3.5 Sonnet (excellent at analysis and improvement)
- GPT-4o (strong reasoning)
- Gemini 1.5 Pro (deep understanding)
- Gemini 2.0 Flash (balanced performance)

**Strategy**: Use models with strong analytical and reasoning capabilities to identify gaps and improve the draft.

### Position C: Validate/Synthesis
**Role**: Validates Position B's output against the original query and creates the final response.

**Recommended Models:**
- Claude 3.5 Sonnet (thorough validation)
- Claude 3 Opus (most powerful reasoning)
- GPT-4o (comprehensive validation)
- Gemini 1.5 Pro (extensive context)
- Gemini 2.0 Flash (fast validation)

**Strategy**: Use high-capability models that excel at validation, fact-checking, and synthesis.

## Tool Support

Models marked with `supports_tools: true` can:
- Search the web (DuckDuckGo)
- Fetch URL content
- Query breach databases (OSINT)

These models can research concepts and gather data during their refinement pass, leading to more accurate and comprehensive outputs.

**Models with Tool Support:**
- All OpenAI models (GPT-4o, GPT-4o Mini, GPT-4 Turbo, GPT-3.5 Turbo)
- All Anthropic Claude models
- All Gemini models
- xAI Grok: Currently **no tool support** (SDK limitation)

## Usage Example

### API Request
```json
POST /v1/runs
{
  "query": "Explain quantum computing",
  "header_prompt": {
    "instructions": "You are a precise, professional assistant."
  },
  "selected_models": {
    "a": "openai:gpt-4o-mini",
    "b": "anthropic:claude-3-5-sonnet-latest",
    "c": "gemini:gemini-2.0-flash"
  }
}
```

### Execution Flow
1. **Position A** (GPT-4o Mini): Generates initial quantum computing explanation
2. **Position B** (Claude 3.5 Sonnet): 
   - Receives Position A's output
   - Can use tools to verify facts or find recent research
   - Produces refined, improved explanation
3. **Position C** (Gemini 2.0 Flash):
   - Receives Position B's output and original query
   - Can use tools to fact-check claims
   - Validates completeness and accuracy
   - Produces final polished response

## Adding New Models

To add a new model:

1. Add entry to `AVAILABLE_MODELS` in `models_config.py`:
```python
{
    "id": "provider:model-name",
    "name": "Display Name",
    "provider": "provider",
    "description": "Model description",
    "supports_tools": True/False,
    "recommended_for": ["draft", "refine", "synthesis"],
}
```

2. Ensure provider is implemented in `services/worker/worker/providers/`

3. Model automatically appears in frontend dropdowns

## Benefits

1. **Flexibility**: Users choose the best models for their use case
2. **Cost Control**: Mix expensive and affordable models strategically
3. **Optimization**: Position-specific recommendations guide optimal choices
4. **Transparency**: Clear indication of which models support tools
5. **Experimentation**: Easy A/B testing of different model combinations
