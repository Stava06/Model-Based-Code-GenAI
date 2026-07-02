import React, { useCallback, useEffect, useRef, useState } from "react";
import { getMyProjects, getProjectOpl, downloadStoredProject, launchStoredProjectInVscode } from "../../services/UserService";
import OpenInVscodeButton from "../OpenInVscodeButton";

const PAGE_SIZE = 15;

const Spinner = ({ label, small = false }) => (
    <div className={`flex flex-col items-center gap-4 ${small ? "py-4" : "py-8"}`}>
        <div
            className={`animate-spin rounded-full border-4 border-violet-200 border-t-violet-500 ${
                small ? "h-8 w-8" : "h-12 w-12"
            }`}
        />
        {label && <p className="text-sm font-medium text-slate-600">{label}</p>}
    </div>
);

const SCORE_METRICS = [
    { key: "overall_score", label: "Overall" },
    { key: "graph_coverage_score", label: "Graph Coverage" },
    { key: "syntax_score", label: "Syntax" },
    { key: "exec_score", label: "Executability" },
];

const formatDate = (iso) => {
    if (!iso) return "Unknown date";
    try {
        return new Date(iso).toLocaleString();
    } catch {
        return iso;
    }
};

const toZipFilename = (fileName) => {
    if (!fileName) return "generated_project.zip";
    if (fileName.toLowerCase().endsWith(".zip")) return fileName;
    const base = fileName.includes(".") ? fileName.replace(/\.[^.]+$/, "") : fileName;
    return `${base}.zip`;
};

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

const MyProjects = () => {
    const [projects, setProjects] = useState([]);
    const [total, setTotal] = useState(0);
    const [isLoading, setIsLoading] = useState(true);
    const [isLoadingMore, setIsLoadingMore] = useState(false);
    const [error, setError] = useState("");
    const [expandedId, setExpandedId] = useState(null);
    const [selectedId, setSelectedId] = useState(null);
    const [oplContent, setOplContent] = useState("");
    const [isOplLoading, setIsOplLoading] = useState(false);
    const [oplError, setOplError] = useState("");
    const [downloadingId, setDownloadingId] = useState(null);
    const [downloadError, setDownloadError] = useState("");

    const userIdRef = useRef(null);
    const oplCacheRef = useRef({});
    const loadMoreRef = useRef(null);
    const skipRef = useRef(0);
    const totalRef = useRef(0);
    const loadingMoreRef = useRef(false);

    const hasMore = projects.length < total;

    const loadOplContent = useCallback(async (projectId) => {
        if (!userIdRef.current) return;

        if (oplCacheRef.current[projectId] !== undefined) {
            setOplContent(oplCacheRef.current[projectId]);
            setOplError("");
            return;
        }

        setIsOplLoading(true);
        setOplError("");
        setOplContent("");

        const result = await getProjectOpl(projectId, userIdRef.current);
        if (result.success) {
            const content = result.data || "";
            oplCacheRef.current[projectId] = content;
            setOplContent(content);
        } else {
            setOplError(result.message || "Failed to load OPL content");
        }

        setIsOplLoading(false);
    }, []);

    const fetchProjects = useCallback(async ({ append = false } = {}) => {
        if (!userIdRef.current) return;

        if (append) {
            if (loadingMoreRef.current || skipRef.current >= totalRef.current) return;
            loadingMoreRef.current = true;
            setIsLoadingMore(true);
        } else {
            setIsLoading(true);
            setError("");
            skipRef.current = 0;
        }

        const result = await getMyProjects(userIdRef.current, {
            skip: skipRef.current,
            limit: PAGE_SIZE,
        });

        if (!result.success) {
            if (!append) {
                setError(result.message || "Failed to load projects");
                setProjects([]);
                setTotal(0);
                totalRef.current = 0;
            }
        } else {
            const list = result.data || [];
            const nextTotal = result.total ?? list.length;
            totalRef.current = nextTotal;
            setTotal(nextTotal);
            setProjects((prev) => (append ? [...prev, ...list] : list));
            skipRef.current += list.length;
        }

        if (append) {
            loadingMoreRef.current = false;
            setIsLoadingMore(false);
        } else {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        const storedUser = localStorage.getItem("user");
        if (!storedUser) {
            setError("Please log in to view your projects");
            setIsLoading(false);
            return;
        }

        let user;
        try {
            user = JSON.parse(storedUser);
        } catch {
            setError("Invalid session. Please log in again");
            setIsLoading(false);
            return;
        }

        if (!user.id) {
            setError("User ID not found. Please log in again");
            setIsLoading(false);
            return;
        }

        userIdRef.current = user.id;
        fetchProjects();
    }, [fetchProjects]);

    useEffect(() => {
        const sentinel = loadMoreRef.current;
        if (!sentinel || isLoading || projects.length >= totalRef.current) return;

        const observer = new IntersectionObserver(
            (entries) => {
                if (entries[0]?.isIntersecting) {
                    fetchProjects({ append: true });
                }
            },
            { root: sentinel.parentElement, threshold: 0.1 }
        );

        observer.observe(sentinel);
        return () => observer.disconnect();
    }, [fetchProjects, isLoading, projects.length, total]);

    const handleRowClick = (project) => {
        if (expandedId === project.id && selectedId === project.id) {
            setSelectedId(null);
            setExpandedId(null);
            setOplContent("");
            setOplError("");
            setDownloadError("");
            return;
        }

        setSelectedId(project.id);
        setExpandedId(project.id);
        setDownloadError("");
        loadOplContent(project.id);
    };

    const handleDownload = async (e, project) => {
        e.stopPropagation();

        if (!userIdRef.current) {
            setDownloadError("Please log in to download");
            return;
        }

        if (!project.has_generated_code) {
            setDownloadError("No generated project available for this entry");
            return;
        }

        setDownloadingId(project.id);
        setDownloadError("");

        try {
            const zipName = toZipFilename(project.file_name);
            const { blob } = await downloadStoredProject(project.id, userIdRef.current, zipName);
            downloadBlob(blob, zipName);
        } catch (err) {
            setDownloadError(err.message || "Failed to download project");
        } finally {
            setDownloadingId(null);
        }
    };

    return (
        <div className="relative h-full w-full overflow-hidden">
            <div className="absolute inset-0 -z-10 bg-gradient-to-br from-[#faf7ff] via-[#fcfbff] to-[#f3f6ff]" />
            <div className="absolute top-[-10rem] right-[-5rem] h-[28rem] w-[28rem] rounded-full bg-pink-200/20 blur-3xl" />
            <div className="absolute bottom-[-8rem] left-[-6rem] h-[24rem] w-[24rem] rounded-full bg-violet-200/20 blur-3xl" />

            <div className="flex h-full flex-col px-10 py-10 lg:px-16">
                <div className="mb-6 shrink-0">
                    <h1 className="text-4xl font-bold tracking-tight text-slate-800">
                        My Projects
                    </h1>
                    <p className="mt-3 text-base text-slate-500">
                        Browse your saved OPL specifications, download generated projects, or open them in VS Code.
                    </p>
                </div>

                <div className="flex min-h-0 flex-1 flex-col rounded-[2.5rem] border border-violet-100 bg-white/70 p-10 shadow-2xl shadow-violet-100/30 backdrop-blur-xl">
                    {error && (
                        <div className="mb-6 rounded-2xl border border-rose-200 bg-rose-50 px-5 py-3 text-sm text-rose-700">
                            {error}
                        </div>
                    )}

                    {downloadError && (
                        <div className="mb-6 rounded-2xl border border-rose-200 bg-rose-50 px-5 py-3 text-sm text-rose-700">
                            {downloadError}
                        </div>
                    )}

                    {isLoading ? (
                        <Spinner label="Loading your projects..." />
                    ) : projects.length === 0 && !error ? (
                        <div className="flex flex-col items-center justify-center py-16 text-center">
                            <p className="text-lg font-semibold text-slate-700">No projects yet</p>
                            <p className="mt-2 text-sm text-slate-500">
                                Create a new project to see it listed here.
                            </p>
                        </div>
                    ) : (
                        <div className="flex min-h-0 flex-1 flex-col">
                            <div className="grid min-h-0 flex-1 gap-8 lg:grid-cols-2">
                                <div className="flex min-h-0 flex-col">
                                    <p className="mb-3 shrink-0 text-xs font-medium uppercase tracking-wide text-violet-500">
                                        Projects ({total})
                                    </p>
                                    <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
                                        {projects.map((project) => {
                                            const isExpanded = expandedId === project.id;
                                            const isSelected = selectedId === project.id;
                                            const displayName = project.file_name || "Untitled project";

                                            return (
                                                <div
                                                    key={project.id}
                                                    className={`overflow-hidden rounded-2xl border transition-all ${
                                                        isSelected
                                                            ? "border-violet-200 bg-violet-50/50 shadow-sm"
                                                            : "border-violet-100 bg-white/80 hover:border-violet-200"
                                                    }`}
                                                >
                                                    <button
                                                        type="button"
                                                        onClick={() => handleRowClick(project)}
                                                        className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left"
                                                    >
                                                        <div className="min-w-0">
                                                            <p className="truncate font-semibold text-slate-700">
                                                                {displayName}
                                                            </p>
                                                            <p className="mt-1 text-xs text-slate-400">
                                                                {formatDate(project.created_at)}
                                                            </p>
                                                        </div>
                                                        <span
                                                            className={`shrink-0 text-violet-400 transition-transform ${
                                                                isExpanded ? "rotate-180" : ""
                                                            }`}
                                                        >
                                                            ▼
                                                        </span>
                                                    </button>

                                                    {isExpanded && (
                                                        <div className="border-t border-violet-100 px-5 py-4">
                                                            <p className="mb-3 text-xs font-medium uppercase tracking-wide text-slate-500">
                                                                File name
                                                            </p>
                                                            <p className="mb-4 rounded-xl border border-violet-100 bg-white/80 px-4 py-2.5 text-sm text-slate-700">
                                                                {displayName}
                                                            </p>

                                                            <p className="mb-3 text-xs font-medium uppercase tracking-wide text-slate-500">
                                                                Evaluation scores
                                                            </p>
                                                            <div className="mb-5 grid grid-cols-2 gap-3">
                                                                {SCORE_METRICS.map(({ key, label }) => {
                                                                    const value = project[key];
                                                                    return (
                                                                        <div
                                                                            key={key}
                                                                            className="rounded-xl border border-violet-100 bg-white/80 px-4 py-3"
                                                                        >
                                                                            <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
                                                                                {label}
                                                                            </p>
                                                                            <p className="mt-1 text-lg font-bold text-violet-600">
                                                                                {value != null
                                                                                    ? `${Math.round(Number(value))}%`
                                                                                    : "—"}
                                                                            </p>
                                                                        </div>
                                                                    );
                                                                })}
                                                            </div>

                                                            <div className="flex flex-wrap gap-3">
                                                                <button
                                                                    type="button"
                                                                    onClick={(e) => handleDownload(e, project)}
                                                                    disabled={
                                                                        !project.has_generated_code ||
                                                                        downloadingId === project.id
                                                                    }
                                                                    className="rounded-2xl bg-gradient-to-r from-violet-400 to-fuchsia-400 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-violet-200/40 transition hover:scale-[1.01] disabled:cursor-not-allowed disabled:opacity-60"
                                                                >
                                                                    {downloadingId === project.id
                                                                        ? "downloading..."
                                                                        : project.has_generated_code
                                                                          ? "Download Project"
                                                                          : "No project generated"}
                                                                </button>

                                                                <OpenInVscodeButton
                                                                    launch={() =>
                                                                        launchStoredProjectInVscode(
                                                                            project.id,
                                                                            userIdRef.current
                                                                        )
                                                                    }
                                                                    disabled={!project.has_generated_code}
                                                                />
                                                            </div>
                                                        </div>
                                                    )}
                                                </div>
                                            );
                                        })}

                                        {hasMore && (
                                            <div ref={loadMoreRef} className="py-2">
                                                {isLoadingMore && (
                                                    <Spinner small label="Loading more projects..." />
                                                )}
                                            </div>
                                        )}
                                    </div>
                                </div>

                                <div className="flex min-h-0 flex-col">
                                    <label className="mb-2 block shrink-0 text-xs font-medium uppercase tracking-wide text-slate-500">
                                        OPL content
                                    </label>
                                    <div className="min-h-0 flex-1 overflow-auto rounded-2xl border border-violet-100 bg-white/80">
                                        {isOplLoading ? (
                                            <Spinner small label="Loading OPL content..." />
                                        ) : oplError ? (
                                            <p className="p-4 text-sm text-rose-600">{oplError}</p>
                                        ) : oplContent ? (
                                            <pre className="min-w-max whitespace-pre p-4 text-sm text-slate-700">
                                                {oplContent}
                                            </pre>
                                        ) : (
                                            <p className="p-4 text-sm text-slate-400">
                                                Select a project to view its OPL content. Click again to
                                                close.
                                            </p>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default MyProjects;
