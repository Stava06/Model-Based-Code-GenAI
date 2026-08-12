import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { streamGenerateProject, downloadGeneratedProject, getOplEvaluation, launchProjectInVscode } from "../../services/UserService";
import OpenInVscodeButton from "../OpenInVscodeButton";
import { isLocalhost } from "../../utils/isLocalhost";

const DEFAULT_STEP_WEIGHTS = {
    init: 5,
    building_logic_map: 20,
    generating: 35,
    evaluating: 25,
    resolving_problem: 0,
    finishing: 10,
    packaging: 30,
    retry: 0,
};

const Spinner = ({ label }) => (
    <div className="flex flex-col items-center gap-4">
        <div className="h-14 w-14 animate-spin rounded-full border-4 border-violet-200 border-t-violet-500" />
        {label && <p className="text-sm font-medium text-slate-600">{label}</p>}
    </div>
);

const ActivityLog = ({ activities, scrollRef }) => (
    <div
        ref={scrollRef}
        className="max-h-64 space-y-2 overflow-y-auto pr-1"
    >
        {activities.length === 0 ? (
            <p className="text-sm text-slate-400">Waiting for agent activity...</p>
        ) : (
            activities.map((activity) => {
                const isIssue = activity.stepId === "resolving_problem";
                const rowClass = isIssue
                    ? "flex items-center gap-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-2.5 text-sm"
                    : "flex items-center gap-3 rounded-xl border border-violet-100 bg-white/80 px-4 py-2.5 text-sm";

                const icon = isIssue ? (
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-rose-200 text-xs font-bold text-rose-700">
                        ✕
                    </span>
                ) : activity.status === "done" ? (
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-xs text-emerald-600">
                        ✓
                    </span>
                ) : (
                    <span className="h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-violet-200 border-t-violet-500" />
                );

                return (
                    <div key={activity.id} className={rowClass}>
                        {icon}
                        <span
                            className={
                                isIssue
                                    ? "font-medium text-rose-700"
                                    : activity.status === "active"
                                      ? "font-medium text-violet-600"
                                      : "text-slate-600"
                            }
                        >
                            {activity.label}
                        </span>
                    </div>
                );
            })
        )}
    </div>
);

const downloadBlob = (blob, filename) => {
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
};

const formatError = (message) => {
    const text = message || "Generation failed";
    return text.startsWith("Error found:") ? text : `Error found: ${text}`;
};

const SCORE_METRICS = [
    { key: "overall_score", label: "Overall", color: "#8b5cf6", trackColor: "#ede9fe" },
    { key: "graph_coverage_score", label: "Graph Coverage", color: "#ec4899", trackColor: "#fce7f3" },
    { key: "syntax_score", label: "Syntax", color: "#10b981", trackColor: "#d1fae5" },
    { key: "exec_score", label: "Executability", color: "#3b82f6", trackColor: "#dbeafe" },
];

const ScoreCircle = ({ label, value, color, trackColor }) => {
    const size = 88;
    const strokeWidth = 7;
    const radius = (size - strokeWidth) / 2;
    const circumference = 2 * Math.PI * radius;
    const pct = value != null ? Math.min(100, Math.max(0, Number(value))) : null;
    const offset = pct != null ? circumference - (pct / 100) * circumference : circumference;

    return (
        <div className="flex flex-col items-center gap-2 bg-transparent">
            <div className="relative" style={{ width: size, height: size }}>
                <svg width={size} height={size} className="-rotate-90">
                    <circle
                        cx={size / 2}
                        cy={size / 2}
                        r={radius}
                        fill="transparent"
                        stroke={trackColor}
                        strokeWidth={strokeWidth}
                    />
                    {pct != null && (
                        <circle
                            cx={size / 2}
                            cy={size / 2}
                            r={radius}
                            fill="transparent"
                            stroke={color}
                            strokeWidth={strokeWidth}
                            strokeDasharray={circumference}
                            strokeDashoffset={offset}
                            strokeLinecap="round"
                        />
                    )}
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-base font-bold" style={{ color: pct != null ? color : "#94a3b8" }}>
                        {pct != null ? `${Math.round(pct)}%` : "—"}
                    </span>
                </div>
            </div>
            <p className="text-center text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
        </div>
    );
};

const applyActivityProgress = (activities, seenStepIdsRef, activeHalfStepsRef, progressRef, stepWeights) => {
    let changed = false;

    for (const activity of activities) {
        const stepId = activity.stepId;
        if (seenStepIdsRef.current.has(stepId)) continue;

        const weight = stepWeights[stepId] ?? 8;
        const hadHalfCredit = activeHalfStepsRef.current.has(stepId);

        if (activity.status === "done") {
            progressRef.current += hadHalfCredit ? weight * 0.5 : weight;
            seenStepIdsRef.current.add(stepId);
            activeHalfStepsRef.current.delete(stepId);
            changed = true;
        } else if (activity.status === "active" && !hadHalfCredit) {
            progressRef.current += weight * 0.5;
            activeHalfStepsRef.current.add(stepId);
            changed = true;
        }
    }

    return changed;
};

const Generate = () => {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const seenStepIdsRef = useRef(new Set());
    const activeHalfStepsRef = useRef(new Set());
    const progressRef = useRef(0);
    const stepWeightsRef = useRef(DEFAULT_STEP_WEIGHTS);
    const logScrollRef = useRef(null);
    const generationRunIdRef = useRef(0);

    const oplId = searchParams.get("opl_id");
    const userId = searchParams.get("user_id");
    const filename = searchParams.get("filename") || "generated_project.zip";

    const [progress, setProgress] = useState(0);
    const [stageLabel, setStageLabel] = useState("Initializing agent");
    const [activities, setActivities] = useState([]);
    const [isGenerating, setIsGenerating] = useState(true);
    const [isComplete, setIsComplete] = useState(false);
    const [error, setError] = useState("");
    const [evaluation, setEvaluation] = useState(null);
    const [evaluationWarning, setEvaluationWarning] = useState("");
    const [projectFileName, setProjectFileName] = useState(filename);
    const [pendingDownload, setPendingDownload] = useState(null);

    useEffect(() => {
        if (logScrollRef.current) {
            logScrollRef.current.scrollTop = logScrollRef.current.scrollHeight;
        }
    }, [activities]);

    useEffect(() => {
        if (!oplId || !userId) {
            setError(formatError("Missing generation parameters. Please start from New Project."));
            setIsGenerating(false);
            return;
        }

        const runId = ++generationRunIdRef.current;
        const isCurrentRun = () => generationRunIdRef.current === runId;
        let doneReceived = false;
        let errorReceived = false;
        const streamController = new AbortController();
        const downloadController = new AbortController();

        seenStepIdsRef.current = new Set();
        activeHalfStepsRef.current = new Set();
        progressRef.current = 0;
        stepWeightsRef.current = DEFAULT_STEP_WEIGHTS;

        setProgress(0);
        setStageLabel("Initializing agent");
        setActivities([]);
        setIsGenerating(true);
        setIsComplete(false);
        setError("");
        setEvaluation(null);
        setEvaluationWarning("");
        setPendingDownload(null);
        setProjectFileName(filename);

        const handleProgress = (payload) => {
            if (!isCurrentRun()) return;

            if (payload.step_weights) {
                stepWeightsRef.current = { ...DEFAULT_STEP_WEIGHTS, ...payload.step_weights };
            }

            if (Array.isArray(payload.activities)) {
                const changed = applyActivityProgress(
                    payload.activities,
                    seenStepIdsRef,
                    activeHalfStepsRef,
                    progressRef,
                    stepWeightsRef.current
                );
                if (changed) {
                    setProgress(Math.min(99, Math.round(progressRef.current)));
                }
                setActivities(payload.activities);
            }

            if (payload.message) {
                setStageLabel(payload.message);
            }
        };

        const finishGeneration = async (payload) => {
            try {
                if (!payload.download_id) {
                    throw new Error("Generation finished but no download id was provided");
                }

                if (Array.isArray(payload.activities) && isCurrentRun()) {
                    handleProgress(payload);
                }

                if (isCurrentRun()) {
                    progressRef.current = 100;
                    setProgress(100);
                    setStageLabel("Downloading project...");
                }

                // Let the browser release the SSE connection before downloading.
                await new Promise((resolve) => setTimeout(resolve, 0));

                const downloadName = payload.filename || filename;
                const { blob } = await downloadGeneratedProject(
                    payload.download_id,
                    userId,
                    downloadName,
                    { signal: downloadController.signal }
                );

                if (!isCurrentRun()) return;

                downloadBlob(blob, downloadName);
                setProjectFileName(downloadName);
                setPendingDownload({
                    downloadId: payload.download_id,
                    filename: downloadName,
                });

                setStageLabel("Fetching evaluation results...");
                setEvaluationWarning("");

                try {
                    const evalResult = await getOplEvaluation(oplId);
                    if (!isCurrentRun()) return;

                    if (evalResult.success && evalResult.data) {
                        setEvaluation(evalResult.data);
                    } else {
                        setEvaluation(null);
                        setEvaluationWarning(
                            evalResult.message || "Evaluation results are not available yet."
                        );
                    }
                } catch (evalErr) {
                    if (!isCurrentRun()) return;
                    setEvaluation(null);
                    setEvaluationWarning(
                        evalErr.response?.data?.message
                            || evalErr.message
                            || "Could not load evaluation results."
                    );
                }

                setIsComplete(true);
            } catch (err) {
                if (!isCurrentRun()) return;
                if (streamController.signal.aborted || downloadController.signal.aborted) return;

                let message = err.message || "Failed to download generated project";
                if (err.response?.data instanceof Blob) {
                    try {
                        const text = await err.response.data.text();
                        const errorPayload = JSON.parse(text);
                        message = errorPayload.message || message;
                    } catch {
                        /* keep default message */
                    }
                } else if (err.response?.data?.message) {
                    message = err.response.data.message;
                }
                setError(formatError(message));
            } finally {
                if (isCurrentRun()) {
                    setIsGenerating(false);
                }
            }
        };

        const runGeneration = async () => {
            try {
                await streamGenerateProject(oplId, userId, filename, {
                    signal: streamController.signal,
                    onProgress: handleProgress,
                    onError: (payload) => {
                        if (!isCurrentRun()) return;
                        errorReceived = true;
                        setError(formatError(payload.message));
                        setIsGenerating(false);
                    },
                    onDone: async (payload) => {
                        doneReceived = true;
                        await finishGeneration(payload);
                    },
                });

                if (isCurrentRun() && !doneReceived && !errorReceived) {
                    setError(formatError("Generation stream closed before the project was ready."));
                    setIsGenerating(false);
                }
            } catch (err) {
                if (!isCurrentRun() || streamController.signal.aborted) return;
                setError(formatError(err.message));
                setIsGenerating(false);
            }
        };

        runGeneration();

        return () => {
            generationRunIdRef.current += 1;
            streamController.abort();
            downloadController.abort();
        };
    }, [oplId, userId, filename]);

    const retryDownload = async () => {
        if (!pendingDownload) return;

        try {
            const { blob } = await downloadGeneratedProject(
                pendingDownload.downloadId,
                userId,
                pendingDownload.filename
            );
            downloadBlob(blob, pendingDownload.filename);
        } catch (err) {
            let message = err.message || "Download failed";
            if (err.response?.data instanceof Blob) {
                try {
                    const text = await err.response.data.text();
                    const errorPayload = JSON.parse(text);
                    message = errorPayload.message || message;
                } catch {
                    /* keep default message */
                }
            } else if (err.response?.data?.message) {
                message = err.response.data.message;
            }
            setEvaluationWarning(message);
        }
    };

    return (
        <div className="relative min-h-screen w-full overflow-hidden">
            <div className="absolute inset-0 -z-10 bg-gradient-to-br from-[#faf7ff] via-[#fcfbff] to-[#f3f6ff]" />
            <div className="absolute top-[-10rem] right-[-5rem] h-[28rem] w-[28rem] rounded-full bg-pink-200/20 blur-3xl" />
            <div className="absolute bottom-[-8rem] left-[-6rem] h-[24rem] w-[24rem] rounded-full bg-violet-200/20 blur-3xl" />

            <div className="flex min-h-screen flex-col px-10 py-10 lg:px-16">
                <div className="mb-10">
                    <h1 className="text-4xl font-bold tracking-tight text-slate-800">Generate Project</h1>
                    <p className="mt-3 text-base text-slate-500">
                        Building your fullstack application from the OPL specification.
                    </p>
                </div>

                <div className="mx-auto w-full max-w-3xl rounded-[2.5rem] border border-violet-100 bg-white/70 p-10 shadow-2xl shadow-violet-100/30 backdrop-blur-xl">
                    {error && (
                        <div className="space-y-6 text-center">
                            <div className="whitespace-pre-wrap rounded-2xl border border-rose-200 bg-rose-50 px-5 py-4 text-left text-sm text-rose-700">
                                {error}
                            </div>
                            <button
                                onClick={() => navigate("/newproject")}
                                className="rounded-2xl bg-gradient-to-r from-violet-400 to-fuchsia-400 px-8 py-3 text-sm font-semibold text-white shadow-lg"
                            >
                                Back to New Project
                            </button>
                        </div>
                    )}

                    {isGenerating && !error && (
                        <div className="space-y-8">
                            <Spinner label={stageLabel} />

                            <div>
                                <div className="mb-2 flex justify-between text-sm text-slate-500">
                                    <span>{stageLabel}</span>
                                    <span>{progress}%</span>
                                </div>
                                <div className="h-3 overflow-hidden rounded-full bg-violet-100">
                                    <div
                                        className="h-full rounded-full bg-gradient-to-r from-violet-400 to-fuchsia-400 transition-all duration-500"
                                        style={{ width: `${progress}%` }}
                                    />
                                </div>
                            </div>

                            <div className="rounded-2xl border border-violet-100 bg-violet-50/40 p-6">
                                <h3 className="mb-4 text-sm font-semibold uppercase tracking-wide text-violet-600">
                                    Agent Activity
                                </h3>
                                <ActivityLog activities={activities} scrollRef={logScrollRef} />
                            </div>

                            <p className="text-center text-xs text-slate-400">
                                This may take several minutes. Please keep this tab open.
                            </p>
                        </div>
                    )}

                    {isComplete && !error && (
                        <div className="space-y-8">
                            <div className="text-center">
                                <div className="mx-auto mb-4 flex h-20 w-20 items-center justify-center rounded-full bg-emerald-100 text-4xl">
                                    🎉
                                </div>
                                <h2 className="text-2xl font-bold text-slate-800">
                                    Congratulations!
                                </h2>
                                <p className="mt-2 text-slate-500">
                                    Your project <span className="font-semibold text-violet-600">{projectFileName}</span> has been generated and downloaded.
                                </p>
                                {pendingDownload && (
                                    <div className="mt-4 flex flex-col items-center gap-3">
                                        <OpenInVscodeButton
                                            className="rounded-2xl bg-gradient-to-r from-violet-400 to-fuchsia-400 px-8 py-3 text-sm font-semibold text-white shadow-lg shadow-violet-200/40 transition hover:scale-[1.01] disabled:cursor-not-allowed disabled:opacity-60"
                                            launch={() =>
                                                launchProjectInVscode(pendingDownload.downloadId, userId)
                                            }
                                            disabled={!userId}
                                        />
                                        <button
                                            type="button"
                                            onClick={retryDownload}
                                            className="text-sm font-medium text-violet-600 underline-offset-2 hover:underline"
                                        >
                                            Download again
                                        </button>
                                    </div>
                                )}
                            </div>

                            {evaluationWarning && !evaluation && (
                                <div className="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-800">
                                    {evaluationWarning}
                                </div>
                            )}

                            {evaluation && (
                                <div>
                                    <h3 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">
                                        Evaluation Results
                                    </h3>
                                    <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
                                        {SCORE_METRICS.map(({ key, label, color, trackColor }) => (
                                            <ScoreCircle
                                                key={key}
                                                label={label}
                                                value={evaluation[key]}
                                                color={color}
                                                trackColor={trackColor}
                                            />
                                        ))}
                                    </div>
                                </div>
                            )}

                            <div className="rounded-2xl border border-violet-100 bg-violet-50/40 p-6">
                                <h3 className="mb-4 text-sm font-semibold uppercase tracking-wide text-violet-600">
                                    Next Steps
                                </h3>
                                <ol className="space-y-3 text-sm text-slate-600">
                                    {isLocalhost() ? (
                                        <li className="flex gap-3">
                                            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-violet-200 text-xs font-bold text-violet-700">1</span>
                                            Click <span className="font-semibold text-violet-600">Open in VS Code</span> to extract the project, open it in VS Code, and start the frontend and backend dev servers.
                                        </li>
                                    ) : (
                                        <li className="flex gap-3">
                                            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-violet-200 text-xs font-bold text-violet-700">1</span>
                                            Extract the downloaded zip and open the project folder in your editor.
                                        </li>
                                    )}
                                    <li className="flex gap-3">
                                        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-violet-200 text-xs font-bold text-violet-700">2</span>
                                        If needed, run <code className="rounded bg-white px-1.5 py-0.5 text-xs">npm install</code> in <code className="rounded bg-white px-1.5 py-0.5 text-xs">frontend/</code> and <code className="rounded bg-white px-1.5 py-0.5 text-xs">pip install -r requirements.txt</code> in <code className="rounded bg-white px-1.5 py-0.5 text-xs">backend/</code>{isLocalhost() ? " before the dev servers start" : ""}.
                                    </li>
                                    <li className="flex gap-3">
                                        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-violet-200 text-xs font-bold text-violet-700">3</span>
                                        {isLocalhost()
                                            ? "Open the app in your browser (usually http://localhost:5173) and verify it matches your OPL specification."
                                            : "Start the frontend and backend dev servers, then open the app in your browser and verify it matches your OPL specification."}
                                    </li>
                                </ol>
                            </div>

                            <div className="flex justify-center gap-3">
                                <button
                                    onClick={() => navigate("/newproject")}
                                    className="rounded-2xl border border-violet-200 bg-white px-8 py-3 text-sm font-semibold text-violet-600 transition hover:bg-violet-50"
                                >
                                    New Project
                                </button>
                                <button
                                    onClick={() => navigate("/profile")}
                                    className="rounded-2xl bg-gradient-to-r from-violet-400 to-fuchsia-400 px-8 py-3 text-sm font-semibold text-white shadow-lg"
                                >
                                    View Profile
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default Generate;
