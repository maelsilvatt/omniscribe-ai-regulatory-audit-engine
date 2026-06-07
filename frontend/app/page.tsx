'use client';

import { useState, useRef, DragEvent, ChangeEvent, useEffect } from 'react';

// --- CONSTANTS ---
// Design Decision: Centralized URLs allow seamless environment switching without hunting for hardcoded strings.
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const WS_BASE_URL = API_BASE_URL.replace(/^http/, 'ws');

// --- INTERFACES ---
interface Finding {
  id: string;
  doc_clause_reference: string;
  regulation_violated: string;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  finding_description: string;
  remediation_steps: string;
}

interface AuditReport {
  document_id: string;
  frameworks_evaluated: string[];
  audited_at: string;
  summary: {
    total_issues: number;
    critical_risk_count: number;
    high_risk_count: number;
    medium_risk_count: number;
    low_risk_count: number;
    compliance_score: number;
  };
  findings: Finding[];
}

interface HistoryItem {
  session_id: string;
  document_id: string;
  frameworks_evaluated: string[];
  audited_at: string;
  compliance_score: number;
  total_issues: number;
}

type TabState = 'workspace' | 'history';

export default function AdministrativeDashboard() {
  // --- STATE MANAGEMENT ---
  const [activeTab, setActiveTab] = useState<TabState>('workspace');
  
  // Workspace State
  const [isLoading, setIsLoading] = useState(false);
  const [currentAgent, setCurrentAgent] = useState('');
  const [logs, setLogs] = useState<string[]>([]);
  const [auditReport, setAuditReport] = useState<AuditReport | null>(null);
  
  // File & Configuration State
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [targetFramework, setTargetFramework] = useState<string>('CDC');
  const [isDragging, setIsDragging] = useState(false);

  // History State
  const [auditHistory, setAuditHistory] = useState<HistoryItem[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);

  // --- REFS ---
  const wsRef = useRef<WebSocket | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // --- LIFECYCLE EFFECTS ---
  
  // Fetch history only when the user navigates to the history tab to save bandwidth
  useEffect(() => {
    if (activeTab === 'history') {
      fetchAuditHistory();
    }
  }, [activeTab]);

  // Design Decision: Always clean up active WebSockets on unmount to prevent memory 
  // leaks and rogue background connections if the user navigates away from the dashboard.
  useEffect(() => {
    return () => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.close();
      }
    };
  }, []);

  // --- API CALLS ---

  const fetchAuditHistory = async () => {
    setIsLoadingHistory(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/audit/history`);
      if (response.ok) {
        const data = await response.json();
        setAuditHistory(data);
      } else {
        console.error('Failed to fetch history:', response.statusText);
      }
    } catch (error) {
      console.error('Network error fetching history:', error);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  const fetchHistoricalReport = async (sessionId: string) => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/audit/report/${sessionId}`);
      if (!response.ok) throw new Error('Report not found in the database.');
      
      const data = await response.json();
      setAuditReport(data);
      setActiveTab('workspace'); // Redirect user back to workspace to view the report
    } catch (error) {
      alert('Error loading historical report.');
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  // --- EVENT HANDLERS ---

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      const file = files[0];
      if (file.type === 'application/pdf') {
        setSelectedFile(file);
      } else {
        alert('Unsupported format. Please select a PDF file.');
      }
    }
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      setSelectedFile(files[0]);
    }
  };

  const triggerFileSelect = () => {
    fileInputRef.current?.click();
  };

  const initiateAuditStream = async () => {
    if (!selectedFile) return;

    setIsLoading(true);
    setLogs([]);
    setAuditReport(null);

    try {
      // Normalize document ID: remove extension and uppercase for consistency
      const documentId = selectedFile.name.replace(/\.pdf$/i, '').toUpperCase();

      // Design Decision: Using FormData to securely transmit the binary PDF payload
      // alongside the metadata in a single multipart/form-data request.
      const formData = new FormData();
      formData.append('document_id', documentId);
      formData.append('regulatory_frameworks', targetFramework);
      formData.append('strictness_level', 'high');
      formData.append('file', selectedFile);

      const response = await fetch(`${API_BASE_URL}/api/v1/audit/initiate`, {
        method: 'POST',        
        body: formData 
      });

      if (!response.ok) throw new Error('Failed to communicate with the agent ecosystem.');
      
      const data = await response.json();
      const sessionId = data.session_id;

      // Initialize real-time WebSocket connection for agent logs
      wsRef.current = new WebSocket(`${WS_BASE_URL}/api/v1/audit/stream/${sessionId}`);

      wsRef.current.onmessage = (event) => {
        const message = JSON.parse(event.data);
        switch (message.event) {
          case 'session_connected':
            setLogs((prev) => [...prev, `[SYSTEM] ${message.message}`]);
            break;
          case 'agent_execution_step':
            setCurrentAgent(message.agent);
            setLogs((prev) => [...prev, `[${message.agent}] ${message.message}`]);
            break;
          case 'audit_completed':
            setAuditReport(message.payload);
            setIsLoading(false);
            wsRef.current?.close();
            break;
          case 'error':
            setLogs((prev) => [...prev, `[ERROR] ${message.message}`]);
            setIsLoading(false);
            break;
        }
      };

      // Robustness: Handle unexpected socket closures
      wsRef.current.onerror = () => {
        setLogs((prev) => [...prev, `[ERROR] WebSocket connection failed unexpectedly.`]);
        setIsLoading(false);
      };

    } catch (error) {
      console.error(error);
      setIsLoading(false);
    }
  };

  // --- RENDER HELPERS ---
  
  const getRiskBadgeStyles = (level: string) => {
    switch (level) {
      case 'CRITICAL': return 'bg-rose-50 text-rose-700 border border-rose-100';
      case 'HIGH': return 'bg-amber-50 text-amber-700 border border-amber-100';
      default: return 'bg-zinc-100 text-zinc-600 border border-zinc-200';
    }
  };

  return (
    <div className="flex min-h-screen bg-zinc-50 text-zinc-800 font-sans antialiased">
      
      {/* SIDEBAR */}
      <aside className="w-64 border-r border-zinc-200 bg-white flex flex-col justify-between p-5 shrink-0 hidden md:flex">
        <div className="space-y-6">
          <div className="flex items-center gap-2 px-2">
            <svg className="w-6 h-6 text-orange-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span className="text-lg font-bold tracking-tight text-zinc-900">
              OmniScribe <span className="text-orange-500">AI</span>
            </span>
          </div>
          
          <nav className="space-y-1">
            <button 
              onClick={() => setActiveTab('workspace')}
              className={`w-full flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-lg transition border ${
                activeTab === 'workspace' 
                  ? 'bg-orange-50 text-orange-700 border-orange-100/50' 
                  : 'text-zinc-600 border-transparent hover:text-zinc-900 hover:bg-zinc-100'
              }`}
            >
              <span className={`h-1.5 w-1.5 rounded-full ${activeTab === 'workspace' ? 'bg-orange-500' : 'bg-transparent'}`} /> 
              Workspace
            </button>
            <button 
              onClick={() => { setActiveTab('history'); setAuditReport(null); }}
              className={`w-full flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-lg transition border ${
                activeTab === 'history' 
                  ? 'bg-orange-50 text-orange-700 border-orange-100/50' 
                  : 'text-zinc-600 border-transparent hover:text-zinc-900 hover:bg-zinc-100'
              }`}
            >
              <span className={`h-1.5 w-1.5 rounded-full ${activeTab === 'history' ? 'bg-orange-500' : 'bg-transparent'}`} />
              Global History
            </button>
            <a href="#" className="flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-lg text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100 transition">
              Indexed Laws
            </a>
          </nav>
        </div>
        <div className="border-t border-zinc-200 pt-4 px-2 text-xs text-zinc-500 font-sans tracking-tight">
          Omniscribe AI - 2026, Rio de Janeiro
        </div>
      </aside>

      {/* MAIN CONTENT AREA */}
      <main className="flex-1 flex flex-col overflow-x-hidden">
        
        <header className="h-14 border-b border-zinc-200 bg-white/80 backdrop-blur flex items-center justify-between px-8 sticky top-0 z-40">
          <div className="flex items-center gap-2 text-xs font-mono text-zinc-500">
            <span>Workspace</span> <span className="text-zinc-300">/</span> 
            <span className="text-zinc-700 font-medium uppercase tracking-wider text-[10px]">
              {activeTab === 'workspace' ? 'Compliance Engine' : 'Consolidated History'}
            </span>
          </div>
        </header>

        <div className="p-8 space-y-6 flex-1 max-w-7xl w-full mx-auto">
          
          {/* --- WORKSPACE TAB --- */}
          {activeTab === 'workspace' && (
            <>
              <div>
                <h2 className="text-2xl font-bold tracking-tight text-zinc-900">Audit Dashboard</h2>
                <p className="text-zinc-500 text-xs mt-0.5">Upload a contract to initiate automated regulatory scanning.</p>
              </div>

              {!isLoading && !auditReport && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-start">
                  
                  {/* Dropzone */}
                  <div 
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    className={`md:col-span-2 border-2 border-dashed rounded-xl p-12 flex flex-col items-center justify-center text-center transition min-h-[320px] ${
                      isDragging 
                        ? 'border-orange-500 bg-orange-50/50' 
                        : selectedFile 
                          ? 'border-zinc-300 bg-zinc-100/50' 
                          : 'border-zinc-200 bg-white hover:border-zinc-300'
                    }`}
                  >
                    <input type="file" ref={fileInputRef} onChange={handleFileChange} accept=".pdf" className="hidden" />
                    
                    <div className="p-4 bg-zinc-50 rounded-full border border-zinc-100 text-zinc-400 mb-4 shadow-sm">
                      <svg className={`w-8 h-8 transition-transform ${isDragging ? 'scale-110 text-orange-500' : 'text-zinc-400'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                      </svg>
                    </div>

                    {selectedFile ? (
                      <div className="space-y-2">
                        <h3 className="text-sm font-semibold text-zinc-800">Document Loaded</h3>
                        <p className="text-xs font-mono text-orange-600 bg-orange-50 border border-orange-100 px-3 py-1.5 rounded-lg max-w-sm mx-auto truncate">
                          {selectedFile.name}
                        </p>
                        <button onClick={triggerFileSelect} className="text-[11px] text-zinc-400 hover:text-zinc-600 underline underline-offset-2 block mx-auto pt-2">
                          Replace file
                        </button>
                      </div>
                    ) : (
                      <div>
                        <h3 className="text-sm font-semibold text-zinc-700">Drag and drop the contract here</h3>
                        <p className="text-xs text-zinc-400 mt-1 mb-4">Only PDF files are supported.</p>
                        <button onClick={triggerFileSelect} className="bg-white hover:bg-zinc-50 border border-zinc-200 text-zinc-700 text-xs font-medium px-4 py-2 rounded-lg transition shadow-sm">
                          Select PDF File
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Configuration Panel */}
                  <div className="border border-zinc-200 bg-white rounded-xl p-5 space-y-5 shadow-sm">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-400 border-b border-zinc-100 pb-2">Scan Parameters</h4>
                    
                    <div className="space-y-2">
                      <label className="text-[11px] font-sans font-semibold text-zinc-500 uppercase tracking-wider block">Target Regulation</label>
                      <select 
                        value={targetFramework} 
                        onChange={(e) => setTargetFramework(e.target.value)} 
                        className="w-full bg-zinc-50 border border-zinc-200 rounded-lg p-2.5 text-xs text-zinc-700 font-medium focus:outline-none focus:border-orange-500 transition"
                      >
                        <option value="CDC">Consumer Defense Code (CDC)</option>
                        <option value="LGPD">General Data Protection Law (LGPD)</option>
                      </select>
                    </div>

                    <div className="space-y-2.5 border-t border-zinc-100 pt-3">
                      <label className="text-[11px] font-sans font-semibold text-zinc-500 uppercase tracking-wider block">Analysis Strictness</label>
                      <div className="grid grid-cols-3 gap-1 bg-zinc-100 p-0.5 rounded-lg text-[11px] font-medium text-zinc-600">
                        <button type="button" className="py-1.5 rounded-md text-center hover:bg-white/60 transition">Low</button>
                        <button type="button" className="py-1.5 rounded-md text-center hover:bg-white/60 transition">Medium</button>
                        <button type="button" className="py-1.5 rounded-md text-center bg-white text-orange-600 shadow-sm font-semibold">High</button>
                      </div>
                      <div className="flex justify-between items-center text-[11px] font-sans text-zinc-400 pt-1.5">
                        <span>Engine:</span> <span className="text-zinc-600 font-medium">Omniscribe Multi-agent AI</span>
                      </div>
                    </div>

                    <button 
                      onClick={initiateAuditStream} 
                      disabled={!selectedFile} 
                      className={`w-full text-xs font-semibold py-2.5 rounded-lg transition shadow-sm text-center ${
                        selectedFile 
                          ? 'bg-orange-500 text-white hover:bg-orange-600 active:scale-98 cursor-pointer' 
                          : 'bg-zinc-100 text-zinc-300 cursor-not-allowed border border-zinc-200/50'
                      }`}
                    >
                      Analyze Contract
                    </button>
                  </div>
                </div>
              )}

              {/* Streaming Output & Results Panel */}
              {(isLoading || auditReport) && (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
                  
                  {/* Left Column: Report / Loading Indicator */}
                  <div className="lg:col-span-2 space-y-6">
                    {auditReport && (
                      <div className="grid grid-cols-3 gap-4">
                        <div className="border border-zinc-200 bg-white rounded-xl p-4 flex flex-col justify-between shadow-sm">
                          <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">Global Score</span>
                          <span className={`text-3xl font-black mt-2 ${auditReport.summary.compliance_score > 50 ? 'text-emerald-600' : 'text-rose-600'}`}>
                            {auditReport.summary.compliance_score.toFixed(1)}
                          </span>
                        </div>
                        <div className="border border-zinc-200 bg-white rounded-xl p-4 flex flex-col justify-between shadow-sm">
                          <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">Total Issues</span>
                          <span className="text-3xl font-black mt-2 text-zinc-800">{auditReport.summary.total_issues}</span>
                        </div>
                        <div className="border border-zinc-200 bg-white rounded-xl p-4 flex flex-col justify-between shadow-sm">
                          <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">High Severity</span>
                          <span className="text-3xl font-black mt-2 text-amber-600">
                            {auditReport.summary.critical_risk_count + auditReport.summary.high_risk_count}
                          </span>
                        </div>
                      </div>
                    )}

                    {auditReport && (
                      <div className="border border-zinc-200 rounded-xl bg-white overflow-hidden shadow-sm">
                        <div className="px-5 py-4 border-b border-zinc-200 bg-zinc-50 flex justify-between items-center">
                          <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-500">Non-Compliance Log</h3>
                          <span className="text-[10px] font-mono text-zinc-400">Filter: {auditReport.frameworks_evaluated[0]} Active</span>
                        </div>
                        <div className="divide-y divide-zinc-100">
                          {auditReport.findings.map((finding) => (
                            <div key={finding.id} className="p-5 space-y-3 hover:bg-zinc-50/50 transition group">
                              <div className="flex justify-between items-center gap-4">
                                <div className="space-y-0.5">
                                  <div className="flex items-center gap-2">
                                    <span className="text-xs font-mono font-bold bg-zinc-100 px-1.5 py-0.5 border border-zinc-200 rounded text-zinc-500">
                                      {finding.id}
                                    </span>
                                    <span className="text-sm font-semibold text-zinc-800">{finding.doc_clause_reference}</span>
                                  </div>
                                  <span className="text-xs text-orange-600/90 font-mono block">{finding.regulation_violated}</span>
                                </div>
                                <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-bold tracking-wider ${getRiskBadgeStyles(finding.risk_level)}`}>
                                  {finding.risk_level}
                                </span>
                              </div>
                              <p className="text-xs text-zinc-600 leading-relaxed">{finding.finding_description}</p>
                              <div className="text-xs bg-zinc-50 p-3 rounded border border-zinc-100 font-mono text-zinc-700">
                                <span className="font-bold text-zinc-400 text-[10px] block uppercase tracking-wider mb-1">Mitigation Action</span>
                                {finding.remediation_steps}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {isLoading && (
                      <div className="border border-zinc-200 bg-white rounded-xl p-12 text-center text-xs text-zinc-400 font-mono flex flex-col items-center justify-center space-y-3 shadow-sm">
                        <div className="w-4 h-4 border-2 border-zinc-200 border-t-orange-500 rounded-full animate-spin" />
                        <span>Awaiting GovernanceAgent structuring...</span>
                      </div>
                    )}
                  </div>

                  {/* Right Column: Metadata & Console */}
                  <div className="space-y-6">
                    <div className="border border-zinc-200 bg-white rounded-xl p-5 space-y-4 shadow-sm">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-400 border-b border-zinc-100 pb-2">Target Metadata</h4>
                      <div className="space-y-2.5 text-xs font-mono">
                        <div className="flex justify-between">
                          <span className="text-zinc-400">Document:</span> 
                          <span className="text-zinc-700 font-medium truncate max-w-[120px]">
                            {selectedFile?.name || auditReport?.document_id}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-400">Framework:</span> 
                          <span className="text-orange-600 font-bold">{targetFramework}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-400">Mode:</span> 
                          <span className="text-zinc-700">Omniscribe AI</span>
                        </div>
                      </div>
                    </div>

                    <div className="border border-zinc-200 bg-zinc-900 rounded-xl overflow-hidden flex flex-col h-72 shadow-md">
                      <div className="px-4 py-2.5 border-b border-zinc-800 bg-zinc-950 flex items-center justify-between font-mono text-[11px] text-zinc-400">
                        <span>Event Console</span>
                        {isLoading && <span className="text-orange-400 animate-pulse">● running</span>}
                      </div>
                      <div className="p-4 flex-1 overflow-y-auto font-mono text-[11px] text-zinc-400 space-y-2 bg-zinc-900">
                        {logs.map((log, i) => {
                          let colorClass = "text-zinc-300";
                          if (log.includes("[ERROR]")) colorClass = "text-rose-400";
                          if (log.includes("[SYSTEM]")) colorClass = "text-emerald-400";
                          return <div key={i} className={`${colorClass} leading-normal border-b border-zinc-800/50 pb-1`}>{log}</div>;
                        })}
                        {isLoading && (
                          <div className="text-orange-400/90 animate-pulse flex items-center gap-1.5 pt-1">
                            <span>▶ {currentAgent || 'Engine'} processing block</span>
                            <span className="inline-block w-1 h-3 bg-orange-500" />
                          </div>
                        )}
                      </div>
                    </div>

                    {auditReport && (
                      <button 
                        onClick={() => { setAuditReport(null); setSelectedFile(null); }} 
                        className="w-full bg-white hover:bg-zinc-50 text-zinc-500 border border-zinc-200 text-xs font-mono py-2 rounded-lg transition shadow-sm"
                      >
                        New Scan
                      </button>
                    )}
                  </div>
                </div>
              )}
            </>
          )}

          {/* --- HISTORY TAB --- */}
          {activeTab === 'history' && (
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-bold tracking-tight text-zinc-900">Consolidated History</h2>
                <p className="text-zinc-500 text-xs mt-0.5">Consult previously executed regulatory audits stored locally.</p>
              </div>

              <div className="bg-white border border-zinc-200 rounded-xl overflow-hidden shadow-sm">
                {isLoadingHistory ? (
                  <div className="p-12 text-center text-xs text-zinc-400 font-mono flex flex-col items-center justify-center space-y-3">
                    <div className="w-4 h-4 border-2 border-zinc-200 border-t-orange-500 rounded-full animate-spin" />
                    <span>Reading records from the relational database...</span>
                  </div>
                ) : auditHistory.length === 0 ? (
                  <div className="p-12 text-center text-xs text-zinc-400 font-sans">
                    No audits found in the local data history.
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="bg-zinc-50 border-b border-zinc-200 text-[11px] font-sans font-semibold text-zinc-500 uppercase tracking-wider">
                          <th className="py-3 px-6">Session ID</th>
                          <th className="py-3 px-6">Contract Identifier</th>
                          <th className="py-3 px-6">Target Regulation</th>
                          <th className="py-3 px-6 text-center">Global Score</th>
                          <th className="py-3 px-6 text-center">Issues</th>
                          <th className="py-3 px-6">Audit Date</th>
                          <th className="py-3 px-6 text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-zinc-200 text-xs font-sans text-zinc-700">
                        {auditHistory.map((item) => (
                          <tr key={item.session_id} className="hover:bg-zinc-50/70 transition">
                            <td className="py-3.5 px-6 font-mono text-zinc-400 text-[11px]">#{item.session_id}</td>
                            <td className="py-3.5 px-6 font-medium text-zinc-900 max-w-[200px] truncate">{item.document_id}</td>
                            <td className="py-3.5 px-6">
                              <span className="bg-orange-50 border border-orange-100 text-orange-700 font-semibold text-[10px] px-2 py-0.5 rounded">
                                {Array.isArray(item.frameworks_evaluated) 
                                  ? item.frameworks_evaluated.join(', ') 
                                  : item.frameworks_evaluated}
                              </span>
                            </td>
                            <td className="py-3.5 px-6 text-center">
                              <span className={`font-bold text-sm ${item.compliance_score > 50 ? 'text-emerald-600' : 'text-rose-600'}`}>
                                {item.compliance_score.toFixed(1)}
                              </span>
                            </td>
                            <td className="py-3.5 px-6 text-center font-medium">{item.total_issues}</td>
                            <td className="py-3.5 px-6 text-zinc-500">
                              {new Date(item.audited_at).toLocaleString('en-US')}
                            </td>
                            <td className="py-3.5 px-6 text-right">
                              <button 
                                onClick={() => fetchHistoricalReport(item.session_id)}
                                className="bg-white hover:bg-zinc-50 text-zinc-700 border border-zinc-200 font-medium text-[11px] px-3 py-1.5 rounded-lg shadow-sm transition"
                              >
                                View
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}

        </div>
      </main>
    </div>
  );
}