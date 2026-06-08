import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { saveOplFile } from "../../services/UserService";

const ACCEPTED_TYPES = [".txt", ".html"];
const ACCEPTED_MIME = "text/plain,text/html,.txt,.html";

const readFileAsString = (file) =>
    new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(new Error("Failed to read file"));
        reader.readAsText(file);
    });

const convertToOpl = async (file, rawContent) => {
    const ext = file.name.toLowerCase().slice(file.name.lastIndexOf("."));
    if (ext === ".html") {
        const doc = new DOMParser().parseFromString(rawContent, "text/html");
        return (doc.body?.textContent || rawContent).trim();
    }
    return rawContent.trim();
};

const Spinner = ({ label }) => (
    <div className="flex flex-col items-center gap-4 py-8">
        <div className="h-12 w-12 animate-spin rounded-full border-4 border-violet-200 border-t-violet-500" />
        {label && <p className="text-sm font-medium text-slate-600">{label}</p>}
    </div>
);

const NewProject = () => {
    const navigate = useNavigate();
    const [selectedFile, setSelectedFile] = useState(null);
    const [oplContent, setOplContent] = useState("");
    const [fileName, setFileName] = useState("");
    const [isConverting, setIsConverting] = useState(false);
    const [uploadFinished, setUploadFinished] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState("");

    const handleFileChange = (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const ext = file.name.toLowerCase().slice(file.name.lastIndexOf("."));
        if (!ACCEPTED_TYPES.includes(ext)) {
            setError("Please upload a .txt or .html file");
            return;
        }

        setError("");
        setSelectedFile(file);
        setFileName("");
        setUploadFinished(false);
    };

    const handleUpload = async () => {
        if (!selectedFile) {
            setError("Please choose a file first");
            return;
        }

        setError("");
        setIsConverting(true);
        setUploadFinished(false);

        try {
            const rawContent = await readFileAsString(selectedFile);
            const oplText = await convertToOpl(selectedFile, rawContent);

            setOplContent(oplText);
            setUploadFinished(true);
        } catch {
            setError("Failed to read or convert the file");
        } finally {
            setIsConverting(false);
        }
    };

    const handleGenerate = async () => {
        const storedUser = localStorage.getItem("user");
        if (!storedUser) {
            setError("Please log in to generate a project");
            return;
        }

        let user;
        try {
            user = JSON.parse(storedUser);
        } catch {
            setError("Invalid session. Please log in again");
            return;
        }

        if (!user.id) {
            setError("User ID not found. Please log in again");
            return;
        }

        const finalOpl = oplContent.trim();
        if (!finalOpl) {
            setError("OPL content is empty");
            return;
        }

        setError("");
        setIsSaving(true);

        const resolvedFileName = fileName.trim() || selectedFile?.name || "project.txt";

        try {
            const result = await saveOplFile(finalOpl, user.id, resolvedFileName);

            if (!result.success) {
                setError(result.message || "Failed to save OPL file");
                return;
            }

            const oplId = result.data;
            const baseName = resolvedFileName.replace(/\.(txt|html)$/i, "") + ".zip";

            navigate(
                `/generate?opl_id=${encodeURIComponent(oplId)}&user_id=${encodeURIComponent(user.id)}&filename=${encodeURIComponent(baseName)}`
            );
        } catch (err) {
            setError(err.response?.data?.message || err.message || "Failed to save OPL file");
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <div className="relative min-h-screen w-full overflow-hidden">
            <div className="absolute inset-0 -z-10 bg-gradient-to-br from-[#faf7ff] via-[#fcfbff] to-[#f3f6ff]" />
            <div className="absolute top-[-10rem] right-[-5rem] h-[28rem] w-[28rem] rounded-full bg-pink-200/20 blur-3xl" />
            <div className="absolute bottom-[-8rem] left-[-6rem] h-[24rem] w-[24rem] rounded-full bg-violet-200/20 blur-3xl" />

            <div className="flex min-h-screen flex-col px-10 py-10 lg:px-16">
                <div className="mb-10">
                    <h1 className="text-4xl font-bold tracking-tight text-slate-800">
                        New Project
                    </h1>
                    <p className="mt-3 text-base text-slate-500">
                        Upload your specification file and start generating your software project.
                    </p>
                </div>

                <div className="flex-1 rounded-[2.5rem] border border-violet-100 bg-white/70 p-10 shadow-2xl shadow-violet-100/30 backdrop-blur-xl">
                    {error && (
                        <div className="mb-6 rounded-2xl border border-rose-200 bg-rose-50 px-5 py-3 text-sm text-rose-700">
                            {error}
                        </div>
                    )}

                    {!uploadFinished && (
                        <>
                            <label
                                htmlFor="file-upload"
                                className="flex h-[22rem] w-full cursor-pointer flex-col items-center justify-center rounded-[2rem] border-2 border-dashed border-violet-200 bg-violet-50/40 transition-all hover:bg-violet-50"
                            >
                                <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-3xl bg-white shadow-lg shadow-violet-100">
                                    <span className="text-4xl font-light text-violet-500">+</span>
                                </div>
                                <h2 className="text-2xl font-semibold text-slate-700">Upload File</h2>
                                <p className="mt-3 text-sm text-slate-500">Drag and drop or click to browse</p>
                                <p className="mt-1 text-xs text-slate-400">Supported formats: .txt, .html</p>
                                <input
                                    id="file-upload"
                                    type="file"
                                    accept={ACCEPTED_MIME}
                                    onChange={handleFileChange}
                                    className="hidden"
                                />
                            </label>

                            {selectedFile && !isConverting && (
                                <div className="mt-6 flex items-center justify-between rounded-2xl border border-violet-100 bg-violet-50/60 px-5 py-4">
                                    <div>
                                        <p className="text-xs font-medium uppercase tracking-wide text-violet-500">
                                            Selected File
                                        </p>
                                        <p className="mt-1 font-semibold text-slate-700">{selectedFile.name}</p>
                                    </div>
                                    <button
                                        onClick={handleUpload}
                                        className="rounded-2xl bg-gradient-to-r from-violet-400 to-fuchsia-400 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-violet-200/40 transition hover:scale-[1.01]"
                                    >
                                        Read & Convert
                                    </button>
                                </div>
                            )}

                            {isConverting && <Spinner label="Converting file..." />}
                        </>
                    )}

                    {uploadFinished && (
                        <div className="space-y-6">
                            <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-5 py-4">
                                <p className="text-sm font-semibold text-emerald-700">Upload finished</p>
                                <p className="mt-1 text-xs text-emerald-600">
                                    Your file has been read and converted successfully.
                                </p>
                            </div>

                            <div>
                                <label
                                    htmlFor="file-name"
                                    className="mb-2 block text-xs font-medium uppercase tracking-wide text-violet-500"
                                >
                                    File name
                                </label>
                                <input
                                    id="file-name"
                                    type="text"
                                    value={fileName}
                                    onChange={(e) => setFileName(e.target.value)}
                                    placeholder={selectedFile?.name || "Enter file name"}
                                    className="w-full rounded-2xl border border-violet-100 bg-white/80 px-4 py-3 text-sm text-slate-700 outline-none placeholder:text-slate-400 focus:border-violet-300 focus:ring-4 focus:ring-violet-100"
                                />
                            </div>

                            <div>
                                <label className="mb-2 block text-xs font-medium uppercase tracking-wide text-slate-500">
                                    OPL content (edit before generating)
                                </label>
                                <textarea
                                    value={oplContent}
                                    onChange={(e) => setOplContent(e.target.value)}
                                    rows={12}
                                    className="w-full rounded-2xl border border-violet-100 bg-white/80 px-4 py-3 text-sm text-slate-700 outline-none focus:border-violet-300 focus:ring-4 focus:ring-violet-100"
                                />
                            </div>

                            <div className="flex justify-end">
                                <button
                                    onClick={handleGenerate}
                                    disabled={isSaving || !oplContent.trim()}
                                    className="rounded-2xl bg-gradient-to-r from-violet-400 to-fuchsia-400 px-8 py-3 text-sm font-semibold text-white shadow-lg shadow-violet-200/40 transition hover:scale-[1.01] disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                    {isSaving ? "Saving..." : "Generate"}
                                </button>
                            </div>

                            {isSaving && <Spinner label="Saving OPL file..." />}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default NewProject;
