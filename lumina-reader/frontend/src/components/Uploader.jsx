import React, { useState, useEffect } from 'react';
import useReadStore from '../store/readStore';
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const Uploader = () => {
    const {
        setProject, setUploading, setProcessing, setProgress,
        isUploading, isProcessing, processingProgress, processingMessage,
        setPages, setGlobalStyle
    } = useReadStore();

    const [taskId, setTaskId] = useState(null);

    const handleFileChange = async (event) => {
        const file = event.target.files[0];
        if (!file) return;

        await uploadFile(file);
    };

    const uploadFile = async (file) => {
        setUploading(true);
        const formData = new FormData();
        formData.append("file", file);

        try {
            // 1. Upload
            const res = await axios.post(`${API_URL}/upload`, formData);
            const project = res.data;
            setProject(project.id, project.title);
            setUploading(false);

            // 2. Start Processing
            setProcessing(true);
            const processRes = await axios.post(`${API_URL}/process/${project.id}`);
            setTaskId(processRes.data.task_id);

        } catch (error) {
            console.error("Upload failed", error);
            setUploading(false);
            setProcessing(false);
            alert("Upload failed");
        }
    };

    // WebSocket for status
    useEffect(() => {
        if (!taskId || !isProcessing) return;

        const wsUrl = API_URL.replace(/^http/, 'ws') + `/ws/${taskId}`;
        const ws = new WebSocket(wsUrl);

        ws.onmessage = async (event) => {
            const data = JSON.parse(event.data);
            const { status, progress, message, project_id } = data;

            if (status === 'PROCESSING') {
                setProgress(progress, message);
            } else if (status === 'SUCCESS' || status === 'completed') {
                ws.close();
                // Job Done
                // The task might not return project_id in redis message, so we use the stored projectId
                await fetchBook(useReadStore.getState().projectId);
            } else if (status === 'FAILURE') {
                ws.close();
                setProcessing(false);
                alert("Processing failed: " + message);
            }
        };

        ws.onerror = (error) => {
            console.error("WebSocket error", error);
        };

        return () => ws.close();
    }, [taskId, isProcessing]);

    const fetchBook = async (projectId) => {
        try {
            const res = await axios.get(`${API_URL}/book/${projectId}`);
            setGlobalStyle(res.data.global_style);
            setPages(res.data.pages);
            setProcessing(false);
        } catch (err) {
            console.error("Failed to fetch book", err);
        }
    };

    if (isUploading) {
        return (
            <div className="flex flex-col items-center justify-center p-12 bg-lumina-card rounded-xl shadow-2xl border border-slate-700">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-lumina-accent mb-4"></div>
                <p className="text-lg text-slate-300">Uploading PDF...</p>
            </div>
        );
    }

    if (isProcessing) {
        return (
            <div className="flex flex-col items-center justify-center p-12 bg-lumina-card rounded-xl shadow-2xl border border-slate-700 w-full max-w-md">
                <h3 className="text-xl font-serif text-lumina-accent mb-4">Creating your Visual Novel</h3>
                <div className="w-full bg-slate-700 rounded-full h-2.5 mb-4">
                    <div className="bg-lumina-accent h-2.5 rounded-full transition-all duration-500" style={{ width: `${processingProgress}%` }}></div>
                </div>
                <p className="text-sm text-slate-400">{processingMessage || "Initializing AI..."}</p>
            </div>
        );
    }

    return (
        <div className="flex flex-col items-center justify-center p-16 border-2 border-dashed border-slate-600 rounded-2xl bg-slate-800/50 hover:bg-slate-800 transition-colors">
            <h2 className="text-3xl font-serif mb-4 text-center">Transform your Book</h2>
            <p className="text-slate-400 mb-8 text-center max-w-sm">
                Upload a PDF to generate a scene-by-scene visual experience powered by AI.
            </p>

            <label className="relative cursor-pointer bg-lumina-accent hover:bg-sky-400 text-slate-900 font-bold py-3 px-8 rounded-full shadow-lg transition-transform hover:scale-105">
                <span>Choose PDF</span>
                <input type="file" className="hidden" accept=".pdf" onChange={handleFileChange} />
            </label>
        </div>
    );
};

export default Uploader;
