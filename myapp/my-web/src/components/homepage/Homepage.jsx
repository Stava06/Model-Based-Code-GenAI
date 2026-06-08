import React, { useState } from 'react';
import NavBar from '../NavBar/NavBar';
import Profile from './Profile';
import NewProject from './NewProject';

const Homepage = ({ defaultView = "newProject" }) => {
    const [currentView, setCurrentView] = useState(defaultView);

    return (
        <div className="flex min-h-screen bg-slate-50 font-sans">
            <NavBar currentView={currentView} setCurrentView={setCurrentView} />

            <div className="flex-1 p-8">
                {currentView === "newProject" && <NewProject />}
                {currentView === "profile" && <Profile />}
            </div>
        </div>
    );
};

export default Homepage;

