"use client";

import * as React from "react";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";

import { getArtifacts, getRun, type ArtifactOut } from "@/lib/api";

const NEURAL_LINES: Record<PassPhase, string[]> = {
  idle: [],
  planned: ["queueing…"],
  generating: [
    "Σ wᵢ·xᵢ → logits[t]",
    "softmax(logits) → p(token)",
    "sampling next token…",
  ],
  scoring: [
    "Δ consistency → s_c",
    "Δ completeness → s_k",
    "Σ weights → total_score",
  ],
  done: [],
  error: [],
};

const STATUS_TOKENS: Record<string, string[]> = {
  queued: ["[queue]", "→ [dispatch]", "…"],
  running: ["[draft]", "[refine]", "[score]", "[aggregate]"],
  completed: ["[done]"],
};

function NeuralTicker({ phase }: { phase: PassPhase }) {
  const [idx, setIdx] = useState(0);
  const lines = NEURAL_LINES[phase] || [];

  useEffect(() => {
    if (lines.length === 0) return;
    setIdx(0);
    const id = setInterval(() => {
      setIdx((i) => (i + 1) % lines.length);
    }, 900);
    return () => clearInterval(id);
  }, [phase, lines.length]);

  if (lines.length === 0) return null;

  return (
    <div
      className="rounded-xl border px-3 py-2"
      style={{
        borderColor: "rgba(var(--chr-border), 0.55)",
        background:
          "repeating-linear-gradient(90deg, rgba(var(--chr-paper-wash),0.6) 0, rgba(var(--chr-paper-wash),0.9) 4px, rgba(var(--chr-paper-wash),0.1) 8px)",
        opacity: 0.95,
      }}
    >
      <div
        className="text-[11px]"
        style={{ fontFamily: "var(--chr-font-mono)", color: "rgb(var(--chr-muted))" }}
      >
        <span className="mr-1 text-[10px] opacity-70">λ&gt;</span>
        {lines[idx]}
      </div>
    </div>
  );
}

function BinaryBand({ active }: { active: boolean }) {
  if (!active) return null;
  const pattern = "1010 1101 0110 1110 0011 0101 1001 0001";
  return (
    <div
      className="mt-2 h-5 overflow-hidden rounded-full border"
      style={{
        borderColor: "rgba(var(--chr-border), 0.6)",
        background: "rgba(var(--chr-paper-wash),0.35)",
        fontFamily: "var(--chr-font-mono)",
        fontSize: "10px",
        color: "rgba(var(--chr-muted),0.9)",
      }}
    >
      <div className="animate-[marquee_8s_linear_infinite] whitespace-nowrap px-3">
        {pattern} {pattern} {pattern}
      </div>
    </div>
  );
}

function TokenStream({ status }: { status: string }) {
  const tokens = STATUS_TOKENS[status] || ["[idle]"];
  const [i, setI] = useState(0);

  useEffect(() => {
    setI(0);
    const id = setInterval(() => setI((x) => (x + 1) % tokens.length), 600);
    return () => clearInterval(id);
  }, [status, tokens.length]);

  return (
    <div
      className="text-[11px]"
      style={{ fontFamily: "var(--chr-font-mono)", color: "rgb(var(--chr-muted))" }}
    >
      {tokens.slice(0, i + 1).join(" ")}
    </div>
  );
}

type PassPhase = "idle" | "planned" | "generating" | "scoring" | "done" | "error";

type PassState = {
  passIndex: number;
  modelId?: string;
  phase: PassPhase;
  error?: string | null;
  score?: ArtifactOut["score"];
};

type EventPayload = {
  pass_index?: unknown;
  model_id?: unknown;
  error?: unknown;
  total?: unknown;
  data?: unknown;
  chunk?: unknown;
};

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

function parseEventPayload(raw: string): EventPayload | null {
  if (!raw) return null;
  try {
    const v: unknown = JSON.parse(raw);
    if (!isObject(v)) return null;
    return v as EventPayload;
  } catch {
    return null;
  }
}

function clamp01(n: number) {
  if (Number.isNaN(n)) return 0;
  if (n < 0) return 0;
  if (n > 1) return 1;
  return n;
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  const pct = Math.round(clamp01(value) * 100);
  return (
    <div className="flex items-center gap-3">
      <div className="w-28 text-[11px]" style={{ fontFamily: "var(--chr-font-mono)", color: "rgb(var(--chr-muted))" }}>
        {label}
      </div>
      <div
        className="h-2 flex-1 overflow-hidden rounded-full border"
        style={{ borderColor: "rgba(var(--chr-border), 0.6)", background: "rgba(var(--chr-paper-wash), 0.55)" }}
      >
        <div
          className="h-full transition-all duration-700"
          style={{ width: `${pct}%`, background: "rgb(var(--chr-ink))", opacity: 0.85 }}
        />
      </div>
      <div className="w-10 text-right text-[11px]" style={{ fontFamily: "var(--chr-font-mono)", color: "rgb(var(--chr-muted))" }}>
        {pct}
      </div>
    </div>
  );
}

export default function RunPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = React.use(params);
  const apiBase = useMemo(
    () =>
      (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8090").replace(
        /\/$/,
        ""
      ),
    []
  );

  const [status, setStatus] = useState<string>("loading");
  const [artifacts, setArtifacts] = useState<ArtifactOut[]>([]);
  const [activeTab, setActiveTab] = useState<number>(1);
  const [events, setEvents] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  
  // Streaming text: passIndex -> accumulated text
  const [streamingText, setStreamingText] = useState<Record<number, string>>({});
  // Streaming metadata: track chunks and timing
  const [streamingMeta, setStreamingMeta] = useState<Record<number, { chunkCount: number; startTime: number; approxTokens?: number }>>({});

  const isWaitingForWorker =
    status === "queued" && artifacts.length === 0 && events.length === 0;

  // Auto-switch tabs to the latest artifact as they arrive (only if user hasn't manually switched back)
  const lastArtifactIndex = artifacts.length > 0 ? artifacts[artifacts.length - 1].pass_index : 1;
  useEffect(() => {
    if (status === "running" || status === "queued") {
      setActiveTab(lastArtifactIndex);
    }
  }, [lastArtifactIndex, status]);

  const maxPasses = 3; // MVP currently generates passes 1–3. Increase to 9 when round-robin is enabled.
  const [passStates, setPassStates] = useState<PassState[]>(() =>
    Array.from({ length: maxPasses }, (_, i) => ({ passIndex: i + 1, phase: "idle" as const }))
  );

  async function refreshArtifacts() {
    const data = await getArtifacts(runId);
    const arts = data.artifacts || [];
    setArtifacts(arts);

    // Hydrate pass state from persisted artifacts (useful on refresh/reload).
    setPassStates((prev) => {
      const next = prev.map((p) => ({ ...p }));
      for (const a of arts) {
        const idx = next.findIndex((p) => p.passIndex === a.pass_index);
        if (idx === -1) continue;

        next[idx].modelId = a.model_id;
        next[idx].error = a.error || null;
        next[idx].score = a.score ?? null;

        if (a.error) next[idx].phase = "error";
        else if (a.score?.total != null) next[idx].phase = "done";
        else if (a.output_text) next[idx].phase = "scoring";
        else next[idx].phase = next[idx].phase === "idle" ? "planned" : next[idx].phase;
      }
      return next;
    });
  }

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const run = await getRun(runId);
        if (!cancelled) setStatus(run.status || "unknown");
        await refreshArtifacts();
      } catch (e) {
        if (!cancelled)
          setError(e instanceof Error ? e.message : "Failed to load run");
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  useEffect(() => {
    const es = new EventSource(`${apiBase}/v1/runs/${runId}/events`);

    function onAnyEvent(e: MessageEvent) {
      const raw = typeof e.data === "string" ? e.data : "";
      setEvents((prev) => [`${e.type}: ${raw}`, ...prev]);

      const payload = parseEventPayload(raw);

      if (e.type === "run.started") setStatus("running");
      if (e.type === "run.completed") setStatus("completed");

      // Handle streaming chunks
      if (e.type === "artifact.chunk" && payload) {
        const passIndex = typeof payload.pass_index === "number" ? payload.pass_index : null;
        const chunk = typeof payload.chunk === "string" ? payload.chunk : "";
        if (passIndex != null && chunk) {
          setStreamingText((prev) => ({
            ...prev,
            [passIndex]: (prev[passIndex] || "") + chunk,
          }));
          
          // Track streaming metadata
          setStreamingMeta((prev) => {
            const existing = prev[passIndex];
            if (!existing) {
              return {
                ...prev,
                [passIndex]: { chunkCount: 1, startTime: Date.now() },
              };
            }
            return {
              ...prev,
              [passIndex]: { ...existing, chunkCount: existing.chunkCount + 1 },
            };
          });
        }
      }
      
      // Handle progress updates
      if (e.type === "artifact.progress" && payload) {
        const passIndex = typeof payload.pass_index === "number" ? payload.pass_index : null;
        const approxTokens = typeof payload.approx_tokens === "number" ? payload.approx_tokens : 0;
        if (passIndex != null) {
          setStreamingMeta((prev) => ({
            ...prev,
            [passIndex]: { ...prev[passIndex], approxTokens },
          }));
        }
      }
      
      // Real-time animation driver.
      if (payload) {
        const passIndex = typeof payload.pass_index === "number" ? payload.pass_index : null;
        if (passIndex != null) {
          setPassStates((prev) => {
            const next = prev.map((p) => ({ ...p }));
            const idx = next.findIndex((p) => p.passIndex === passIndex);
            if (idx === -1) return prev;

            if (typeof payload.model_id === "string") next[idx].modelId = payload.model_id;

            if (e.type === "artifact.planned") next[idx].phase = "planned";
            if (e.type === "artifact.started") {
              next[idx].phase = "generating";
              // Clear streaming text and metadata for this pass when starting
              setStreamingText((prev) => ({ ...prev, [passIndex]: "" }));
              setStreamingMeta((prev) => ({ ...prev, [passIndex]: { chunkCount: 0, startTime: Date.now() } }));
            }
            if (e.type === "score.started") next[idx].phase = "scoring";

            if (e.type === "artifact.error") {
              next[idx].phase = "error";
              next[idx].error = typeof payload.error === "string" ? payload.error : "error";
            }

            if (e.type === "score.created") {
              const total = typeof payload.total === "number" ? payload.total : undefined;
              const data = isObject(payload.data) ? payload.data : {};

              next[idx].phase = "done";
              next[idx].score = {
                total,
                ...(data as Record<string, unknown>),
              } as ArtifactOut["score"];
            }

            return next;
          });
        }
      }

      // Keep persisted views up to date.
      if (
        e.type === "artifact.created" ||
        e.type === "artifact.error" ||
        e.type === "score.created" ||
        e.type === "run.completed"
      ) {
        refreshArtifacts().catch(() => undefined);
      }
    }

    const types = [
      "run.queued",
      "run.started",
      "run.completed",
      "artifact.planned",
      "artifact.started",
      "artifact.chunk",
      "artifact.progress",
      "artifact.created",
      "artifact.error",
      "score.started",
      "score.created",
    ];
    for (const t of types) es.addEventListener(t, onAnyEvent);
    es.onerror = () => {
      // leave the connection to auto-retry
    };

    return () => {
      es.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, apiBase]);

  // Helper to find artifact for current tab
  const currentArtifact = artifacts.find((a) => a.pass_index === activeTab);
  const currentPassState = passStates.find((p) => p.passIndex === activeTab);

  return (
    <div className="min-h-screen px-6 py-8">
      <main className="mx-auto flex w-full max-w-5xl flex-col gap-6">
        {/* Header */}
        <header className="flex items-start justify-between gap-6">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-3">
              <Link href="/" className="chr-subtle hover:underline">
                ← back
              </Link>
              <span className="text-xs text-gray-400">/</span>
              <div className="chr-subtle">run {runId.slice(0, 8)}…</div>
            </div>
            <div className="flex items-center gap-3 mt-1">
              <div
                className={`text-sm ${
                  status === "queued" || status === "running" ? "animate-pulse" : ""
                }`}
                style={{ fontFamily: "var(--chr-font-mono)" }}
              >
                status: <span style={{ color: "rgb(var(--chr-ink))" }}>{status}</span>
              </div>
              <TokenStream status={status} />
            </div>
          </div>
          <button
            className="chr-button"
            style={{ height: 32, padding: "0 12px", fontSize: "0.75rem" }}
            onClick={() => refreshArtifacts()}
            type="button"
          >
            refresh
          </button>
        </header>

        {error ? (
          <div
            className="rounded-xl border px-4 py-3 text-sm"
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

        {isWaitingForWorker ? (
          <div className="flex h-64 flex-col items-center justify-center rounded-xl border border-dashed" style={{ borderColor: "rgba(var(--chr-border), 0.8)" }}>
            <div className="animate-pulse text-sm text-gray-500 font-mono">
              Waiting for worker to pick up job...
            </div>
          </div>
        ) : (
          <>
            {/* Pipeline Visualization */}
            <div className="chr-card p-6">
              <div className="flex items-center justify-between gap-4">
                {passStates.slice(0, 3).map((p, idx) => {
                  const isActive = p.phase === "generating" || p.phase === "scoring";
                  const isDone = p.phase === "done";
                  const hasError = p.phase === "error";
                  const isIdle = p.phase === "idle" || p.phase === "planned";
                  
                  let stageName = "Draft";
                  let stageDesc = "Initial response";
                  if (p.passIndex === 2) {
                    stageName = "Refine";
                    stageDesc = "Improve & clarify";
                  } else if (p.passIndex === 3) {
                    stageName = "Validate";
                    stageDesc = "Check & finalize";
                  }
                  
                  let borderColor = "rgba(var(--chr-border), 0.6)";
                  let bgColor = "rgba(var(--chr-paper-wash), 0.3)";
                  let iconColor = "rgb(var(--chr-muted))";
                  let icon = "○";
                  
                  if (isDone) {
                    borderColor = "rgba(34, 197, 94, 0.5)"; // green
                    bgColor = "rgba(34, 197, 94, 0.08)";
                    iconColor = "#22c55e";
                    icon = "✓";
                  } else if (hasError) {
                    borderColor = "rgba(239, 68, 68, 0.5)"; // red
                    bgColor = "rgba(239, 68, 68, 0.08)";
                    iconColor = "#ef4444";
                    icon = "✕";
                  } else if (isActive) {
                    borderColor = "rgba(59, 130, 246, 0.6)"; // blue
                    bgColor = "rgba(59, 130, 246, 0.08)";
                    iconColor = "#3b82f6";
                    icon = "⋯";
                  }
                  
                  return (
                    <React.Fragment key={p.passIndex}>
                      <div 
                        className="flex-1 relative"
                        style={{ minWidth: 0 }}
                      >
                        <div
                          className={`rounded-lg border-2 p-4 transition-all duration-300 ${
                            isActive ? "animate-pulse" : ""
                          }`}
                          style={{
                            borderColor,
                            backgroundColor: bgColor,
                          }}
                        >
                          <div className="flex items-start gap-3">
                            <div 
                              className="text-2xl font-bold flex-shrink-0"
                              style={{ color: iconColor }}
                            >
                              {icon}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                <div 
                                  className="font-semibold text-sm"
                                  style={{ color: "rgb(var(--chr-ink))" }}
                                >
                                  {stageName}
                                </div>
                                <div 
                                  className="text-[10px] px-1.5 py-0.5 rounded"
                                  style={{
                                    fontFamily: "var(--chr-font-mono)",
                                    backgroundColor: "rgba(var(--chr-border), 0.3)",
                                    color: "rgb(var(--chr-muted))",
                                  }}
                                >
                                  {p.passIndex}
                                </div>
                              </div>
                              <div 
                                className="text-xs truncate"
                                style={{ color: "rgb(var(--chr-muted))" }}
                                title={stageDesc}
                              >
                                {stageDesc}
                              </div>
                              {p.modelId && (
                                <div 
                                  className="text-[10px] mt-1 truncate"
                                  style={{ 
                                    fontFamily: "var(--chr-font-mono)",
                                    color: "rgb(var(--chr-muted))",
                                    opacity: 0.7,
                                  }}
                                  title={p.modelId}
                                >
                                  {p.modelId}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                      
                      {/* Arrow between stages */}
                      {idx < 2 && (
                        <div 
                          className="flex items-center justify-center flex-shrink-0"
                          style={{ width: "32px" }}
                        >
                          <div 
                            className="text-xl"
                            style={{ color: "rgb(var(--chr-muted))", opacity: 0.5 }}
                          >
                            →
                          </div>
                        </div>
                      )}
                    </React.Fragment>
                  );
                })}
              </div>
            </div>
            
            {/* Tabs */}
            <div className="flex items-center gap-2 border-b pb-1" style={{ borderColor: "rgba(var(--chr-border), 0.6)" }}>
              {passStates.map((p) => {
                const hasArtifact = artifacts.some((a) => a.pass_index === p.passIndex);
                const isActive = activeTab === p.passIndex;
                
                // Labels
                let label = `Pass ${p.passIndex}`;
                if (p.passIndex === 1) label = "1. Draft";
                if (p.passIndex === 2) label = "2. Refine";
                if (p.passIndex === 3) label = "3. Validate";
                if (p.passIndex === 4) label = "4. Voice";

                // Status indicator
                let statusIndicator = null;
                if (p.phase === "error") {
                  statusIndicator = <span className="ml-2 text-red-500" title="Error">✕</span>;
                } else if (p.phase === "done") {
                  statusIndicator = <span className="ml-2 text-green-500" title="Completed">✓</span>;
                } else if (p.phase === "generating" || p.phase === "scoring") {
                  statusIndicator = <span className="ml-2 animate-pulse" title="Processing">⋯</span>;
                }

                return (
                  <button
                    key={p.passIndex}
                    onClick={() => setActiveTab(p.passIndex)}
                    disabled={!hasArtifact && p.phase !== "generating" && p.phase !== "scoring" && p.phase !== "error"}
                    className={`
                      relative px-4 py-2 text-sm font-medium transition-colors
                      ${isActive ? "text-[rgb(var(--chr-ink))]" : "text-[rgb(var(--chr-muted))] hover:text-[rgb(var(--chr-ink))]"}
                      ${!hasArtifact && p.phase !== "generating" && p.phase !== "error" ? "opacity-50 cursor-not-allowed" : ""}
                      ${p.phase === "error" ? "text-red-500" : ""}
                    `}
                  >
                    {label}
                    {statusIndicator}
                    {isActive && (
                      <div
                        className="absolute bottom-[-5px] left-0 h-[2px] w-full bg-[rgb(var(--chr-ink))]"
                      />
                    )}
                  </button>
                );
              })}
            </div>

            {/* Main Content Area: Split View */}
            <div className="flex flex-col gap-8 md:flex-row">
              {/* Left Sidebar: Stats & Metadata */}
              <aside className="flex w-full flex-col gap-6 md:w-64 md:shrink-0">
                {currentArtifact ? (
                  <>
                    {/* Model Info */}
                    <div className="chr-card p-4">
                      <h3 className="chr-subtle mb-3">Model Info</h3>
                      <div className="flex flex-col gap-2 text-xs" style={{ color: "rgb(var(--chr-ink))" }}>
                        <div className="flex justify-between">
                          <span style={{ color: "rgb(var(--chr-muted))" }}>Model</span>
                          <span className="font-mono text-right">{currentArtifact.model_id}</span>
                        </div>
                        <div className="flex justify-between">
                          <span style={{ color: "rgb(var(--chr-muted))" }}>Role</span>
                          <span className="font-mono text-right">{currentArtifact.role}</span>
                        </div>
                        <div className="flex justify-between">
                          <span style={{ color: "rgb(var(--chr-muted))" }}>Latency</span>
                          <span className="font-mono text-right">
                            {currentArtifact.usage?.latency_ms
                              ? `${Math.round(Number(currentArtifact.usage.latency_ms))}ms`
                              : "-"}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Scoring Metrics */}
                    {currentArtifact.score?.total != null && (
                      <div className="chr-card p-4">
                        <h3 className="chr-subtle mb-3">Score & Metrics</h3>
                        
                        <div className="mb-4">
                          <div className="text-xs mb-1" style={{ color: "rgb(var(--chr-muted))" }}>Total Score</div>
                          <div className="flex items-center gap-3">
                            <div className="text-2xl font-bold font-mono">
                              {Math.round(currentArtifact.score.total * 100)}
                            </div>
                            {(() => {
                              const score = Math.round(currentArtifact.score.total * 100);
                              let qualityLabel = "Poor";
                              let qualityColor = "#ef4444"; // red
                              
                              if (score >= 80) {
                                qualityLabel = "Excellent";
                                qualityColor = "#22c55e"; // green
                              } else if (score >= 60) {
                                qualityLabel = "Good";
                                qualityColor = "#eab308"; // yellow
                              }
                              
                              return (
                                <div
                                  className="text-xs px-2 py-1 rounded-full font-medium"
                                  style={{
                                    backgroundColor: `${qualityColor}20`,
                                    color: qualityColor,
                                    border: `1px solid ${qualityColor}40`,
                                  }}
                                >
                                  {qualityLabel}
                                </div>
                              );
                            })()}
                          </div>
                        </div>

                        <div className="flex flex-col gap-3">
                          {currentArtifact.score.dimensions &&
                            Object.entries(currentArtifact.score.dimensions).map(([key, val]) => {
                              if (val === null || val === undefined) return null;
                              
                              // Color-code based on score value
                              const pct = Math.round(val * 100);
                              let barColor = "#ef4444"; // red for <60
                              if (pct >= 80) barColor = "#22c55e"; // green for >=80
                              else if (pct >= 60) barColor = "#eab308"; // yellow for 60-79
                              
                              return (
                                <div key={key}>
                                  <div className="flex justify-between text-[10px] uppercase tracking-wider mb-1" style={{ color: "rgb(var(--chr-muted))" }}>
                                    <span>{key.replace("_", " ")}</span>
                                    <span style={{ color: barColor, fontWeight: 600 }}>{pct}</span>
                                  </div>
                                  <div
                                    className="h-1.5 w-full overflow-hidden rounded-full"
                                    style={{ background: "rgba(var(--chr-border), 0.4)" }}
                                  >
                                    <div
                                      className="h-full rounded-full transition-all duration-700"
                                      style={{
                                        width: `${clamp01(val) * 100}%`,
                                        background: barColor,
                                        opacity: 0.85,
                                      }}
                                    />
                                  </div>
                                </div>
                              );
                            })}
                        </div>

                        {currentArtifact.score.meta?.words ? (
                          <div className="mt-4 pt-4 border-t" style={{ borderColor: "rgba(var(--chr-border), 0.5)" }}>
                            <div className="flex justify-between text-xs">
                              <span style={{ color: "rgb(var(--chr-muted))" }}>Word Count</span>
                              <span className="font-mono">{String(currentArtifact.score.meta.words)}</span>
                            </div>
                          </div>
                        ) : null}
                      </div>
                    )}
                  </>
                ) : (
                  <div className="chr-card p-4 text-xs text-[rgb(var(--chr-muted))]">
                    Select a completed pass to see metrics.
                  </div>
                )}
              </aside>

              {/* Right Content: Artifact Text */}
              <div className="min-w-0 flex-1">
                {/* Error State */}
                {currentPassState?.phase === "error" && currentPassState.error ? (
                  <div className="chr-card min-h-[300px] p-6 md:p-10">
                    <div className="flex flex-col gap-4">
                      <div className="flex items-start gap-3">
                        <div className="text-2xl">⚠️</div>
                        <div className="flex-1">
                          <h3 className="text-lg font-semibold text-red-600 mb-2">Stage {activeTab} Failed</h3>
                          <div 
                            className="rounded-lg border px-4 py-3 text-sm font-mono"
                            style={{
                              borderColor: "rgba(180, 80, 50, 0.4)",
                              background: "rgba(180, 80, 50, 0.08)",
                              color: "rgb(var(--chr-ink))",
                            }}
                          >
                            {currentPassState.error}
                          </div>
                          
                          {/* Error suggestions */}
                          <div className="mt-4 text-sm" style={{ color: "rgb(var(--chr-muted))" }}>
                            <p className="font-semibold mb-2">Common solutions:</p>
                            <ul className="list-disc list-inside space-y-1">
                              {currentPassState.error.includes("API key") || currentPassState.error.includes("key") ? (
                                <li>Check that the API key is correctly configured in Settings</li>
                              ) : null}
                              {currentPassState.error.includes("timeout") ? (
                                <li>The request took too long - try again or use a different model</li>
                              ) : null}
                              {currentPassState.error.includes("metadata") || currentPassState.error.includes("Illegal") ? (
                                <li>API key may have hidden characters - try re-entering it</li>
                              ) : null}
                              <li>Try starting a new run with different model selections</li>
                            </ul>
                          </div>
                          
                          {/* Show previous stage impact */}
                          {activeTab === 2 && (
                            <div 
                              className="mt-4 rounded-lg border px-3 py-2 text-xs"
                              style={{
                                borderColor: "rgba(255, 200, 100, 0.4)",
                                background: "rgba(255, 200, 100, 0.08)",
                                color: "rgb(var(--chr-muted))",
                              }}
                            >
                              <strong>Note:</strong> Stage 3 (Validate) may be affected since it relies on the refined output from this stage.
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ) : currentArtifact ? (
                  <div className="chr-card min-h-[500px] p-6 md:p-10">
                    <div className="chr-markdown max-w-none text-base leading-relaxed">
                      <ReactMarkdown>{currentArtifact.output_text as string}</ReactMarkdown>
                    </div>
                  </div>
                ) : streamingText[activeTab] ? (
                  <div className="chr-card min-h-[500px] p-6 md:p-10">
                    {/* Streaming speed indicator */}
                    {(() => {
                      const meta = streamingMeta[activeTab];
                      if (!meta) return null;
                      
                      const elapsedSeconds = (Date.now() - meta.startTime) / 1000;
                      const chunkRate = elapsedSeconds > 0 ? (meta.chunkCount / elapsedSeconds).toFixed(1) : "0.0";
                      const wordCount = streamingText[activeTab].split(/\s+/).length;
                      const approxTokens = meta.approxTokens || Math.floor(wordCount * 1.3); // Rough estimate
                      const tokensPerSec = elapsedSeconds > 0 ? (approxTokens / elapsedSeconds).toFixed(1) : "0.0";
                      
                      return (
                        <div 
                          className="mb-4 flex items-center gap-4 text-xs pb-3 border-b"
                          style={{ 
                            borderColor: "rgba(var(--chr-border), 0.4)",
                            color: "rgb(var(--chr-muted))",
                            fontFamily: "var(--chr-font-mono)",
                          }}
                        >
                          <div className="flex items-center gap-2">
                            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                            <span>Streaming</span>
                          </div>
                          <div>•</div>
                          <div>{tokensPerSec} tokens/sec</div>
                          <div>•</div>
                          <div>~{approxTokens} tokens</div>
                          <div>•</div>
                          <div>{wordCount} words</div>
                        </div>
                      );
                    })()}
                    
                    <div className="chr-markdown max-w-none text-base leading-relaxed">
                      <ReactMarkdown>{streamingText[activeTab]}</ReactMarkdown>
                      <span className="chr-cursor">▋</span>
                    </div>
                  </div>
                ) : (
                  <div className="flex h-64 flex-col items-center justify-center text-sm text-gray-400 font-mono">
                    {currentPassState?.phase === "generating" ? (
                      <div className="flex flex-col items-center gap-3">
                        <div className="animate-spin h-5 w-5 border-2 border-gray-400 border-t-transparent rounded-full" />
                        <span>Generating pass {activeTab}...</span>
                        <NeuralTicker phase="generating" />
                      </div>
                    ) : currentPassState?.phase === "scoring" ? (
                      <div className="flex flex-col items-center gap-3">
                        <div className="animate-spin h-5 w-5 border-2 border-gray-400 border-t-transparent rounded-full" />
                        <span>Scoring pass {activeTab}...</span>
                      </div>
                    ) : (
                      <span>Waiting for previous steps...</span>
                    )}
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
