import { create } from 'zustand';

const useReadStore = create((set) => ({
    projectId: null,
    projectTitle: "",
    globalStyle: "",
    pages: [],
    currentPageIndex: 0,

    // Status
    isUploading: false,
    isProcessing: false,
    processingProgress: 0,
    processingMessage: "",

    // Actions
    setProject: (id, title) => set({ projectId: id, projectTitle: title }),
    setGlobalStyle: (style) => set({ globalStyle: style }),
    setPages: (pages) => set({ pages }),
    setCurrentPageIndex: (index) => set({ currentPageIndex: index }),

    setUploading: (status) => set({ isUploading: status }),
    setProcessing: (status) => set({ isProcessing: status }),
    setProgress: (progress, message) => set({ processingProgress: progress, processingMessage: message }),

    reset: () => set({
        projectId: null,
        projectTitle: "",
        globalStyle: "",
        pages: [],
        currentPageIndex: 0,
        isUploading: false,
        isProcessing: false,
        processingProgress: 0,
        processingMessage: ""
    })
}));

export default useReadStore;
