import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { generateProject, getOplEvaluation } from "../../services/UserService";

const STAGES = [
    { label: "Initializing agent", weight: 10 },
    { label: "Loading OPL specification", weight: 15 },
    { label: "Generating frontend & backend", weight: 45 },
    { label: "Running evaluation", weight: 20 },
    { label: "Packaging project", weight: 10 },
];

const Spinner = ({ label }) => (
    <div className="flex flex-col items-center gap-4">
        <div className="h-14 w-14 animate-spin rounded-full border-4 border-violet-200 border-t-violet-500" />
        {label && <p className="text-sm font-medium text-slate-600">{label}</p>}
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

const Generate = () => {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const startedRef = useRef(false);

    const oplId = searchParams.get("opl_id");
    const userId = searchParams.get("user_id");
    const filename = searchParams.get("filename") || "generated_project.zip";

    const [progress, setProgress] = useState(0);
    const [stageLabel, setStageLabel] = useState(STAGES[0].label);
    const [isGenerating, setIsGenerating] = useState(true);
    const [isComplete, setIsComplete] = useState(false);
    const [error, setError] = useState("");
    const [evaluation, setEvaluation] = useState(null);
    const [projectFileName, setProjectFileName] = useState(filename);

    useEffect(() => {
        if (startedRef.current) return;
        if (!oplId || !userId) {
            setError("Missing generation parameters. Please start from New Project.");
            setIsGenerating(false);
            return;
        }

        startedRef.current = true;

        let progressInterval;
        let stageIndex = 0;
        let currentProgress = 0;

        const advanceStages = () => {
            progressInterval = setInterval(() => {
                const stage = STAGES[stageIndex];
                if (!stage) return;

                setStageLabel(stage.label);
                const cap = STAGES.slice(0, stageIndex + 1).reduce((sum, s) => sum + s.weight, 0);
                currentProgress = Math.min(currentProgress + 1, cap - 2, 92);
                setProgress(currentProgress);

                if (currentProgress >= cap - 2 && stageIndex < STAGES.length - 1) {
                    stageIndex += 1;
                }
            }, 800);
        };

        const runGeneration = async () => {
            advanceStages();

            try {
                const response = await generateProject(oplId, userId, filename, (pct) => {
                    if (pct > 0) {
                        setProgress(Math.max(pct, currentProgress));
                    }
                });

                clearInterval(progressInterval);
                setProgress(95);
                setStageLabel("Downloading project...");

                const contentType = response.headers["content-type"] || "";
                if (contentType.includes("application/json")) {
                    const text = await response.data.text();
                    const payload = JSON.parse(text);
                    throw new Error(payload.message || "Generation failed");
                }

                downloadBlob(response.data, filename);
                setProjectFileName(filename);
                setProgress(98);
                setStageLabel("Fetching evaluation results...");

                try {
                    const evalResult = await getOplEvaluation(oplId);
                    if (evalResult.success) {
                        setEvaluation(evalResult.data);
                    }
                } catch {
                    setEvaluation(null);
                }

                setProgress(100);
                setIsComplete(true);
            } catch (err) {
                clearInterval(progressInterval);
                let message = err.message || "Generation failed";
                if (err.response?.data instanceof Blob) {
                    try {
                        const text = await err.response.data.text();
                        const payload = JSON.parse(text);
                        message = payload.message || message;
                    } catch {
                        /* keep default message */
                    }
                } else if (err.response?.data?.message) {
                    message = err.response.data.message;
                }
                setError(message);
            } finally {
                setIsGenerating(false);
            }
        };

        runGeneration();

        return () => clearInterval(progressInterval);
    }, [oplId, userId, filename]);

    const renderScore = (label, value) => (
        <div className="rounded-xl border border-violet-100 bg-white/80 px-4 py-3">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</p>
            <p className="mt-1 text-2xl font-bold text-violet-600">
                {value != null ? `${value}%` : "—"}
            </p>
        </div>
    );

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
                            <div className="rounded-2xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-700">
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
                            </div>

                            {evaluation && (
                                <div>
                                    <h3 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">
                                        Evaluation Results
                                    </h3>
                                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                                        {renderScore("Overall", evaluation.overall_score)}
                                        {renderScore("Graph Coverage", evaluation.graph_coverage_score)}
                                        {renderScore("Syntax", evaluation.syntax_score)}
                                        {renderScore("Executability", evaluation.exec_score)}
                                    </div>
                                </div>
                            )}

                            <div className="rounded-2xl border border-violet-100 bg-violet-50/40 p-6">
                                <h3 className="mb-4 text-sm font-semibold uppercase tracking-wide text-violet-600">
                                    Next Steps
                                </h3>
                                <ol className="space-y-3 text-sm text-slate-600">
                                    <li className="flex gap-3">
                                        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-violet-200 text-xs font-bold text-violet-700">1</span>
                                        Extract the downloaded zip file to a folder on your machine.
                                    </li>
                                    <li className="flex gap-3">
                                        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-violet-200 text-xs font-bold text-violet-700">2</span>
                                        Open a terminal in the <code className="rounded bg-white px-1.5 py-0.5 text-xs">backend/</code> folder, run <code className="rounded bg-white px-1.5 py-0.5 text-xs">pip install -r requirements.txt</code>, then <code className="rounded bg-white px-1.5 py-0.5 text-xs">python app.py</code>.
                                    </li>
                                    <li className="flex gap-3">
                                        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-violet-200 text-xs font-bold text-violet-700">3</span>
                                        In a second terminal, go to <code className="rounded bg-white px-1.5 py-0.5 text-xs">frontend/</code>, run <code className="rounded bg-white px-1.5 py-0.5 text-xs">npm install</code>, then <code className="rounded bg-white px-1.5 py-0.5 text-xs">npm run dev</code>.
                                    </li>
                                    <li className="flex gap-3">
                                        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-violet-200 text-xs font-bold text-violet-700">4</span>
                                        Open the app in your browser (usually http://localhost:5173) and verify it matches your OPL specification.
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
