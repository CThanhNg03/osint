import React from "react";

const Header = ({ view, onChangeView }) => {
  return (
    <header className="bg-gray-900 border-b border-gray-800 p-4 flex justify-between items-center">
      <div className="flex items-center gap-3">
        <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse"></div>
        <h1 className="text-xl font-bold text-white tracking-wider">
          INTELLIGENCE MONITORING SYSTEM
        </h1>
      </div>
      <div className="flex items-center gap-2 text-sm text-gray-200">
        <button
          className={`px-3 py-1 rounded border ${
            view === "dashboard"
              ? "bg-indigo-600 border-indigo-500 text-white"
              : "bg-gray-800 border-gray-700"
          }`}
          onClick={() => onChangeView("dashboard")}
        >
          Dashboard
        </button>
        <button
          className={`px-3 py-1 rounded border ${
            view === "kg"
              ? "bg-indigo-600 border-indigo-500 text-white"
              : "bg-gray-800 border-gray-700"
          }`}
          onClick={() => onChangeView("kg")}
        >
          KG Explorer
        </button>
        <div className="px-3 py-1 bg-gray-800 rounded border border-gray-700 text-gray-400">
          <span className="text-green-500">●</span> SYSTEM ONLINE
        </div>
        <div className="text-gray-400">{new Date().toLocaleDateString()}</div>
      </div>
    </header>
  );
};

export default Header;
