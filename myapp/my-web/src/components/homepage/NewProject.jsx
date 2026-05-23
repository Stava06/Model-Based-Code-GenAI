import React, { useState } from "react";

const NewProject = () => {
    const [selectedFile, setSelectedFile] = useState(null);

    const handleFileChange = (e) => {
        const file = e.target.files[0];
        setSelectedFile(file);
    };

    const handleUpload = () => {
        if (!selectedFile) {
            alert("Please choose a file first");
            return;
        }

        console.log("Uploaded file:", selectedFile);
    };

    return (
        <div className="relative min-h-screen w-full overflow-hidden">

            {/* Background */}
            <div className="absolute inset-0 -z-10 bg-gradient-to-br from-[#faf7ff] via-[#fcfbff] to-[#f3f6ff]" />

            <div className="absolute top-[-10rem] right-[-5rem] h-[28rem] w-[28rem] rounded-full bg-pink-200/20 blur-3xl" />
            <div className="absolute bottom-[-8rem] left-[-6rem] h-[24rem] w-[24rem] rounded-full bg-violet-200/20 blur-3xl" />

            {/* Content */}
            <div className="flex min-h-screen flex-col px-10 py-10 lg:px-16">

                {/* Header */}
                <div className="mb-10">
                    <h1 className="text-4xl font-bold tracking-tight text-slate-800">
                        New Project
                    </h1>

                    <p className="mt-3 text-base text-slate-500">
                        Upload your OPL file and start generating your software project.
                    </p>
                </div>

                {/* Upload Area */}
                <div className="flex-1 rounded-[2.5rem] border border-violet-100 bg-white/70 p-10 shadow-2xl shadow-violet-100/30 backdrop-blur-xl">

                    <label
                        htmlFor="file-upload"
                        className="flex h-[28rem] w-full cursor-pointer flex-col items-center justify-center rounded-[2rem] border-2 border-dashed border-violet-200 bg-violet-50/40 transition-all hover:bg-violet-50"
                    >
                        <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-3xl bg-white shadow-lg shadow-violet-100">
                            <span className="text-4xl font-light text-violet-500">+</span>
                        </div>

                        <h2 className="text-2xl font-semibold text-slate-700">
                            Upload File
                        </h2>

                        <p className="mt-3 text-sm text-slate-500">
                            Drag and drop or click to browse
                        </p>

                        <p className="mt-1 text-xs text-slate-400">
                            Supported formats: .opl, .txt, .pdf
                        </p>

                        <input
                            id="file-upload"
                            type="file"
                            accept=".opl,.txt,.pdf"
                            onChange={handleFileChange}
                            className="hidden"
                        />
                    </label>

                    {/* Selected file */}
                    {selectedFile && (
                        <div className="mt-6 flex items-center justify-between rounded-2xl border border-violet-100 bg-violet-50/60 px-5 py-4">
                            <div>
                                <p className="text-xs font-medium uppercase tracking-wide text-violet-500">
                                    Selected File
                                </p>

                                <p className="mt-1 font-semibold text-slate-700">
                                    {selectedFile.name}
                                </p>
                            </div>

                            <button
                                onClick={handleUpload}
                                className="rounded-2xl bg-gradient-to-r from-violet-400 to-fuchsia-400 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-violet-200/40 transition hover:scale-[1.01]"
                            >
                                Start Project
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default NewProject;