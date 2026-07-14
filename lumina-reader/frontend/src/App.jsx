import React from 'react';
import Uploader from './components/Uploader';
import SplitReader from './components/SplitReader';
import useReadStore from './store/readStore';

function App() {
    const { pages } = useReadStore();

    return (
        <div className="min-h-screen bg-lumina-dark text-white">
            {pages.length === 0 ? (
                <div className="container mx-auto h-screen flex flex-col">
                    <header className="py-8 px-6 flex justify-between items-center">
                        <h1 className="text-2xl font-serif text-slate-100">Lumina<span className="text-lumina-accent">Reader</span></h1>
                        <nav></nav>
                    </header>
                    <main className="flex-grow flex items-center justify-center px-4">
                        <Uploader />
                    </main>
                    <footer className="py-6 text-center text-slate-600 text-sm">
                        &copy; 2026 Lumina Reader. Context-Aware AI Visualization.
                    </footer>
                </div>
            ) : (
                <SplitReader />
            )}
        </div>
    );
}

export default App;
