"use client";

import { useState } from "react";
import { Info } from "lucide-react";

type WhyTooltipProps = {
  text?: string;
};

export function WhyTooltip({ text }: WhyTooltipProps) {
  const [show, setShow] = useState(false);

  return (
    <span className="relative inline-flex">
      <button
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
        onFocus={() => setShow(true)}
        onBlur={() => setShow(false)}
        onClick={(e) => { e.preventDefault(); setShow(!show); }}
        className="text-gray-300 hover:text-gray-500 transition-colors"
        title="Why this suggestion?"
      >
        <Info className="w-3.5 h-3.5" />
      </button>
      {show && (
        <div className="absolute bottom-full left-0 mb-2 w-64 p-3 bg-gray-900 text-white text-xs rounded-lg shadow-lg z-50">
          <p className="leading-relaxed">
            {text || "Based on similar jobs, material costs, and typical labor hours for this type of work."}
          </p>
          <div className="absolute top-full left-3 w-2 h-2 bg-gray-900 rotate-45" />
        </div>
      )}
    </span>
  );
}
