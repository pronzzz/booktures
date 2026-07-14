import React, { useEffect, useRef } from 'react';
import useReadStore from '../store/readStore';

const SplitReader = () => {
    const { pages, currentPageIndex, setCurrentPageIndex, globalStyle } = useReadStore();

    // Refs for checking intersection
    const pageRefs = useRef([]);

    useEffect(() => {
        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        const index = Number(entry.target.getAttribute('data-index'));
                        setCurrentPageIndex(index);
                    }
                });
            },
            {
                root: null, // viewport
                rootMargin: '-40% 0px -40% 0px', // Trigger when element is in middle of screen
                threshold: 0.1
            }
        );

        pageRefs.current.forEach((ref) => {
            if (ref) observer.observe(ref);
        });

        return () => {
            if (pageRefs.current) {
                pageRefs.current.forEach((ref) => {
                    if (ref) observer.unobserve(ref);
                });
            }
        };
    }, [pages]);

    // Current Image
    const currentImage = pages[currentPageIndex]?.image_url;
    const currentPrompt = pages[currentPageIndex]?.image_prompt;

    return (
        <div className="flex h-screen bg-lumina-dark overflow-hidden">

            {/* LEFT: Text Area */}
            <div className="w-1/2 h-full overflow-y-auto custom-scrollbar p-12 md:p-20 scroll-smooth">
                <div className="max-w-2xl mx-auto">
                    <h1 className="text-4xl font-serif mb-8 text-lumina-accent text-center opacity-80">{globalStyle}</h1>

                    {pages.map((page, index) => (
                        <div
                            key={page.page_number}
                            ref={el => pageRefs.current[index] = el}
                            data-index={index}
                            className="mb-24 transition-opacity duration-500"
                        >
                            <div className="flex items-center text-slate-500 mb-4 text-sm font-mono uppercase tracking-widest">
                                <span>Page {page.page_number}</span>
                                <div className="h-[1px] bg-slate-700 flex-grow ml-4"></div>
                            </div>

                            <p className="text-lg md:text-xl font-serif leading-relaxed text-slate-300">
                                {page.raw_text}
                            </p>

                            {/* Debug or helper text */}
                            {/* <p className="text-xs text-slate-600 mt-2">{page.scene_summary}</p> */}
                        </div>
                    ))}

                    <div className="h-[50vh]"></div> {/* Bottom padding */}
                </div>
            </div>

            {/* RIGHT: Image Area */}
            <div className="w-1/2 h-full bg-black relative border-l border-slate-800">
                {pages.map((page, index) => (
                    <div
                        key={page.page_number}
                        className={`absolute inset-0 transition-opacity duration-1000 ease-in-out ${index === currentPageIndex ? 'opacity-100' : 'opacity-0'}`}
                    >
                        {page.image_url ? (
                            <>
                                <img
                                    src={page.image_url}
                                    alt={`Illustration for page ${page.page_number}`}
                                    className="w-full h-full object-cover"
                                />
                                <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/90 to-transparent p-8">
                                    <p className="text-sm text-slate-400 font-mono italic border-l-2 border-lumina-accent pl-4">
                                        "{page.scene_summary || "Scene visualization..."}"
                                    </p>
                                </div>
                            </>
                        ) : (
                            <div className="flex items-center justify-center h-full text-slate-600">
                                No Image Generated
                            </div>
                        )}
                    </div>
                ))}
            </div>

        </div>
    );
};

export default SplitReader;
