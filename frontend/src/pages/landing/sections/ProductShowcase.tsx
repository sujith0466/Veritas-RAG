import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { LayoutDashboard, MessageSquare, Database, LineChart, CheckCircle2, ChevronRight, FileText, Search, ShieldAlert, Cpu, Activity, Clock, ShieldCheck, Folder, FolderOpen, MoreVertical, FileDown } from 'lucide-react'
import { SectionHeading } from '@/components/landing/SectionHeading'
import { FadeUp } from '@/components/motion/FadeUp'
import { cn } from '@/utils/cn'

const TABS = [
  { id: 'dashboard', label: 'Platform Dashboard', icon: LayoutDashboard },
  { id: 'chat', label: 'Explainable AI Chat', icon: MessageSquare },
  { id: 'kb', label: 'Knowledge Base', icon: Database },
  { id: 'analytics', label: 'Reliability Analytics', icon: LineChart },
]

function DashboardMockup() {
  return (
    <div className="w-full h-full flex bg-surface/50 text-foreground overflow-hidden">
      {/* Sidebar */}
      <div className="w-48 border-r border-border/50 bg-background/50 p-4 flex flex-col space-y-4">
        <div className="h-6 w-24 bg-border/50 rounded animate-pulse" />
        <div className="space-y-2 mt-4">
          {[...Array(5)].map((_, i) => (
            <div key={i} className={cn("h-8 rounded flex items-center px-2", i === 0 ? "bg-primary/10 text-primary" : "text-muted-foreground")} >
              <div className={cn("w-4 h-4 rounded mr-2", i === 0 ? "bg-primary/50" : "bg-border")} />
              <div className="h-2 w-16 bg-current opacity-40 rounded" />
            </div>
          ))}
        </div>
      </div>
      {/* Content */}
      <div className="flex-1 p-6 flex flex-col space-y-6">
        <div className="flex justify-between items-center">
          <h4 className="font-semibold text-lg">System Overview</h4>
          <div className="flex items-center space-x-2 text-xs font-medium text-success bg-success/10 px-2 py-1 rounded-full">
            <Activity className="w-3 h-3" />
            <span>All Systems Operational</span>
          </div>
        </div>

        {/* KPIs */}
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: 'Active Documents', val: '12,403', trend: '+14%', icon: FileText, color: 'text-blue-500' },
            { label: 'Avg Pipeline Latency', val: '1.2s', trend: '-200ms', icon: Clock, color: 'text-amber-500' },
            { label: 'Grounding Accuracy', val: '99.8%', trend: '+0.2%', icon: ShieldCheck, color: 'text-success' },
          ].map((kpi, i) => (
            <div key={i} className="p-4 rounded-xl border border-border/40 bg-background shadow-sm">
              <div className="flex justify-between items-start mb-2">
                <kpi.icon className={`w-5 h-5 ${kpi.color} opacity-80`} />
                <span className="text-[10px] font-bold text-success bg-success/10 px-1.5 py-0.5 rounded">{kpi.trend}</span>
              </div>
              <div className="text-2xl font-bold">{kpi.val}</div>
              <div className="text-xs text-muted-foreground">{kpi.label}</div>
            </div>
          ))}
        </div>

        {/* Processing Queue */}
        <div className="flex-1 rounded-xl border border-border/40 bg-background overflow-hidden flex flex-col">
          <div className="px-4 py-3 border-b border-border/40 text-sm font-medium flex justify-between">
            <span>Live Ingestion Queue</span>
            <span className="text-xs text-muted-foreground">3 items processing</span>
          </div>
          <div className="p-4 space-y-3">
            {[
              { file: 'Q3_Financial_Report.pdf', step: 'Chunking & Embedding', progress: 65, status: 'Processing' },
              { file: 'Enterprise_Architecture_v2.docx', step: 'OCR Extraction', progress: 30, status: 'Processing' },
              { file: 'Security_Audit_2026.md', step: 'Vector Sync', progress: 95, status: 'Finalizing' }
            ].map((task, i) => (
              <div key={i} className="flex flex-col space-y-1.5">
                <div className="flex justify-between text-xs">
                  <span className="font-medium flex items-center"><FileText className="w-3 h-3 mr-1 text-muted-foreground"/> {task.file}</span>
                  <span className="text-muted-foreground">{task.step} • {task.progress}%</span>
                </div>
                <div className="h-1.5 w-full bg-surface rounded-full overflow-hidden">
                  <div className="h-full bg-primary" style={{ width: `${task.progress}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function ChatMockup() {
  return (
    <div className="w-full h-full flex bg-background text-foreground overflow-hidden">
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col border-r border-border/50">
        <div className="h-12 border-b border-border/50 px-4 flex items-center justify-between shadow-sm">
          <span className="font-medium text-sm">Enterprise Assistant</span>
          <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded-full font-medium">Model: GPT-4o</span>
        </div>

        <div className="flex-1 p-6 space-y-6 overflow-hidden flex flex-col justify-end">
          {/* User Message */}
          <div className="flex justify-end">
            <div className="bg-surface border border-border/40 px-4 py-3 rounded-2xl rounded-tr-sm max-w-[80%] shadow-sm">
              <p className="text-sm">What are our current SLA guarantees for the premium enterprise tier, and are there any recent addendums?</p>
            </div>
          </div>

          {/* AI Response */}
          <div className="flex justify-start">
            <div className="bg-primary/5 border border-primary/20 px-4 py-3 rounded-2xl rounded-tl-sm max-w-[90%] shadow-sm relative group">
              <p className="text-sm leading-relaxed mb-3">
                According to the latest <span className="bg-primary/20 text-primary px-1 rounded text-xs cursor-pointer">Enterprise_SLA_v3.pdf [1]</span>, the premium tier guarantees <strong>99.99% uptime</strong> for the RAG infrastructure.
              </p>
              <p className="text-sm leading-relaxed">
                A recent addendum added in March 2026 specifies that vector synchronization delays exceeding 5 minutes will now trigger SLA credits <span className="bg-primary/20 text-primary px-1 rounded text-xs cursor-pointer">Policy_Addendum.md [2]</span>.
              </p>

              <div className="mt-3 flex gap-2">
                <span className="inline-flex items-center text-[10px] bg-background border border-border/60 px-2 py-1 rounded shadow-sm hover:border-primary/50 cursor-pointer">
                  <CheckCircle2 className="w-3 h-3 text-success mr-1"/> High Confidence (98%)
                </span>
                <span className="inline-flex items-center text-[10px] bg-background border border-border/60 px-2 py-1 rounded shadow-sm">
                  <Cpu className="w-3 h-3 text-muted-foreground mr-1"/> 842ms
                </span>
              </div>
            </div>
          </div>

          {/* Follow up */}
          <div className="flex gap-2">
            <span className="text-xs border border-primary/30 text-primary px-3 py-1.5 rounded-full cursor-pointer hover:bg-primary/10 transition-colors">How do customers claim credits?</span>
            <span className="text-xs border border-border text-muted-foreground px-3 py-1.5 rounded-full cursor-pointer hover:bg-surface transition-colors">Show me the addendum</span>
          </div>
        </div>

        <div className="p-4 border-t border-border/50 bg-surface/30">
          <div className="h-10 bg-background border border-border rounded-lg flex items-center px-3 shadow-inner">
            <span className="text-sm text-muted-foreground/50">Ask a question...</span>
          </div>
        </div>
      </div>

      {/* Reasoning Panel */}
      <div className="w-64 bg-surface/30 p-4 flex flex-col space-y-4">
        <h5 className="text-xs font-semibold uppercase text-muted-foreground tracking-wider mb-2">Retrieval Reasoning</h5>

        <div className="space-y-3">
          <div className="bg-background border border-border/40 p-3 rounded-lg shadow-sm">
            <div className="text-[10px] text-muted-foreground mb-1 uppercase font-semibold">Semantic Match</div>
            <div className="text-xs font-medium">Enterprise_SLA_v3.pdf</div>
            <div className="mt-1 h-1 w-full bg-surface rounded-full"><div className="h-full bg-primary w-[94%]" /></div>
          </div>

          <div className="bg-background border border-border/40 p-3 rounded-lg shadow-sm">
            <div className="text-[10px] text-muted-foreground mb-1 uppercase font-semibold">BM25 Exact Match</div>
            <div className="text-xs font-medium">Policy_Addendum.md</div>
            <div className="mt-1 h-1 w-full bg-surface rounded-full"><div className="h-full bg-primary w-[88%]" /></div>
          </div>
        </div>

        <div className="mt-auto p-3 bg-primary/10 border border-primary/20 rounded-lg">
          <div className="flex items-start">
            <ShieldCheck className="w-4 h-4 text-primary mt-0.5 mr-2" />
            <p className="text-[10px] text-primary/90">Output verified against known source documents. No hallucination detected.</p>
          </div>
        </div>
      </div>
    </div>
  )
}

function KBMockup() {
  return (
    <div className="w-full h-full flex bg-background text-foreground overflow-hidden">
      {/* Folder Tree */}
      <div className="w-48 border-r border-border/50 bg-surface/30 p-3 flex flex-col">
        <div className="relative mb-4">
          <Search className="w-3 h-3 absolute left-2 top-1.5 text-muted-foreground" />
          <div className="h-6 bg-background border border-border rounded w-full pl-6 text-[10px] flex items-center text-muted-foreground/50">Search vault...</div>
        </div>

        <div className="space-y-1">
          <div className="flex items-center text-xs font-medium px-2 py-1 bg-primary/10 text-primary rounded">
            <FolderOpen className="w-3.5 h-3.5 mr-2" /> Operations
          </div>
          <div className="flex items-center text-xs font-medium px-2 py-1 text-muted-foreground hover:text-foreground pl-6">
            <FileText className="w-3 h-3 mr-2 text-blue-400" /> Employee_Handbook.pdf
          </div>
          <div className="flex items-center text-xs font-medium px-2 py-1 text-muted-foreground hover:text-foreground pl-6">
            <FileText className="w-3 h-3 mr-2 text-blue-400" /> Q3_Report.pdf
          </div>
          <div className="flex items-center text-xs font-medium px-2 py-1 text-muted-foreground hover:text-foreground mt-1">
            <Folder className="w-3.5 h-3.5 mr-2" /> Legal
          </div>
          <div className="flex items-center text-xs font-medium px-2 py-1 text-muted-foreground hover:text-foreground mt-1">
            <Folder className="w-3.5 h-3.5 mr-2" /> Engineering
          </div>
        </div>
      </div>

      {/* File List */}
      <div className="flex-1 flex flex-col bg-background">
        <div className="h-12 border-b border-border/50 flex items-center px-4 justify-between">
          <div className="flex items-center text-sm font-medium">
            <span className="text-muted-foreground">Operations</span>
            <ChevronRight className="w-3 h-3 mx-1 text-muted-foreground" />
            <span>Employee_Handbook.pdf</span>
          </div>
          <div className="flex gap-2">
            <div className="p-1 border border-border rounded text-muted-foreground hover:bg-surface"><MoreVertical className="w-4 h-4"/></div>
          </div>
        </div>

        {/* Document Preview */}
        <div className="flex-1 p-6 flex items-center justify-center bg-surface/10 overflow-hidden relative">
          <div className="absolute inset-x-8 top-8 bottom-8 bg-background border border-border shadow-md rounded flex flex-col">
            <div className="h-8 border-b border-border/50 flex items-center px-4 justify-between bg-surface/50">
               <span className="text-xs text-muted-foreground">Page 1 of 42</span>
               <FileDown className="w-3 h-3 text-muted-foreground" />
            </div>
            <div className="p-8 text-sm opacity-60">
              <div className="w-3/4 h-6 bg-border/40 rounded mb-6" />
              <div className="space-y-3">
                <div className="w-full h-3 bg-border/20 rounded" />
                <div className="w-full h-3 bg-border/20 rounded" />
                <div className="w-5/6 h-3 bg-border/20 rounded" />
                <div className="w-full h-3 bg-border/20 rounded" />
              </div>
              <div className="w-1/2 h-5 bg-border/40 rounded mt-8 mb-4" />
              <div className="space-y-3">
                <div className="w-full h-3 bg-border/20 rounded" />
                <div className="w-4/5 h-3 bg-border/20 rounded" />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Metadata Panel */}
      <div className="w-56 border-l border-border/50 bg-surface/30 p-4 text-xs">
        <h5 className="font-semibold mb-4 text-sm">Metadata</h5>

        <div className="space-y-4">
          <div>
            <div className="text-muted-foreground mb-1">Status</div>
            <div className="inline-flex items-center bg-success/10 text-success px-2 py-0.5 rounded font-medium"><CheckCircle2 className="w-3 h-3 mr-1"/> Ready</div>
          </div>
          <div>
            <div className="text-muted-foreground mb-1">Chunk Count</div>
            <div className="font-medium">142 chunks</div>
          </div>
          <div>
            <div className="text-muted-foreground mb-1">Vector Index</div>
            <div className="font-medium">qdrant_prod_01</div>
          </div>
          <div>
            <div className="text-muted-foreground mb-1">Tags</div>
            <div className="flex gap-1 mt-1">
              <span className="bg-surface border border-border px-1.5 py-0.5 rounded text-[10px]">HR</span>
              <span className="bg-surface border border-border px-1.5 py-0.5 rounded text-[10px]">Internal</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function AnalyticsMockup() {
  return (
    <div className="w-full h-full p-6 bg-background text-foreground flex flex-col space-y-4">
      <div className="flex justify-between items-center mb-2">
        <h4 className="font-semibold text-lg">System Reliability Analytics</h4>
        <div className="text-xs bg-surface border border-border px-2 py-1 rounded">Last 30 Days</div>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Overall Reliability Score', val: '98.5', type: 'score' },
          { label: 'Hallucination Rate', val: '0.4%', type: 'good' },
          { label: 'Avg Retrieval Confidence', val: '92%', type: 'good' },
          { label: 'Anomalous Queries', val: '12', type: 'warn' },
        ].map((k, i) => (
          <div key={i} className="bg-surface/50 border border-border/60 p-4 rounded-xl shadow-sm">
            <div className="text-xs text-muted-foreground mb-2">{k.label}</div>
            <div className={cn("text-2xl font-bold",
              k.type === 'score' ? 'text-primary' :
              k.type === 'good' ? 'text-success' : 'text-amber-500'
            )}>{k.val}</div>
          </div>
        ))}
      </div>

      <div className="flex-1 grid grid-cols-3 gap-4">
        {/* Main Chart */}
        <div className="col-span-2 bg-surface/30 border border-border/50 rounded-xl p-4 flex flex-col">
          <div className="text-sm font-medium mb-4">Query Volume vs Hallucination Interventions</div>
          <div className="flex-1 flex items-end justify-between px-2 pt-4 relative border-b border-l border-border/50">
            {/* Fake bar chart */}
            {[40, 55, 30, 70, 60, 85, 90, 75, 50, 65, 80, 95].map((h, i) => (
              <div key={i} className="w-8 flex flex-col justify-end items-center group relative">
                <div className="w-full bg-primary/20 hover:bg-primary/40 rounded-t-sm transition-colors" style={{ height: `${h}%` }}>
                  <div className="w-full bg-danger hover:bg-danger/80 rounded-t-sm transition-colors" style={{ height: `${Math.max(2, h * 0.05)}%` }} />
                </div>
              </div>
            ))}
          </div>
          <div className="flex justify-center gap-4 mt-4 text-[10px] text-muted-foreground">
            <div className="flex items-center"><div className="w-2 h-2 bg-primary/20 mr-1 rounded-sm"/> Safe Queries</div>
            <div className="flex items-center"><div className="w-2 h-2 bg-danger mr-1 rounded-sm"/> Blocked Hallucinations</div>
          </div>
        </div>

        {/* Secondary Info */}
        <div className="bg-surface/30 border border-border/50 rounded-xl p-4 flex flex-col">
          <div className="text-sm font-medium mb-4">Top Rejected Sources</div>
          <div className="space-y-3 flex-1">
            {[
              { name: 'Deprecated_API_v1.md', count: 42, conf: '14%' },
              { name: 'Old_Pricing_2024.pdf', count: 28, conf: '22%' },
              { name: 'Draft_Proposal_X.docx', count: 15, conf: '31%' },
            ].map((s, i) => (
              <div key={i} className="flex justify-between items-center text-xs p-2 bg-background border border-border/40 rounded shadow-sm">
                <div className="flex items-center truncate mr-2"><ShieldAlert className="w-3 h-3 text-danger mr-1.5 shrink-0"/> <span className="truncate">{s.name}</span></div>
                <div className="font-mono text-[10px] text-muted-foreground">{s.conf}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

export function ProductShowcase() {
  const [activeTab, setActiveTab] = useState(TABS[0].id)

  return (
    <section id="platform" className="py-24 overflow-hidden relative">
      <div className="container mx-auto px-4 md:px-8 max-w-7xl">
        <FadeUp>
          <SectionHeading
            title="Designed for Enterprise Scale."
            subtitle="Explore the intuitive tools that give your team complete control over your AI knowledge infrastructure."
            className="mb-16"
          />
        </FadeUp>

        {/* Tab Navigation */}
        <FadeUp delay={0.1}>
          <div className="flex flex-wrap justify-center gap-2 mb-12">
            {TABS.map((tab) => {
              const isActive = activeTab === tab.id
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    "relative px-4 py-2 rounded-full text-sm font-medium transition-colors outline-none focus-visible:ring-2 focus-visible:ring-primary flex items-center space-x-2 z-10",
                    isActive ? "text-primary-foreground" : "text-muted-foreground hover:text-foreground"
                  )}
                  aria-selected={isActive}
                  role="tab"
                >
                  <tab.icon className="w-4 h-4" />
                  <span>{tab.label}</span>
                  {isActive && (
                    <motion.div
                      layoutId="showcase-active-tab"
                      className="absolute inset-0 bg-primary rounded-full -z-10 shadow-sm"
                      transition={{ type: "spring", stiffness: 300, damping: 30 }}
                    />
                  )}
                </button>
              )
            })}
          </div>
        </FadeUp>

        {/* Mockup Container */}
        <FadeUp delay={0.2} duration={0.8}>
          <div className="relative mx-auto max-w-5xl rounded-xl md:rounded-2xl border border-white/20 bg-gradient-to-br from-surface/80 to-surface-elevated/80 backdrop-blur-xl shadow-[0_0_50px_-12px_hsl(var(--primary)/0.25)] overflow-hidden aspect-[16/10] md:aspect-[16/9] ring-1 ring-white/10 group">

            {/* Mac window header - Enhanced */}
            <div className="absolute top-0 w-full h-11 border-b border-border/60 bg-gradient-to-b from-surface/90 to-surface/50 flex items-center px-4 space-x-3 z-30 shadow-sm backdrop-blur-md">
              <div className="flex space-x-2">
                <div className="w-3 h-3 rounded-full bg-[#FF5F56] border border-[#E0443E] shadow-inner" />
                <div className="w-3 h-3 rounded-full bg-[#FFBD2E] border border-[#DEA123] shadow-inner" />
                <div className="w-3 h-3 rounded-full bg-[#27C93F] border border-[#1AAB29] shadow-inner" />
              </div>
              <div className="flex-1 text-center flex justify-center items-center">
                <span className="text-[11px] font-medium text-muted-foreground tracking-wide">Veritas RAG</span>
              </div>
            </div>

            <div className="pt-11 w-full h-full relative bg-background/95">
              <AnimatePresence mode="wait">
                <motion.div
                  key={activeTab}
                  initial={{ opacity: 0, y: 15, scale: 0.97 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -15, scale: 0.97 }}
                  transition={{ type: "spring", stiffness: 300, damping: 30, mass: 0.8 }}
                  className="w-full h-full flex flex-col"
                >
                  {activeTab === 'dashboard' && <DashboardMockup />}
                  {activeTab === 'chat' && <ChatMockup />}
                  {activeTab === 'kb' && <KBMockup />}
                  {activeTab === 'analytics' && <AnalyticsMockup />}
                </motion.div>
              </AnimatePresence>
            </div>

            {/* Subtle gloss overlay */}
            <div className="absolute inset-0 bg-gradient-to-tr from-transparent via-white/[0.02] to-transparent pointer-events-none" />
          </div>
        </FadeUp>
      </div>
    </section>
  )
}
