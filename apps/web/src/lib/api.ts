export type RunCreateRequest = {
  query: string;
  header_prompt?: Record<string, unknown>;
  selected_models?: Record<string, string>;
  output_length?: "brief" | "standard" | "comprehensive";
  stage_prompts?: Record<string, string>;
  budget?: Record<string, unknown>;
  credential_mode?: Record<string, "byok" | "managed" | "auto">;
};

export type RunCreateResponse = {
  id: string;
  status: string;
};

export type RunOut = {
  id: string;
  status: string;
  query: string;
  header_prompt: Record<string, unknown>;
  selected_models: Record<string, string>;
  budget: Record<string, unknown>;
  total_usage: Record<string, unknown>;
  error?: string | null;
};

export type ArtifactOut = {
  id: string;
  pass_index: number;
  model_id: string;
  role: string;
  output_text: string;
  error?: string | null;
  usage?: Record<string, unknown>;
  score?: {
    total?: number;
    dimensions?: {
      alignment?: number;
      completeness?: number;
      consensus?: number | null;
      factual_accuracy?: number | null;
    };
    notes?: string[];
    meta?: Record<string, unknown>;
  } | null;
};

export type ModelInfo = {
  id: string;
  name: string;
  provider: string;
  description: string;
  supports_tools: boolean;
  recommended_for: string[];
};

export type Position = {
  slot: string;
  role: string;
  name: string;
  description: string;
};

export type ModelsResponse = {
  models: ModelInfo[];
  count: number;
};

export type PositionsResponse = {
  positions: Position[];
  defaults: Record<string, string>;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
  "http://localhost:8090";

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        "content-type": "application/json",
        ...(init?.headers || {}),
      },
      cache: "no-store",
    });

    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || `Request failed (${res.status})`);
    }

    return (await res.json()) as T;
  } catch (err) {
    // Browser often reports network/CORS as a generic TypeError("Failed to fetch").
    const base = API_BASE;
    if (err instanceof TypeError) {
      throw new Error(
        `Failed to reach API at ${base}. Make sure chriseon API is running and accessible (CORS).`
      );
    }
    throw err;
  }
}

export async function getInfo(): Promise<{ service: string; version: string }> {
  return http<{ service: string; version: string }>("/v1/info");
}

export async function createRun(body: RunCreateRequest): Promise<RunCreateResponse> {
  return http<RunCreateResponse>("/v1/runs", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getRun(runId: string): Promise<RunOut> {
  return http<RunOut>(`/v1/runs/${encodeURIComponent(runId)}`);
}

export async function getArtifacts(runId: string): Promise<{ artifacts: ArtifactOut[] }> {
  return http(`/v1/runs/${encodeURIComponent(runId)}/artifacts`);
}

export async function listModels(position?: string): Promise<ModelsResponse> {
  const query = position ? `?position=${encodeURIComponent(position)}` : "";
  return http<ModelsResponse>(`/v1/models${query}`);
}

export async function getPositions(): Promise<PositionsResponse> {
  return http<PositionsResponse>("/v1/models/positions/list");
}
