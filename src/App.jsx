import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Home, MessageSquare, Satellite, Map as MapIcon, RefreshCw, BarChart2,
  Folder, FileText, Settings, HelpCircle, ChevronLeft, ChevronRight,
  Search, Calendar, Paperclip, Sparkles, Bell, ZoomIn, ZoomOut, Locate,
  Layers, Ruler, Maximize2, CheckCircle2, Circle, Brain, Download,
  Share2, ChevronDown, X, MapPin, Radio, Globe2, Clock, TrendingUp,
  Droplets, Building2, Trees, Wheat, Eye, FileBarChart, Plus, ArrowRight
} from "lucide-react";
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from "recharts";

/* ============================================================
   SatQuery AI — Geospatial Intelligence Platform (Prototype)
   Colors:
   bg      #070B14 (near-black navy)
   panel   #0D1420
   border  #1C2638
   blue    #3B82F6
   cyan    #22D3EE
   violet  #8B5CF6
   green   #22C55E
   amber   #F59E0B
   red     #EF4444
   ============================================================ */

const NAV_ITEMS = [
  { id: "dashboard", label: "Dashboard", icon: Home },
  { id: "query", label: "Query Assistant", icon: MessageSquare },
  { id: "imagery", label: "Imagery", icon: Satellite },
  { id: "map", label: "Analysis Map", icon: MapIcon },
  { id: "change", label: "Change Detection", icon: RefreshCw },
  { id: "analytics", label: "Analytics", icon: BarChart2 },
  { id: "projects", label: "Projects", icon: Folder },
  { id: "reports", label: "Reports", icon: FileText },
];

const EXAMPLE_CHIPS = [
  { label: "Detect water bodies", icon: Droplets },
  { label: "Find new buildings", icon: Building2 },
  { label: "Compare forest cover", icon: Trees },
  { label: "Identify agricultural areas", icon: Wheat },
  { label: "Detect flood affected regions", icon: Droplets },
];

const DEFAULT_QUERY = "Show flooded areas around Assam between July and August 2025.";

const DETECTED_OBJECTS = [
  { id: "wb1", name: "Water Body 01", confidence: 98, x: 32, y: 38, area: "9.8 km²" },
  { id: "wb2", name: "Water Body 02", confidence: 95, x: 58, y: 55, area: "7.1 km²" },
  { id: "wb3", name: "Water Body 03", confidence: 93, x: 71, y: 28, area: "6.7 km²" },
];

const PIPELINE_STEPS = [
  "Understanding Query",
  "Identifying Location",
  "Selecting Satellite Data",
  "Preparing Imagery",
  "Running AI Analysis",
  "Spatial Analysis",
  "Generating Results",
];

const ANALYTICS_TIME_SERIES = [
  { m: "Mar", objects: 120, area: 88 },
  { m: "Apr", objects: 160, area: 102 },
  { m: "May", objects: 145, area: 96 },
  { m: "Jun", objects: 210, area: 134 },
  { m: "Jul", objects: 260, area: 161 },
  { m: "Aug", objects: 302, area: 189 },
];

const CONFIDENCE_DIST = [
  { name: "90-100%", value: 62, color: "#22C55E" },
  { name: "75-90%", value: 27, color: "#22D3EE" },
  { name: "50-75%", value: 8, color: "#F59E0B" },
  { name: "<50%", value: 3, color: "#EF4444" },
];

const ACTIVITY = [
  { d: "Mon", n: 4 }, { d: "Tue", n: 7 }, { d: "Wed", n: 5 },
  { d: "Thu", n: 9 }, { d: "Fri", n: 12 }, { d: "Sat", n: 6 }, { d: "Sun", n: 3 },
];

const REPORTS = [
  { name: "Assam Flood Assessment — Aug 2025", location: "Assam, India", date: "24 Aug 2025", type: "Flood Detection", status: "Complete" },
  { name: "Sundarbans Mangrove Change", location: "West Bengal, India", date: "18 Aug 2025", type: "Change Detection", status: "Complete" },
  { name: "Bengaluru Urban Expansion Q2", location: "Karnataka, India", date: "02 Aug 2025", type: "Object Detection", status: "Complete" },
  { name: "Punjab Crop Health Survey", location: "Punjab, India", date: "27 Jul 2025", type: "Agricultural Analysis", status: "Processing" },
];

/* ------------------ Toast system ------------------ */
function useToasts() {
  const [toasts, setToasts] = useState([]);
  const push = useCallback((message, tone = "info") => {
    const id = Math.random().toString(36).slice(2);
    setToasts((t) => [...t, { id, message, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3200);
  }, []);
  return { toasts, push };
}

function ToastStack({ toasts }) {
  const toneColor = { info: "#3B82F6", success: "#22C55E", warn: "#F59E0B" };
  return (
    <div style={{ position: "fixed", bottom: 20, right: 20, zIndex: 200, display: "flex", flexDirection: "column", gap: 8 }}>
      {toasts.map((t) => (
        <div key={t.id} style={{
          background: "#0D1420", border: `1px solid ${toneColor[t.tone] || "#1C2638"}`,
          borderLeft: `3px solid ${toneColor[t.tone] || "#3B82F6"}`,
          color: "#E5E9F0", padding: "10px 16px", borderRadius: 10, fontSize: 13,
          minWidth: 220, boxShadow: "0 8px 24px rgba(0,0,0,0.45)",
          animation: "satq-slide-in 0.25s ease-out"
        }}>
          {t.message}
        </div>
      ))}
    </div>
  );
}

/* ------------------ Small UI atoms ------------------ */
function Card({ children, style, className }) {
  return (
    <div className={className} style={{
      background: "linear-gradient(180deg, rgba(19,27,44,0.65), rgba(13,20,32,0.65))",
      border: "1px solid #1C2638", borderRadius: 16, backdropFilter: "blur(6px)",
      boxShadow: "0 1px 0 rgba(255,255,255,0.02) inset", ...style
    }}>
      {children}
    </div>
  );
}

function Badge({ children, color = "#22C55E", bg = "rgba(34,197,94,0.12)" }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11.5, fontWeight: 600,
      color, background: bg, border: `1px solid ${color}44`, padding: "4px 10px", borderRadius: 999,
      letterSpacing: 0.2
    }}>
      {children}
    </span>
  );
}

function StatTile({ label, value, sub, accent = "#22D3EE" }) {
  return (
    <div style={{ flex: 1, minWidth: 130, padding: "16px 18px", borderRadius: 14, background: "rgba(255,255,255,0.02)", border: "1px solid #1C2638" }}>
      <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 26, fontWeight: 700, color: "#F2F5FA" }}>{value}</div>
      <div style={{ fontSize: 12.5, color: "#8B94A8", marginTop: 4 }}>{label}</div>
      {sub && <div style={{ fontSize: 11.5, color: accent, marginTop: 6, fontWeight: 600 }}>{sub}</div>}
    </div>
  );
}

/* ------------------ Mock GIS Map ------------------ */
function SatelliteMap({
  objects = DETECTED_OBJECTS, selectedId, onSelect, showFlood = false,
  height = 460, live = false,
}) {
  const [layer, setLayer] = useState("Satellite");
  const [layersOpen, setLayersOpen] = useState(false);
  const [zoom, setZoom] = useState(1);

  const layerBg = {
    Satellite: "linear-gradient(135deg,#0B1220 0%, #142235 35%, #0E1B2A 60%, #1A2A20 100%)",
    Street: "linear-gradient(135deg,#101826 0%, #16202E 100%)",
    Terrain: "linear-gradient(135deg,#0F1A15 0%, #1B2A1E 45%, #23301F 100%)",
    "Analysis Overlay": "linear-gradient(135deg,#0B1220 0%, #172233 60%, #10202A 100%)",
  };

  return (
    <div style={{
      position: "relative", height, borderRadius: 16, overflow: "hidden",
      border: "1px solid #1C2638", background: layerBg[layer],
      transform: `scale(${zoom})`, transformOrigin: "center center", transition: "transform 0.2s ease"
    }}>
      {/* terrain-ish decorative shapes */}
      <svg width="100%" height="100%" viewBox="0 0 400 300" preserveAspectRatio="none" style={{ position: "absolute", inset: 0, opacity: 0.55 }}>
        <defs>
          <linearGradient id="riverGrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#1E4E6B" />
            <stop offset="100%" stopColor="#123049" />
          </linearGradient>
        </defs>
        <path d="M0,180 C60,150 90,210 150,190 C210,170 240,230 300,210 C340,198 370,220 400,205 L400,300 L0,300 Z" fill="url(#riverGrad)" />
        <path d="M-10,60 C60,40 120,90 200,70 C260,55 320,40 410,65" stroke="#243449" strokeWidth="6" fill="none" opacity="0.5" />
        <path d="M20,260 C90,240 150,270 220,250 C280,235 330,255 400,240" stroke="#2B3B52" strokeWidth="4" fill="none" opacity="0.4" />
        {/* road grid */}
        {[...Array(6)].map((_, i) => (
          <line key={i} x1={i * 70} y1="0" x2={i * 70} y2="300" stroke="#2A3850" strokeWidth="1" opacity="0.25" />
        ))}
        {[...Array(4)].map((_, i) => (
          <line key={"h" + i} x1="0" y1={i * 80} x2="400" y2={i * 80} stroke="#2A3850" strokeWidth="1" opacity="0.25" />
        ))}
      </svg>

      {live && (
        <>
          <div style={{ position: "absolute", top: 14, left: 14, display: "flex", alignItems: "center", gap: 6, background: "rgba(7,11,20,0.75)", border: "1px solid #EF444455", padding: "5px 10px", borderRadius: 999, zIndex: 6 }}>
            <span style={{ width: 7, height: 7, borderRadius: 999, background: "#EF4444", boxShadow: "0 0 8px #EF4444" }} />
            <span style={{ fontSize: 11, fontWeight: 700, color: "#FCA5A5", letterSpacing: 0.5 }}>LIVE ANALYSIS</span>
          </div>
          {/* satellite scanning sweep */}
          <div style={{
            position: "absolute", top: 0, bottom: 0, width: "18%",
            background: "linear-gradient(90deg, transparent, rgba(34,211,238,0.16) 45%, rgba(34,211,238,0.35) 50%, rgba(34,211,238,0.16) 55%, transparent)",
            animation: "satq-scan 2.6s linear infinite", pointerEvents: "none", zIndex: 4
          }} />
        </>
      )}

      {/* selected region boundary */}
      <div style={{
        position: "absolute", left: "18%", top: "14%", width: "58%", height: "62%",
        border: "1.5px dashed #3B82F6aa", borderRadius: 10, pointerEvents: "none"
      }} />

      {/* flood overlay polygons */}
      {showFlood && (
        <svg width="100%" height="100%" viewBox="0 0 400 300" style={{ position: "absolute", inset: 0 }}>
          <polygon points="110,120 150,110 175,150 150,190 105,175" fill="#EF444455" stroke="#EF4444" strokeWidth="1.5" />
          <polygon points="220,90 260,95 255,130 215,135" fill="#22D3EE44" stroke="#22D3EE" strokeWidth="1.5" />
          <polygon points="240,170 290,165 300,205 250,215" fill="#EF444455" stroke="#EF4444" strokeWidth="1.5" />
        </svg>
      )}

      {/* detected object markers */}
      {objects.map((o) => {
        const active = selectedId === o.id;
        return (
          <button
            key={o.id}
            onClick={() => onSelect && onSelect(o.id)}
            title={o.name}
            style={{
              position: "absolute", left: `${o.x}%`, top: `${o.y}%`, transform: "translate(-50%,-50%)",
              width: active ? 22 : 14, height: active ? 22 : 14, borderRadius: "50%",
              background: active ? "#22D3EE" : "#3B82F6", border: "2px solid #0B1220",
              boxShadow: active ? "0 0 0 6px rgba(34,211,238,0.25), 0 0 12px #22D3EE" : "0 0 8px rgba(59,130,246,0.6)",
              cursor: "pointer", transition: "all 0.2s ease", zIndex: 5
            }}
          />
        );
      })}

      {/* Layer badge */}
      <div style={{ position: "absolute", top: 14, right: 14, display: "flex", gap: 8 }}>
        <div style={{ position: "relative" }}>
          <button onClick={() => setLayersOpen((v) => !v)} style={mapBtnStyle}>
            <Layers size={15} /> <span style={{ fontSize: 12 }}>{layer}</span> <ChevronDown size={13} />
          </button>
          {layersOpen && (
            <div style={{ position: "absolute", top: 38, right: 0, background: "#0D1420", border: "1px solid #1C2638", borderRadius: 10, overflow: "hidden", width: 160, zIndex: 20 }}>
              {["Satellite", "Street", "Terrain", "Analysis Overlay"].map((l) => (
                <div key={l} onClick={() => { setLayer(l); setLayersOpen(false); }}
                  style={{ padding: "9px 12px", fontSize: 12.5, color: l === layer ? "#22D3EE" : "#C7CEDB", cursor: "pointer", background: l === layer ? "rgba(34,211,238,0.08)" : "transparent" }}>
                  {l}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Map controls */}
      <div style={{ position: "absolute", bottom: 14, right: 14, display: "flex", flexDirection: "column", gap: 6 }}>
        <button style={mapIconBtn} onClick={() => setZoom((z) => Math.min(z + 0.15, 1.6))}><ZoomIn size={15} /></button>
        <button style={mapIconBtn} onClick={() => setZoom((z) => Math.max(z - 0.15, 0.85))}><ZoomOut size={15} /></button>
        <button style={mapIconBtn}><Locate size={15} /></button>
        <button style={mapIconBtn}><Ruler size={15} /></button>
        <button style={mapIconBtn}><Maximize2 size={15} /></button>
      </div>

      <div style={{ position: "absolute", bottom: 14, left: 14, fontSize: 10.5, color: "#5A6478", background: "rgba(7,11,20,0.6)", padding: "3px 8px", borderRadius: 6 }}>
        Basemap: {layer} · Zoom {zoom.toFixed(2)}x
      </div>
    </div>
  );
}

const mapBtnStyle = {
  display: "flex", alignItems: "center", gap: 6, background: "rgba(7,11,20,0.8)",
  border: "1px solid #1C2638", color: "#C7CEDB", padding: "7px 10px", borderRadius: 10,
  cursor: "pointer", fontSize: 12
};
const mapIconBtn = {
  ...mapBtnStyle, padding: 8, justifyContent: "center"
};

/* ------------------ Analysis processing modal ------------------ */
function ProcessingModal({ onDone }) {
  const [stepIdx, setStepIdx] = useState(0);
  useEffect(() => {
    if (stepIdx >= PIPELINE_STEPS.length) {
      const t = setTimeout(onDone, 500);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setStepIdx((i) => i + 1), 380);
    return () => clearTimeout(t);
  }, [stepIdx]);

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(4,6,12,0.72)", zIndex: 150,
      display: "flex", alignItems: "center", justifyContent: "center", backdropFilter: "blur(3px)"
    }}>
      <Card style={{ width: 420, padding: 28 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 18 }}>
          <div style={{ width: 34, height: 34, borderRadius: 10, background: "linear-gradient(135deg,#3B82F6,#22D3EE)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Sparkles size={17} color="#0B1220" />
          </div>
          <div>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 15, color: "#F2F5FA" }}>Running AI Analysis</div>
            <div style={{ fontSize: 11.5, color: "#8B94A8" }}>This usually takes a few seconds</div>
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {PIPELINE_STEPS.map((step, i) => {
            const done = i < stepIdx;
            const active = i === stepIdx;
            return (
              <div key={step} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                {done ? <CheckCircle2 size={16} color="#22C55E" /> :
                  active ? <span style={{ width: 16, height: 16, borderRadius: "50%", border: "2px solid #22D3EE", borderTopColor: "transparent", display: "inline-block", animation: "satq-spin 0.7s linear infinite" }} /> :
                    <Circle size={16} color="#3A4256" />}
                <span style={{ fontSize: 13, color: done ? "#C7CEDB" : active ? "#F2F5FA" : "#5A6478", fontWeight: active ? 600 : 400 }}>
                  {step}
                </span>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}

/* ------------------ Sidebar ------------------ */
function Sidebar({ page, setPage, collapsed, setCollapsed }) {
  return (
    <div style={{
      width: collapsed ? 74 : 236, transition: "width 0.2s ease", flexShrink: 0,
      background: "#0A0F1A", borderRight: "1px solid #161F30", display: "flex", flexDirection: "column",
      height: "100vh", position: "sticky", top: 0
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "20px 18px", borderBottom: "1px solid #161F30" }}>
        <div style={{
          width: 34, height: 34, borderRadius: 9, flexShrink: 0,
          background: "linear-gradient(135deg,#3B82F6,#8B5CF6)", display: "flex", alignItems: "center", justifyContent: "center",
          boxShadow: "0 0 16px rgba(59,130,246,0.35)"
        }}>
          <Satellite size={17} color="#fff" />
        </div>
        {!collapsed && (
          <div>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 14.5, color: "#F2F5FA", letterSpacing: 0.2 }}>SatQuery AI</div>
            <div style={{ fontSize: 10, color: "#5A6478" }}>Geospatial Intelligence</div>
          </div>
        )}
      </div>
      {!collapsed && (
        <div style={{ margin: "10px 18px 0", fontSize: 10, color: "#4A5568", background: "rgba(139,92,246,0.06)", border: "1px solid #8B5CF633", borderRadius: 8, padding: "6px 9px" }}>
          Built for SIH26167 · ISRO datasets (simulated: Bhuvan, Sentinel, Landsat)
        </div>
      )}

      <div style={{ flex: 1, padding: "14px 10px", display: "flex", flexDirection: "column", gap: 3, overflowY: "auto" }}>
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const active = page === item.id;
          return (
            <button key={item.id} onClick={() => setPage(item.id)}
              style={{
                display: "flex", alignItems: "center", gap: 12, padding: "10px 12px", borderRadius: 10,
                background: active ? "linear-gradient(90deg, rgba(59,130,246,0.16), rgba(34,211,238,0.06))" : "transparent",
                border: active ? "1px solid #2A3F63" : "1px solid transparent",
                color: active ? "#5FC5F0" : "#8B94A8", cursor: "pointer", textAlign: "left", fontSize: 13, fontWeight: active ? 600 : 500,
                justifyContent: collapsed ? "center" : "flex-start"
              }}>
              <Icon size={17} style={{ flexShrink: 0 }} />
              {!collapsed && item.label}
            </button>
          );
        })}
      </div>

      <div style={{ padding: "10px", borderTop: "1px solid #161F30", display: "flex", flexDirection: "column", gap: 3 }}>
        <button style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 12px", borderRadius: 10, background: "transparent", border: "none", color: "#8B94A8", cursor: "pointer", fontSize: 13, justifyContent: collapsed ? "center" : "flex-start" }}>
          <Settings size={17} /> {!collapsed && "Settings"}
        </button>
        <button style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 12px", borderRadius: 10, background: "transparent", border: "none", color: "#8B94A8", cursor: "pointer", fontSize: 13, justifyContent: collapsed ? "center" : "flex-start" }}>
          <HelpCircle size={17} /> {!collapsed && "Help"}
        </button>
        <button onClick={() => setCollapsed((c) => !c)}
          style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8, marginTop: 6, padding: "8px", borderRadius: 10, background: "#101828", border: "1px solid #1C2638", color: "#8B94A8", cursor: "pointer" }}>
          {collapsed ? <ChevronRight size={15} /> : <><ChevronLeft size={15} /> <span style={{ fontSize: 11.5 }}>Collapse</span></>}
        </button>
      </div>
    </div>
  );
}

/* ------------------ Top bar ------------------ */
function TopBar({ title, subtitle }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 22, flexWrap: "wrap", gap: 12 }}>
      <div>
        <h1 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 24, fontWeight: 700, color: "#F2F5FA", margin: 0 }}>{title}</h1>
        {subtitle && <p style={{ color: "#8B94A8", fontSize: 13.5, marginTop: 4 }}>{subtitle}</p>}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "#4ADE80", background: "rgba(34,197,94,0.08)", border: "1px solid #22C55E33", padding: "6px 12px", borderRadius: 999 }}>
          <span style={{ width: 6, height: 6, borderRadius: 999, background: "#22C55E", boxShadow: "0 0 6px #22C55E" }} />
          System Online
        </div>
        <button style={{ background: "transparent", border: "1px solid #1C2638", borderRadius: 10, padding: 8, color: "#8B94A8", cursor: "pointer" }}>
          <Bell size={16} />
        </button>
        <div style={{ width: 34, height: 34, borderRadius: "50%", background: "linear-gradient(135deg,#8B5CF6,#3B82F6)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12.5, fontWeight: 700, color: "#fff" }}>
          AN
        </div>
      </div>
    </div>
  );
}

/* ------------------ Query panel (shared) ------------------ */
function QueryPanel({ query, setQuery, onAnalyze }) {
  return (
    <Card style={{ padding: 24 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
        <Sparkles size={17} color="#22D3EE" />
        <h2 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 17, fontWeight: 700, color: "#F2F5FA", margin: 0 }}>Ask SatQuery</h2>
      </div>
      <p style={{ color: "#8B94A8", fontSize: 13, margin: "2px 0 14px" }}>Analyze satellite imagery using natural language.</p>

      <textarea
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Ask anything about your satellite imagery…"
        rows={3}
        style={{
          width: "100%", resize: "none", background: "#0B121F", border: "1px solid #1C2638",
          borderRadius: 12, padding: "14px 16px", color: "#F2F5FA", fontSize: 14.5, outline: "none",
          fontFamily: "inherit", boxSizing: "border-box"
        }}
      />

      <div style={{ display: "flex", gap: 10, marginTop: 12, flexWrap: "wrap" }}>
        <ToolBtn icon={MapPin} label="Select Region" />
        <ToolBtn icon={Calendar} label="Date Range" />
        <ToolBtn icon={Paperclip} label="Attach Imagery" />
        <button onClick={onAnalyze} style={{
          marginLeft: "auto", display: "flex", alignItems: "center", gap: 8,
          background: "linear-gradient(135deg,#3B82F6,#22D3EE)", border: "none", color: "#06121F",
          fontWeight: 700, fontSize: 13.5, padding: "10px 20px", borderRadius: 10, cursor: "pointer",
          boxShadow: "0 4px 18px rgba(34,211,238,0.25)"
        }}>
          <Sparkles size={15} /> Analyze
        </button>
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 16 }}>
        {EXAMPLE_CHIPS.map((c) => {
          const Icon = c.icon;
          return (
            <button key={c.label} onClick={() => setQuery(c.label)}
              style={{
                display: "flex", alignItems: "center", gap: 6, background: "rgba(139,92,246,0.08)",
                border: "1px solid #8B5CF633", color: "#C7B9F5", fontSize: 12, padding: "7px 12px",
                borderRadius: 999, cursor: "pointer"
              }}>
              <Icon size={12.5} /> {c.label}
            </button>
          );
        })}
      </div>
    </Card>
  );
}

function ToolBtn({ icon: Icon, label }) {
  return (
    <button style={{
      display: "flex", alignItems: "center", gap: 7, background: "#0B121F", border: "1px solid #1C2638",
      color: "#C7CEDB", fontSize: 12.5, padding: "9px 13px", borderRadius: 10, cursor: "pointer"
    }}>
      <Icon size={14} /> {label}
    </button>
  );
}

/* ------------------ AI Analysis right panel ------------------ */
function AnalysisPanel({ complete, selectedId, setSelectedId, push }) {
  const [reasoningOpen, setReasoningOpen] = useState(true);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Card style={{ padding: 20 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <h3 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 15, fontWeight: 700, color: "#F2F5FA", margin: 0 }}>AI Analysis</h3>
          {complete ? <Badge color="#22C55E">● Analysis Complete</Badge> : <Badge color="#F59E0B" bg="rgba(245,158,11,0.1)">● Awaiting Query</Badge>}
        </div>
        {complete ? (
          <>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginBottom: 18 }}>
              <StatTile label="Water Bodies" value="12" />
              <StatTile label="Total Area" value="23.6 km²" />
              <StatTile label="Confidence" value="94.8%" accent="#22C55E" />
              <StatTile label="Change" value="+12.4%" accent="#EF4444" />
            </div>
            <div style={{ fontSize: 12.5, fontWeight: 700, color: "#8B94A8", marginBottom: 10, letterSpacing: 0.3 }}>DETECTED OBJECTS</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {DETECTED_OBJECTS.map((o) => (
                <div key={o.id} style={{
                  display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 12px",
                  borderRadius: 10, background: selectedId === o.id ? "rgba(34,211,238,0.08)" : "rgba(255,255,255,0.02)",
                  border: `1px solid ${selectedId === o.id ? "#22D3EE55" : "#1C2638"}`
                }}>
                  <div>
                    <div style={{ fontSize: 13, color: "#F2F5FA", fontWeight: 600 }}>{o.name}</div>
                    <div style={{ fontSize: 11.5, color: "#8B94A8" }}>{o.confidence}% confidence · {o.area}</div>
                  </div>
                  <button onClick={() => { setSelectedId(o.id); push(`Focused on ${o.name}`, "info"); }}
                    style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11.5, background: "transparent", border: "1px solid #2A3F63", color: "#5FC5F0", padding: "6px 10px", borderRadius: 8, cursor: "pointer" }}>
                    <Eye size={12} /> View on Map
                  </button>
                </div>
              ))}
            </div>
          </>
        ) : (
          <div style={{ fontSize: 13, color: "#5A6478", textAlign: "center", padding: "24px 0" }}>
            Run a query to see AI analysis results here.
          </div>
        )}
      </Card>

      {complete && (
        <Card style={{ padding: 20 }}>
          <div onClick={() => setReasoningOpen((v) => !v)} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", cursor: "pointer" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Brain size={16} color="#8B5CF6" />
              <h3 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 14.5, fontWeight: 700, color: "#F2F5FA", margin: 0 }}>AI Analysis Process</h3>
            </div>
            <ChevronDown size={16} color="#8B94A8" style={{ transform: reasoningOpen ? "rotate(180deg)" : "none", transition: "0.2s" }} />
          </div>
          {reasoningOpen && (
            <div style={{ marginTop: 16 }}>
              <div style={{ fontSize: 11.5, fontWeight: 700, color: "#8B94A8", marginBottom: 8 }}>QUERY UNDERSTANDING</div>
              {["Location identified", "Time range identified", "Analysis type identified"].map((t) => (
                <div key={t} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5, color: "#C7CEDB", marginBottom: 6 }}>
                  <CheckCircle2 size={13} color="#22C55E" /> {t}
                </div>
              ))}
              <div style={{ fontSize: 11.5, fontWeight: 700, color: "#8B94A8", margin: "14px 0 8px" }}>SELECTED TOOLS</div>
              {["Satellite Retrieval", "Vision Model", "Segmentation", "Change Detection", "GIS Spatial Analysis"].map((t) => (
                <div key={t} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5, color: "#C7CEDB", marginBottom: 6 }}>
                  <CheckCircle2 size={13} color="#22C55E" /> {t}
                </div>
              ))}
              <div style={{ fontSize: 11.5, fontWeight: 700, color: "#8B94A8", margin: "14px 0 8px" }}>MODEL</div>
              <p style={{ fontSize: 12.5, color: "#8B94A8", lineHeight: 1.6, margin: 0 }}>
                Vision-language fusion encoder + segmentation head, fine-tuned on multispectral flood/water-body imagery.
              </p>
              <div style={{ fontSize: 11.5, fontWeight: 700, color: "#8B94A8", margin: "14px 0 8px" }}>RESULT</div>
              <p style={{ fontSize: 13, color: "#C7CEDB", lineHeight: 1.6, margin: 0 }}>
                12 water bodies were identified in the selected region with an estimated total area of 23.6 km².
              </p>
              <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
                <button onClick={() => push("Showing supporting evidence tiles", "info")} style={ghostBtn}>View Evidence</button>
                <button onClick={() => push("Methodology panel opened", "info")} style={ghostBtn}>Show Methodology</button>
              </div>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

const ghostBtn = {
  fontSize: 12, background: "transparent", border: "1px solid #1C2638", color: "#C7CEDB",
  padding: "8px 12px", borderRadius: 9, cursor: "pointer"
};

/* ------------------ Dashboard / Query Assistant page ------------------ */
function DashboardPage({ query, setQuery, analysisState, runAnalysis, selectedId, setSelectedId, push }) {
  const complete = analysisState === "complete";
  return (
    <div>
      <TopBar title="Good morning, Analyst" subtitle="Explore satellite intelligence using natural language." />
      <div style={{ display: "grid", gridTemplateColumns: "1.6fr 1fr", gap: 20, alignItems: "start" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <QueryPanel query={query} setQuery={setQuery} onAnalyze={runAnalysis} />
          <Card style={{ padding: 20 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
              <h3 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 15, fontWeight: 700, color: "#F2F5FA", margin: 0 }}>Analysis Map</h3>
              {complete && <span style={{ fontSize: 11.5, color: "#8B94A8" }}>Sentinel-2 + Sentinel-1 · Dhemaji, Assam · 27.48°N, 94.56°E</span>}
            </div>
            <SatelliteMap
              objects={complete ? DETECTED_OBJECTS : []}
              selectedId={selectedId}
              onSelect={setSelectedId}
              showFlood={complete}
              live={complete}
            />
          </Card>
        </div>
        <AnalysisPanel complete={complete} selectedId={selectedId} setSelectedId={setSelectedId} push={push} />
      </div>
    </div>
  );
}

/* ------------------ Imagery page ------------------ */
function ImageryPage() {
  const sources = [
    { icon: Satellite, tone: "#3B82F6", title: "Optical", sat: "Sentinel-2", res: "10 m resolution", extra: "Cloud coverage: 4%", date: "22 Aug 2025", status: "Processed" },
    { icon: Radio, tone: "#8B5CF6", title: "SAR", sat: "Sentinel-1", res: "10 m resolution", extra: "All-weather imaging", date: "21 Aug 2025", status: "Processed" },
    { icon: Globe2, tone: "#22C55E", title: "Landsat", sat: "Landsat-9", res: "30 m resolution", extra: "Historical imagery", date: "14 Aug 2025", status: "Archived" },
  ];
  return (
    <div>
      <TopBar title="Imagery Sources" subtitle="Multimodal satellite data feeding the current analysis." />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 18 }}>
        {sources.map((s) => {
          const Icon = s.icon;
          return (
            <Card key={s.title} style={{ padding: 20 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
                <div style={{ width: 36, height: 36, borderRadius: 10, background: `${s.tone}22`, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <Icon size={18} color={s.tone} />
                </div>
                <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 15, color: "#F2F5FA" }}>{s.title}</div>
              </div>
              <div style={{ height: 120, borderRadius: 10, marginBottom: 14, background: "linear-gradient(135deg,#101B2C,#16283A)", border: "1px solid #1C2638" }} />
              <div style={{ fontSize: 13.5, color: "#C7CEDB", fontWeight: 600, marginBottom: 2 }}>{s.sat}</div>
              <div style={{ fontSize: 12, color: "#8B94A8", marginBottom: 10 }}>{s.res} · {s.extra}</div>
              <Row label="Acquisition Date" value={s.date} />
              <Row label="Resolution" value={s.res.replace(" resolution", "")} />
              <Row label="Processing Status" value={s.status} valueColor={s.status === "Processed" ? "#22C55E" : "#8B94A8"} />
            </Card>
          );
        })}
      </div>
    </div>
  );
}

function Row({ label, value, valueColor = "#F2F5FA" }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, padding: "6px 0", borderTop: "1px solid #161F30" }}>
      <span style={{ color: "#8B94A8" }}>{label}</span>
      <span style={{ color: valueColor, fontWeight: 600 }}>{value}</span>
    </div>
  );
}

/* ------------------ Analysis Map / Workspace page ------------------ */
function AnalysisMapPage({ push }) {
  const [selectedId, setSelectedId] = useState(null);
  const [primary, setPrimary] = useState("Optical");
  const [secondary, setSecondary] = useState("SAR");
  const [analysisType, setAnalysisType] = useState("Object Detection");
  const [running, setRunning] = useState(false);

  return (
    <div>
      <TopBar title="Analysis Workspace" subtitle="Build and configure a custom spatial analysis query." />
      <div style={{ display: "grid", gridTemplateColumns: "260px 1.6fr 300px", gap: 18, alignItems: "start" }}>
        <Card style={{ padding: 18 }}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 14, color: "#F2F5FA", marginBottom: 14 }}>Query Builder</div>
          <Field label="Location"><SelectLike value="Assam, India" /></Field>
          <Field label="Primary Data"><Dropdown value={primary} setValue={setPrimary} options={["Optical", "SAR", "Landsat"]} /></Field>
          <Field label="Secondary Data"><Dropdown value={secondary} setValue={setSecondary} options={["SAR", "Optical", "None"]} /></Field>
          <Field label="Time Range">
            <div style={{ display: "flex", gap: 6 }}>
              <SelectLike value="01 Jul 2025" small />
              <SelectLike value="30 Aug 2025" small />
            </div>
          </Field>
          <Field label="Analysis Type"><Dropdown value={analysisType} setValue={setAnalysisType} options={["Object Detection", "Change Detection", "Segmentation"]} /></Field>
          <Field label="Target"><SelectLike value="Water Bodies" /></Field>
          <Field label="Model"><SelectLike value="Auto Select" /></Field>
          <button onClick={() => { setRunning(true); push("Analysis started", "info"); setTimeout(() => { setRunning(false); push("Workspace analysis complete", "success"); }, 1800); }}
            style={{
              width: "100%", marginTop: 6, display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
              background: "linear-gradient(135deg,#3B82F6,#22D3EE)", border: "none", color: "#06121F",
              fontWeight: 700, fontSize: 13, padding: "11px 0", borderRadius: 10, cursor: "pointer"
            }}>
            {running ? <RefreshCw size={14} className="satq-spin" /> : <Sparkles size={14} />} Run Analysis
          </button>
        </Card>

        <Card style={{ padding: 18 }}>
          <SatelliteMap objects={DETECTED_OBJECTS} selectedId={selectedId} onSelect={setSelectedId} height={520} live={running} />
        </Card>

        <Card style={{ padding: 18 }}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 14, color: "#F2F5FA", marginBottom: 14 }}>Results</div>
          <StatRow label="Objects Detected" value="43" />
          <StatRow label="Area" value="128.4 km²" />
          <StatRow label="Confidence" value="94.2%" />
          <StatRow label="Processing Time" value="18.4 sec" />
        </Card>
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: 11.5, color: "#8B94A8", marginBottom: 6 }}>{label}</div>
      {children}
    </div>
  );
}
function SelectLike({ value, small }) {
  return (
    <div style={{ flex: small ? 1 : "none", background: "#0B121F", border: "1px solid #1C2638", borderRadius: 9, padding: "9px 11px", fontSize: 12.5, color: "#C7CEDB" }}>
      {value}
    </div>
  );
}
function Dropdown({ value, setValue, options }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ position: "relative" }}>
      <div onClick={() => setOpen((v) => !v)} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", cursor: "pointer", background: "#0B121F", border: "1px solid #1C2638", borderRadius: 9, padding: "9px 11px", fontSize: 12.5, color: "#C7CEDB" }}>
        {value} <ChevronDown size={13} />
      </div>
      {open && (
        <div style={{ position: "absolute", top: 38, left: 0, right: 0, background: "#0D1420", border: "1px solid #1C2638", borderRadius: 9, zIndex: 20, overflow: "hidden" }}>
          {options.map((o) => (
            <div key={o} onClick={() => { setValue(o); setOpen(false); }} style={{ padding: "8px 11px", fontSize: 12.5, color: o === value ? "#22D3EE" : "#C7CEDB", cursor: "pointer" }}>{o}</div>
          ))}
        </div>
      )}
    </div>
  );
}
function StatRow({ label, value }) {
  return (
    <div style={{ padding: "12px 0", borderBottom: "1px solid #161F30" }}>
      <div style={{ fontSize: 20, fontWeight: 700, fontFamily: "'Space Grotesk', sans-serif", color: "#F2F5FA" }}>{value}</div>
      <div style={{ fontSize: 11.5, color: "#8B94A8" }}>{label}</div>
    </div>
  );
}

/* ------------------ Change Detection page ------------------ */
function SwipeCompare({ height = 260 }) {
  const [pos, setPos] = useState(50);
  const ref = useRef(null);
  const dragging = useRef(false);

  const updateFromClientX = (clientX) => {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const p = Math.min(100, Math.max(0, ((clientX - rect.left) / rect.width) * 100));
    setPos(p);
  };

  return (
    <div
      ref={ref}
      onMouseDown={(e) => { dragging.current = true; updateFromClientX(e.clientX); }}
      onMouseMove={(e) => { if (dragging.current) updateFromClientX(e.clientX); }}
      onMouseUp={() => (dragging.current = false)}
      onMouseLeave={() => (dragging.current = false)}
      onTouchStart={(e) => updateFromClientX(e.touches[0].clientX)}
      onTouchMove={(e) => updateFromClientX(e.touches[0].clientX)}
      style={{ position: "relative", height, borderRadius: 12, overflow: "hidden", border: "1px solid #1C2638", cursor: "ew-resize", userSelect: "none" }}
    >
      {/* AFTER (full width, red change zones) */}
      <div style={{ position: "absolute", inset: 0, background: "linear-gradient(135deg,#0F1A2A,#152436)" }}>
        <svg viewBox="0 0 300 220" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }} preserveAspectRatio="none">
          <polygon points="80,100 130,90 150,130 110,160 70,145" fill="#EF444455" stroke="#EF4444" strokeWidth="1.5" />
          <polygon points="180,60 220,70 210,110 170,105" fill="#EF444455" stroke="#EF4444" strokeWidth="1.5" />
        </svg>
        <div style={{ position: "absolute", top: 10, right: 12 }}><Badge color="#22D3EE" bg="rgba(34,211,238,0.12)">AFTER · 18 Jun 2025</Badge></div>
      </div>
      {/* BEFORE (clipped by slider position) */}
      <div style={{ position: "absolute", inset: 0, width: `${pos}%`, overflow: "hidden", background: "linear-gradient(135deg,#0F1A2A,#152436)", borderRight: "2px solid #22D3EE" }}>
        <div style={{ position: "absolute", top: 10, left: 12 }}><Badge color="#8B94A8" bg="rgba(255,255,255,0.06)">BEFORE · 12 Jun 2024</Badge></div>
      </div>
      {/* handle */}
      <div style={{ position: "absolute", top: "50%", left: `${pos}%`, transform: "translate(-50%,-50%)", width: 30, height: 30, borderRadius: "50%", background: "#22D3EE", display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 0 10px #22D3EE99", pointerEvents: "none" }}>
        <RefreshCw size={14} color="#06121F" />
      </div>
    </div>
  );
}

function ChangeDetectionPage() {
  const [year, setYear] = useState(2025);
  const pct = ((year - 2024) / (2025 - 2024)) * 100;
  return (
    <div>
      <TopBar title="Multi-Temporal Change Detection" subtitle="Compare imagery across two time periods to detect surface change." />
      <Card style={{ padding: 22, marginBottom: 20 }}>
        <div style={{ fontSize: 11.5, color: "#8B94A8", marginBottom: 10 }}>Drag the handle to compare before and after imagery</div>
        <SwipeCompare />

        <div style={{ display: "flex", gap: 14, marginTop: 20, flexWrap: "wrap" }}>
          <StatTile label="Changed Area" value="18.4 km²" />
          <StatTile label="Change" value="+8.2%" accent="#EF4444" />
          <StatTile label="Confidence" value="91%" accent="#22C55E" />
        </div>

        <div style={{ marginTop: 26 }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "#8B94A8", marginBottom: 8 }}>
            <span>2024</span>
            <span style={{ color: "#22D3EE", fontWeight: 700 }}>{year.toFixed(2)}</span>
            <span>2025</span>
          </div>
          <input
            type="range" min="2024" max="2025" step="0.01" value={year}
            onChange={(e) => setYear(parseFloat(e.target.value))}
            style={{ width: "100%", accentColor: "#22D3EE" }}
          />
        </div>
      </Card>

      <Card style={{ padding: 20 }}>
        <SatelliteMap objects={[]} showFlood height={380} live />
      </Card>
    </div>
  );
}

/* ------------------ Results page ------------------ */
function ResultsPage({ push }) {
  const [selectedId, setSelectedId] = useState(null);
  const rows = [
    { obj: "Water Body", count: 12, area: "23.6 km²", conf: "94%" },
    { obj: "Buildings", count: 21, area: "8.4 km²", conf: "91%" },
    { obj: "Roads", count: 10, area: "14.2 km", conf: "89%" },
  ];
  return (
    <div>
      <TopBar title="Analysis Results" subtitle="Detailed output from the most recent spatial analysis run." />
      <div style={{ display: "flex", gap: 14, marginBottom: 20, flexWrap: "wrap" }}>
        <StatTile label="Objects Detected" value="43" />
        <StatTile label="Area Analyzed" value="128.4 km²" />
        <StatTile label="Average Confidence" value="94.2%" accent="#22C55E" />
        <StatTile label="Processing Time" value="18.4 sec" />
      </div>
      <Card style={{ padding: 20, marginBottom: 20 }}>
        <SatelliteMap objects={DETECTED_OBJECTS} selectedId={selectedId} onSelect={setSelectedId} height={380} />
      </Card>
      <Card style={{ padding: 20 }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ textAlign: "left", color: "#8B94A8", fontSize: 11.5, borderBottom: "1px solid #1C2638" }}>
              <th style={{ padding: "8px 6px" }}>Object</th>
              <th style={{ padding: "8px 6px" }}>Count</th>
              <th style={{ padding: "8px 6px" }}>Area</th>
              <th style={{ padding: "8px 6px" }}>Confidence</th>
              <th style={{ padding: "8px 6px" }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.obj} style={{ borderBottom: "1px solid #161F30" }}>
                <td style={{ padding: "10px 6px", color: "#F2F5FA", fontWeight: 600 }}>{r.obj}</td>
                <td style={{ padding: "10px 6px", color: "#C7CEDB" }}>{r.count}</td>
                <td style={{ padding: "10px 6px", color: "#C7CEDB" }}>{r.area}</td>
                <td style={{ padding: "10px 6px", color: "#22C55E" }}>{r.conf}</td>
                <td style={{ padding: "10px 6px" }}>
                  <button onClick={() => push(`Viewing ${r.obj} details`, "info")} style={ghostBtn}>View</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div style={{ display: "flex", gap: 10, marginTop: 18, flexWrap: "wrap" }}>
          <button onClick={() => push("Exported CSV", "success")} style={ghostBtn}><Download size={12} style={{ marginRight: 5 }} />Export CSV</button>
          <button onClick={() => push("Exported GeoJSON", "success")} style={ghostBtn}><Download size={12} style={{ marginRight: 5 }} />Export GeoJSON</button>
          <button onClick={() => push("Generating PDF report…", "info")} style={ghostBtn}><FileBarChart size={12} style={{ marginRight: 5 }} />Generate PDF</button>
          <button onClick={() => push("Share link copied", "success")} style={ghostBtn}><Share2 size={12} style={{ marginRight: 5 }} />Share Analysis</button>
        </div>
      </Card>
    </div>
  );
}

/* ------------------ Analytics page ------------------ */
function AnalyticsPage() {
  return (
    <div>
      <TopBar title="Analytics" subtitle="Aggregate trends across all analyses run on the platform." />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>
        <Card style={{ padding: 20 }}>
          <SectionTitle>Objects Detected Over Time</SectionTitle>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={ANALYTICS_TIME_SERIES}>
              <CartesianGrid stroke="#161F30" vertical={false} />
              <XAxis dataKey="m" stroke="#5A6478" fontSize={11} tickLine={false} axisLine={false} />
              <YAxis stroke="#5A6478" fontSize={11} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={{ background: "#0D1420", border: "1px solid #1C2638", borderRadius: 8, fontSize: 12 }} />
              <Line type="monotone" dataKey="objects" stroke="#22D3EE" strokeWidth={2.5} dot={{ r: 3, fill: "#22D3EE" }} />
            </LineChart>
          </ResponsiveContainer>
        </Card>

        <Card style={{ padding: 20 }}>
          <SectionTitle>Area Analyzed (km²)</SectionTitle>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={ANALYTICS_TIME_SERIES}>
              <defs>
                <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3B82F6" stopOpacity={0.5} />
                  <stop offset="100%" stopColor="#3B82F6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#161F30" vertical={false} />
              <XAxis dataKey="m" stroke="#5A6478" fontSize={11} tickLine={false} axisLine={false} />
              <YAxis stroke="#5A6478" fontSize={11} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={{ background: "#0D1420", border: "1px solid #1C2638", borderRadius: 8, fontSize: 12 }} />
              <Area type="monotone" dataKey="area" stroke="#3B82F6" fill="url(#areaFill)" strokeWidth={2.5} />
            </AreaChart>
          </ResponsiveContainer>
        </Card>

        <Card style={{ padding: 20 }}>
          <SectionTitle>Confidence Distribution</SectionTitle>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={CONFIDENCE_DIST} dataKey="value" nameKey="name" innerRadius={55} outerRadius={80} paddingAngle={3}>
                {CONFIDENCE_DIST.map((d) => <Cell key={d.name} fill={d.color} />)}
              </Pie>
              <Tooltip contentStyle={{ background: "#0D1420", border: "1px solid #1C2638", borderRadius: 8, fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 11.5, color: "#8B94A8" }} />
            </PieChart>
          </ResponsiveContainer>
        </Card>

        <Card style={{ padding: 20 }}>
          <SectionTitle>Analysis Activity (This Week)</SectionTitle>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={ACTIVITY}>
              <CartesianGrid stroke="#161F30" vertical={false} />
              <XAxis dataKey="d" stroke="#5A6478" fontSize={11} tickLine={false} axisLine={false} />
              <YAxis stroke="#5A6478" fontSize={11} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={{ background: "#0D1420", border: "1px solid #1C2638", borderRadius: 8, fontSize: 12 }} />
              <Bar dataKey="n" fill="#8B5CF6" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>
    </div>
  );
}
function SectionTitle({ children }) {
  return <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 13.5, color: "#F2F5FA", marginBottom: 10 }}>{children}</div>;
}

/* ------------------ Projects page ------------------ */
function ProjectsPage() {
  const projects = [
    { name: "Assam Flood Monitoring", updated: "2 hours ago", analyses: 8 },
    { name: "Sundarbans Mangrove Watch", updated: "1 day ago", analyses: 14 },
    { name: "Bengaluru Urban Growth", updated: "3 days ago", analyses: 5 },
    { name: "Punjab Crop Health", updated: "1 week ago", analyses: 22 },
  ];
  return (
    <div>
      <TopBar title="Projects" subtitle="Organize analyses into ongoing monitoring projects." />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 16 }}>
        <Card style={{ padding: 20, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: 130, cursor: "pointer", border: "1px dashed #2A3F63" }}>
          <Plus size={22} color="#5FC5F0" />
          <div style={{ fontSize: 13, color: "#5FC5F0", marginTop: 8, fontWeight: 600 }}>New Project</div>
        </Card>
        {projects.map((p) => (
          <Card key={p.name} style={{ padding: 20 }}>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 14.5, color: "#F2F5FA" }}>{p.name}</div>
            <div style={{ fontSize: 12, color: "#8B94A8", marginTop: 6 }}>Updated {p.updated} · {p.analyses} analyses</div>
            <div style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12, color: "#5FC5F0", marginTop: 12, cursor: "pointer" }}>
              Open project <ArrowRight size={13} />
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

/* ------------------ Reports page ------------------ */
function ReportsPage({ push }) {
  const [generating, setGenerating] = useState(false);
  return (
    <div>
      <TopBar title="Intelligence Reports" subtitle="Generate and manage exportable analysis reports." />
      <Card style={{ padding: 20, marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontSize: 13, color: "#8B94A8" }}>Compile the latest analysis into a shareable intelligence report.</div>
          <button
            onClick={() => { setGenerating(true); push("Generating report…", "info"); setTimeout(() => { setGenerating(false); push("Report generated successfully", "success"); }, 1600); }}
            style={{
              display: "flex", alignItems: "center", gap: 8, background: "linear-gradient(135deg,#3B82F6,#22D3EE)",
              border: "none", color: "#06121F", fontWeight: 700, fontSize: 13, padding: "10px 18px", borderRadius: 10, cursor: "pointer"
            }}>
            {generating ? <RefreshCw size={14} className="satq-spin" /> : <FileText size={14} />}
            {generating ? "Generating…" : "Generate New Report"}
          </button>
        </div>
      </Card>

      <Card style={{ padding: 0, overflow: "hidden", marginBottom: 20 }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ textAlign: "left", color: "#8B94A8", fontSize: 11.5, background: "rgba(255,255,255,0.02)" }}>
              <th style={{ padding: "12px 16px" }}>Report Name</th>
              <th style={{ padding: "12px 16px" }}>Location</th>
              <th style={{ padding: "12px 16px" }}>Date</th>
              <th style={{ padding: "12px 16px" }}>Type</th>
              <th style={{ padding: "12px 16px" }}>Status</th>
            </tr>
          </thead>
          <tbody>
            {REPORTS.map((r) => (
              <tr key={r.name} style={{ borderTop: "1px solid #161F30", cursor: "pointer" }} onClick={() => push(`Opening "${r.name}"`, "info")}>
                <td style={{ padding: "12px 16px", color: "#F2F5FA", fontWeight: 600 }}>{r.name}</td>
                <td style={{ padding: "12px 16px", color: "#C7CEDB" }}>{r.location}</td>
                <td style={{ padding: "12px 16px", color: "#C7CEDB" }}>{r.date}</td>
                <td style={{ padding: "12px 16px", color: "#C7CEDB" }}>{r.type}</td>
                <td style={{ padding: "12px 16px" }}>
                  <Badge color={r.status === "Complete" ? "#22C55E" : "#F59E0B"} bg={r.status === "Complete" ? "rgba(34,197,94,0.1)" : "rgba(245,158,11,0.1)"}>{r.status}</Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card style={{ padding: 22 }}>
        <SectionTitle>Report Preview — Assam Flood Assessment</SectionTitle>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginTop: 10 }}>
          {["Executive Summary", "Study Area", "Satellite Data", "Methodology", "Detected Features", "Change Analysis", "Statistics", "Maps", "Confidence", "Limitations"].map((s) => (
            <div key={s} style={{ fontSize: 12.5, color: "#C7CEDB", background: "rgba(255,255,255,0.02)", border: "1px solid #1C2638", borderRadius: 9, padding: "10px 12px" }}>
              {s}
            </div>
          ))}
        </div>
        <div style={{ display: "flex", gap: 10, marginTop: 18 }}>
          <button onClick={() => push("Downloading PDF…", "success")} style={ghostBtn}><Download size={12} style={{ marginRight: 5 }} />PDF</button>
          <button onClick={() => push("Downloading CSV…", "success")} style={ghostBtn}><Download size={12} style={{ marginRight: 5 }} />CSV</button>
          <button onClick={() => push("Downloading GeoJSON…", "success")} style={ghostBtn}><Download size={12} style={{ marginRight: 5 }} />GeoJSON</button>
        </div>
      </Card>
    </div>
  );
}

/* ------------------ Root App ------------------ */
export default function App() {
  const [page, setPage] = useState("dashboard");
  const [collapsed, setCollapsed] = useState(false);
  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [analysisState, setAnalysisState] = useState("idle"); // idle | processing | complete
  const [selectedId, setSelectedId] = useState(null);
  const { toasts, push } = useToasts();

  const runAnalysis = () => {
    if (!query.trim()) { push("Enter a query first", "warn"); return; }
    setAnalysisState("processing");
  };

  return (
    <div style={{
      display: "flex", minHeight: "100vh", background: "#070B14",
      fontFamily: "'Inter', -apple-system, sans-serif", color: "#E5E9F0"
    }}>
      <style>{`
        @keyframes satq-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes satq-slide-in { from { opacity:0; transform: translateY(6px);} to {opacity:1; transform:none;} }
        @keyframes satq-scan { from { left: -20%; } to { left: 105%; } }
        .satq-spin { animation: satq-spin 0.9s linear infinite; }
        input[type=range] { height: 4px; border-radius: 4px; background: #1C2638; }
        table th, table td { white-space: nowrap; }
      `}</style>

      <Sidebar page={page} setPage={setPage} collapsed={collapsed} setCollapsed={setCollapsed} />

      <div style={{ flex: 1, padding: "26px 32px", minWidth: 0 }}>
        {page === "dashboard" && (
          <DashboardPage query={query} setQuery={setQuery} analysisState={analysisState}
            runAnalysis={runAnalysis} selectedId={selectedId} setSelectedId={setSelectedId} push={push} />
        )}
        {page === "query" && (
          <div>
            <TopBar title="Query Assistant" subtitle="Have a focused conversation with your satellite data." />
            <div style={{ display: "grid", gridTemplateColumns: "1.6fr 1fr", gap: 20 }}>
              <QueryPanel query={query} setQuery={setQuery} onAnalyze={runAnalysis} />
              <AnalysisPanel complete={analysisState === "complete"} selectedId={selectedId} setSelectedId={setSelectedId} push={push} />
            </div>
          </div>
        )}
        {page === "imagery" && <ImageryPage />}
        {page === "map" && <AnalysisMapPage push={push} />}
        {page === "change" && <ChangeDetectionPage />}
        {page === "analytics" && <AnalyticsPage />}
        {page === "projects" && <ProjectsPage />}
        {page === "reports" && <ReportsPage push={push} />}
      </div>

      {analysisState === "processing" && (
        <ProcessingModal onDone={() => { setAnalysisState("complete"); push("Analysis complete", "success"); }} />
      )}
      <ToastStack toasts={toasts} />
    </div>
  );
}