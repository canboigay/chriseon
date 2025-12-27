"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { createRun, getInfo, getPositions, listModels, type ModelInfo, type Position } from "@/lib/api";

export default function Home() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [instructions, setInstructions] = useState(
    "You are a precise, professional assistant."
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [apiStatus, setApiStatus] = useState<"checking" | "ok" | "bad">("checking");
  
  const [positions, setPositions] = useState<Position[]>([]);
  const [allModels, setAllModels] = useState<ModelInfo[]>([]);
  const [selectedModels, setSelectedModels] = useState<Record<string, string>>({
    a: "xai:grok-3",
    b: "gemini:gemini-2.0-flash",
    c: "xai:grok-4-0709",
  });
  const [outputLength, setOutputLength] = useState<
    "brief" | "standard" | "comprehensive"
  >("standard");
  const [stagePrompts, setStagePrompts] = useState<Record<string, string>>({});

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const info = await getInfo();
        if (!cancelled && info.service === "chriseon-api") setApiStatus("ok");
        else if (!cancelled) setApiStatus("bad");
        
        // Load positions and models
        const [positionsData, modelsData] = await Promise.all([
          getPositions(),
          listModels(),
        ]);
        
        if (!cancelled) {
          setPositions(positionsData.positions);
          setAllModels(modelsData.models);
          setSelectedModels(positionsData.defaults);
        }
      } catch {
        if (!cancelled) setApiStatus("bad");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const run = await createRun({
        query,
        header_prompt: { instructions },
        selected_models: selectedModels,
        output_length: outputLength,
        stage_prompts: stagePrompts,
      });
      router.push(`/runs/${run.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create run");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen px-6 py-10">
      <main className="chr-container flex flex-col gap-6">
        <header className="flex flex-col gap-2">
          <div className="flex items-center justify-between gap-4">
            <div className="chr-subtle">multi-model orchestrator</div>
            <div
              className="text-xs"
              style={{ color: "rgb(var(--chr-muted))", fontFamily: "var(--chr-font-mono)" }}
            >
              api: {apiStatus === "checking" ? "checking" : apiStatus}
            </div>
          </div>
          <h1 className="chr-h1">chriseon</h1>
          <p className="text-[0.98rem]" style={{ color: "rgb(var(--chr-muted))" }}>
            Round-robin refinement, scoring, and full transparency.
          </p>
        </header>

        <section className="chr-card p-5 sm:p-6">
          <form onSubmit={onSubmit} className="flex flex-col gap-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <label className="flex flex-col gap-2">
                <div className="flex items-baseline justify-between gap-3">
                  <span
                    className="text-sm font-semibold"
                    style={{ color: "rgb(var(--chr-ink))" }}
                  >
                    Query
                  </span>
                </div>
                <textarea
                  className="chr-textarea min-h-[120px]"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Ask anything…"
                  required
                />
              </label>

              <label className="flex flex-col gap-2">
                <div className="flex items-baseline justify-between gap-3">
                  <span
                    className="text-sm font-semibold"
                    style={{ color: "rgb(var(--chr-ink))" }}
                  >
                    System instructions
                  </span>
                </div>
                <textarea
                  className="chr-textarea min-h-[120px]"
                  value={instructions}
                  onChange={(e) => setInstructions(e.target.value)}
                />
              </label>
            </div>

            {/* Output length */}
            <div className="flex flex-col gap-2">
              <div>
                <div className="text-sm font-medium" style={{ color: "rgb(var(--chr-ink))" }}>
                  Output length
                </div>
                <div className="text-xs" style={{ color: "rgb(var(--chr-muted))" }}>
                  Applies to every stage.
                </div>
              </div>

              <div className="flex gap-2">
                {(
                  [
                    { key: "brief", label: "Brief" },
                    { key: "standard", label: "Standard" },
                    { key: "comprehensive", label: "Comprehensive" },
                  ] as const
                ).map((opt) => {
                  const active = outputLength === opt.key;
                  return (
                    <button
                      key={opt.key}
                      type="button"
                      onClick={() => setOutputLength(opt.key)}
                      aria-pressed={active}
                      className="px-3 py-2 rounded-lg text-sm border"
                      style={{
                        borderColor: active
                          ? "rgba(100, 200, 150, 0.55)"
                          : "rgba(255,255,255,0.12)",
                        background: active
                          ? "rgba(100, 200, 150, 0.12)"
                          : "rgba(255,255,255,0.02)",
                        color: "rgb(var(--chr-ink))",
                      }}
                    >
                      {opt.label}
                    </button>
                  );
                })}
              </div>

              <div className="text-xs" style={{ color: "rgb(var(--chr-muted))" }}>
                Comprehensive is bounded (~800–1200 words).
              </div>
            </div>

            {/* Pipeline */}
            <div className="flex flex-col gap-3">
              <div>
                <div className="text-sm font-medium" style={{ color: "rgb(var(--chr-ink))" }}>
                  Pipeline
                </div>
                <div className="text-xs" style={{ color: "rgb(var(--chr-muted))" }}>
                  Draft → Refine → Validate.
                </div>
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                {positions?.map((pos) => {
                  const modelsForPosition = allModels.filter((m) =>
                    m.recommended_for.includes(pos.role)
                  );
                  const currentModel = allModels.find(
                    (m) => m.id === selectedModels[pos.slot]
                  );

                  const stageTitle =
                    pos.role === "draft"
                      ? "Draft"
                      : pos.role === "refine"
                        ? "Refine"
                        : "Validate";

                  const stageSubtext =
                    pos.role === "draft"
                      ? "Creates the first answer."
                      : pos.role === "refine"
                        ? "Improves clarity and fills gaps."
                        : "Checks against your original request.";

                  return (
                    <div
                      key={pos.slot}
                      className="rounded-xl border p-3"
                      style={{
                        borderColor: "rgba(255,255,255,0.10)",
                        background: "rgba(255,255,255,0.02)",
                      }}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div
                            className="text-sm font-medium"
                            style={{ color: "rgb(var(--chr-ink))" }}
                          >
                            {stageTitle}
                          </div>
                          <div className="text-xs" style={{ color: "rgb(var(--chr-muted))" }}>
                            {stageSubtext}
                          </div>
                        </div>

                        <div
                          className="text-[11px] px-1.5 py-0.5 rounded"
                          style={{
                            background: "rgba(255,255,255,0.06)",
                            color: "rgb(var(--chr-muted))",
                            fontFamily: "var(--chr-font-mono)",
                          }}
                          title={pos.name}
                        >
                          {pos.slot.toUpperCase()}
                        </div>
                      </div>

                      <div className="mt-2 flex items-center justify-end gap-2">
                        {currentModel?.supports_tools ? (
                          <span
                            className="text-[11px] px-1.5 py-0.5 rounded"
                            style={{
                              background: "rgba(100, 200, 150, 0.15)",
                              color: "rgb(100, 200, 150)",
                              fontFamily: "var(--chr-font-mono)",
                            }}
                          >
                            tools
                          </span>
                        ) : null}
                      </div>

                      <select
                        id={`model-${pos.slot}`}
                        className="chr-textarea min-h-0 py-2 cursor-pointer mt-1"
                        value={selectedModels[pos.slot]}
                        onChange={(e) =>
                          setSelectedModels({
                            ...selectedModels,
                            [pos.slot]: e.target.value,
                          })
                        }
                      >
                        {(modelsForPosition.length > 0
                          ? modelsForPosition
                          : allModels
                        ).map((model) => {
                          const isRecommended = model.recommended_for.includes(pos.role);
                          const toolsLabel = model.supports_tools ? " [Tools]" : "";
                          const recommendedLabel = isRecommended ? " ⭐" : "";
                          
                          return (
                            <option key={model.id} value={model.id}>
                              {model.name} ({model.provider}){recommendedLabel}{toolsLabel}
                            </option>
                          );
                        })}
                      </select>
                      
                      {/* Model info tooltip */}
                      {currentModel && (
                        <div 
                          className="mt-2 text-xs p-2 rounded-lg border"
                          style={{
                            borderColor: "rgba(var(--chr-border), 0.5)",
                            backgroundColor: "rgba(var(--chr-paper-wash), 0.5)",
                            color: "rgb(var(--chr-muted))",
                          }}
                        >
                          {currentModel.description}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {error ? (
              <div
                className="rounded-xl border px-3 py-2 text-sm"
                style={{
                  borderColor: "rgba(180, 80, 50, 0.35)",
                  background: "rgba(180, 80, 50, 0.10)",
                  color: "rgb(var(--chr-ink))",
                  fontFamily: "var(--chr-font-mono)",
                }}
              >
                {error}
              </div>
            ) : null}

            {/* Advanced stage prompts (append-only) */}
            <details className="rounded-xl border p-3" style={{ borderColor: "rgba(255,255,255,0.10)" }}>
              <summary
                className="cursor-pointer text-sm"
                style={{ color: "rgb(var(--chr-ink))", fontWeight: 600 }}
              >
                Advanced options
              </summary>
              <div className="text-xs mt-1" style={{ color: "rgb(var(--chr-muted))" }}>
                These instructions are appended per stage and won’t remove Chriseon’s built-in chaining prompts.
              </div>
              <div className="flex flex-col gap-3 mt-3">
                {positions?.map((pos) => (
                  <label key={`stage-prompt-${pos.slot}`} className="flex flex-col gap-2">
                    <span className="text-sm font-medium" style={{ color: "rgb(var(--chr-ink))" }}>
                      {pos.role === "draft"
                        ? "Draft stage"
                        : pos.role === "refine"
                          ? "Refine stage"
                          : "Validate stage"}
                    </span>
                    <span className="text-xs" style={{ color: "rgb(var(--chr-muted))" }}>
                      Optional extra instructions (append-only)
                    </span>
                    <textarea
                      className="chr-textarea min-h-[90px]"
                      value={stagePrompts[pos.slot] || ""}
                      onChange={(e) =>
                        setStagePrompts({ ...stagePrompts, [pos.slot]: e.target.value })
                      }
                      placeholder={`Optional: extra instructions for stage ${pos.slot.toUpperCase()} (will be appended)`}
                    />
                  </label>
                ))}
              </div>
            </details>

            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <button type="submit" disabled={isSubmitting} className="chr-button">
                {isSubmitting ? "Starting" : "Start run"}
              </button>

              <div className="chr-subtle" style={{ opacity: 0.85 }}>
                stores all artifacts by default
              </div>
            </div>

            <p
              className="text-xs"
              style={{ color: "rgb(var(--chr-muted))", fontFamily: "var(--chr-font-mono)" }}
            >
              A drafts → B refines → C validates. Tools-enabled models may research.
            </p>
          </form>
        </section>
      </main>
    </div>
  );
}
