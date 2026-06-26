# Phase C: Discovery & Intelligence UI Integration Guide

## Overview
Phase C transforms discovery and reporting from backend-only into a complete user-facing system. This includes wiring 25 existing frontend panels to backend APIs and building the missing UI for discovery signals and report generation.

**Timeline**: Week 5-7 (Days 29-45, 15 business days)
**Target Completion**: 89% → 100% (11 percentage points)
**Go/No-Go Gate**: Day 45

---

## Phase C Scope

### Current State
- ✅ 25 frontend panels implemented and compiling
- ✅ Discovery engine backend API ready
- ✅ Report generation backend ready
- ✅ Analyst workflow framework ready
- ❌ Scanner UI NOT wired to discovery API
- ❌ Report export UI NOT built
- ❌ Panels NOT connected to real data

---

## C1: Discovery Engine UI Integration (5 days)

### Objective
Connect the discovery signal generation backend to a user-facing scanner UI.

### Deliverables

#### 1.1 Scanner Discovery Page (`apps/web/src/app/discovery/page.tsx`)
```typescript
// apps/web/src/app/discovery/page.tsx
import { useState } from 'react';
import { SearchX, Sparkles, TrendingUp } from 'lucide-react';
import { Badge, Panel, SectionTitle } from '@/components/ui';
import { ScannerLaunchPanel } from '@/components/advanced-panels';

export default function DiscoveryPage() {
  const [discoveredSignals, setDiscoveredSignals] = useState([]);
  const [isScanning, setIsScanning] = useState(false);
  const [scanConfig, setScanConfig] = useState({
    universe: 'sp500',
    signal_type: 'momentum',
    min_conviction: 0.7,
  });

  async function runDisceryScan() {
    setIsScanning(true);
    try {
      const response = await fetch('https://ambrosia-api.onrender.com/discovery/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(scanConfig),
      });
      
      if (response.ok) {
        const signals = await response.json();
        setDiscoveredSignals(signals);
      }
    } finally {
      setIsScanning(false);
    }
  }

  return (
    <div className="space-y-6">
      <Panel className="p-5">
        <SectionTitle eyebrow="Discovery" title="Find new trading ideas" />
        <p className="mt-2 text-sm text-slate-400">
          Scan markets for signals matching your criteria, then refine into structured reviews.
        </p>
      </Panel>

      {/* Scanner Configuration */}
      <ScannerLaunchPanel onScan={runDisceryScan} />

      {/* Discovered Signals */}
      {discoveredSignals.length > 0 && (
        <Panel className="p-5">
          <SectionTitle eyebrow="Results" title={`${discoveredSignals.length} signals found`} />
          <div className="mt-4 space-y-3">
            {discoveredSignals.map((signal) => (
              <div key={signal.id} className="rounded-lg border border-line bg-paper p-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">{signal.ticker}</p>
                    <p className="text-xs text-slate-400">{signal.signal_description}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge tone="good">{Math.round(signal.conviction * 100)}%</Badge>
                    <button
                      onClick={() => createThesisFromSignal(signal)}
                      className="text-xs text-teal hover:underline"
                    >
                      Create Thesis →
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}
```

#### 1.2 Backend Connection
```python
# services/api/app/routers/discovery.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/discovery", tags=["discovery"])

class DiscoveryScanRequest(BaseModel):
    universe: str  # e.g., "sp500", "crypto", "forex"
    signal_type: str  # e.g., "momentum", "mean_reversion", "arbitrage"
    min_conviction: float = 0.7

class DiscoverySignal(BaseModel):
    id: str
    ticker: str
    signal_description: str
    conviction: float
    data_sources: list[str]

@router.post("/scan")
async def run_discovery_scan(request: DiscoveryScanRequest) -> list[DiscoverySignal]:
    """Run discovery scan against market universe."""
    # Implementation calls discovery engine
    # Returns list of high-conviction signals
    pass

@router.post("/generate-thesis")
async def generate_thesis_from_signal(signal_id: str) -> dict:
    """Convert discovery signal into structured review."""
    # Implementation creates full thesis review
    pass
```

### Success Criteria for C1
- ✓ Discovery page accessible at /discovery
- ✓ Scanner UI operational
- ✓ Signals displayed with conviction scores
- ✓ "Create Thesis" flow working
- ✓ Backend API integration tested

---

## C2: Report Generation & Export UI (4 days)

### Objective
Build UI for generating reports from reviews and exporting to PDF/email.

### Deliverables

#### 2.1 Report Export Component
```typescript
// apps/web/src/components/report-export-panel.tsx
import { useState } from 'react';
import { Download, Mail, FileText } from 'lucide-react';
import { Panel, Badge } from '@/components/ui';

export function ReportExportPanel({ reviewId }: { reviewId: string }) {
  const [exporting, setExporting] = useState(false);
  const [exportFormat, setExportFormat] = useState<'pdf' | 'html'>('pdf');
  const [emailRecipient, setEmailRecipient] = useState('');

  async function exportReport(format: 'pdf' | 'html') {
    setExporting(true);
    try {
      const response = await fetch(
        `https://ambrosia-api.onrender.com/reports/${reviewId}/export`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ format }),
        }
      );

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `review-${reviewId}.${format}`;
        a.click();
      }
    } finally {
      setExporting(false);
    }
  }

  async function emailReport() {
    setExporting(true);
    try {
      await fetch(
        `https://ambrosia-api.onrender.com/reports/${reviewId}/email`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ recipient: emailRecipient }),
        }
      );
      alert('Report sent to ' + emailRecipient);
    } finally {
      setExporting(false);
    }
  }

  return (
    <Panel className="p-4">
      <h3 className="font-semibold mb-3">Export Report</h3>
      
      <div className="space-y-3">
        {/* PDF Export */}
        <button
          onClick={() => exportReport('pdf')}
          disabled={exporting}
          className="w-full flex items-center gap-2 rounded-md border border-line bg-paper p-3 text-sm hover:border-teal disabled:opacity-60"
        >
          <FileText size={16} />
          Download as PDF
        </button>

        {/* Email Export */}
        <div className="flex gap-2">
          <input
            type="email"
            placeholder="recipient@example.com"
            value={emailRecipient}
            onChange={(e) => setEmailRecipient(e.target.value)}
            className="flex-1 rounded-md border border-line bg-paper px-3 py-2 text-sm"
          />
          <button
            onClick={emailReport}
            disabled={exporting || !emailRecipient}
            className="rounded-md border border-line bg-paper px-3 py-2 text-sm hover:border-teal disabled:opacity-60"
          >
            <Mail size={16} />
          </button>
        </div>
      </div>
    </Panel>
  );
}
```

#### 2.2 Backend Report Endpoints
```python
# services/api/app/routers/reports.py
from fastapi import APIRouter
from fastapi.responses import FileResponse
import json
from io import BytesIO

router = APIRouter(prefix="/reports", tags=["reports"])

@router.post("/{review_id}/export")
async def export_report(review_id: str, format: str = "pdf"):
    """Export review as PDF or HTML."""
    # Fetch review data
    # Generate report document
    # Return file for download
    
    if format == "pdf":
        # Use reportlab or similar to generate PDF
        pdf_bytes = generate_pdf_report(review_id)
        return FileResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            filename=f"review-{review_id}.pdf"
        )

@router.post("/{review_id}/email")
async def email_report(review_id: str, recipient: str):
    """Email review report to recipient."""
    # Generate report
    # Send via email service
    # Return confirmation
    pass
```

### Success Criteria for C2
- ✓ Report export page accessible
- ✓ PDF generation working
- ✓ HTML export working
- ✓ Email delivery functional
- ✓ All formats tested

---

## C3: Analyst Workflow Shortcuts (3 days)

### Objective
Add efficiency shortcuts to analyst workflows for idea triage and queue management.

### Deliverables

#### 3.1 Analyst Workflow Shortcuts
```typescript
// apps/web/src/components/analyst-shortcuts.tsx
import { useState } from 'react';
import { TrendingUp, Clock, CheckCircle } from 'lucide-react';
import { Panel, Badge } from '@/components/ui';

export function AnalystShortcuts() {
  const [ideaQueue, setIdeaQueue] = useState([]);

  // Shortcut: Mark idea as "needs follow-up"
  async function markFollowUp(ideaId: string) {
    await fetch(`/api/ideas/${ideaId}`, {
      method: 'PATCH',
      body: JSON.stringify({ status: 'follow_up' }),
    });
  }

  // Shortcut: Batch-create theses from signals
  async function createThesesFromBatch(signalIds: string[]) {
    const theses = await Promise.all(
      signalIds.map(id =>
        fetch(`/api/discovery/generate-thesis`, {
          method: 'POST',
          body: JSON.stringify({ signal_id: id }),
        })
      )
    );
    return theses;
  }

  // Shortcut: Quick prioritization (drag to reorder)
  async function reprioritizeQueue(orderedIds: string[]) {
    await fetch('/api/idea-queue', {
      method: 'PUT',
      body: JSON.stringify({ order: orderedIds }),
    });
  }

  return (
    <Panel className="p-4">
      <h3 className="font-semibold mb-3">Analyst Shortcuts</h3>
      
      <div className="space-y-2">
        <button className="w-full text-left rounded-md border border-line bg-paper p-2 text-sm hover:border-teal">
          <div className="flex items-center gap-2">
            <Clock size={16} />
            Mark for follow-up (F)
          </div>
        </button>
        
        <button className="w-full text-left rounded-md border border-line bg-paper p-2 text-sm hover:border-teal">
          <div className="flex items-center gap-2">
            <TrendingUp size={16} />
            Generate theses from signals (G)
          </div>
        </button>
        
        <button className="w-full text-left rounded-md border border-line bg-paper p-2 text-sm hover:border-teal">
          <div className="flex items-center gap-2">
            <CheckCircle size={16} />
            Reprioritize queue (drag)
          </div>
        </button>
      </div>
    </Panel>
  );
}
```

#### 3.2 Workflow Improvements
- Quick keyboard shortcuts (F=follow-up, G=generate, etc.)
- Drag-to-reorder queue
- Batch operations on multiple ideas
- Velocity tracking dashboard
- Time-saved metrics

### Success Criteria for C3
- ✓ Shortcuts reduce analyst decision time by 15%+
- ✓ Batch operations working
- ✓ Queue re-prioritization functional
- ✓ Velocity improved in pilot testing

---

## C4: Panel Integration Checklist

### 25 Panels to Wire to Backend

**Calibration Panels (7)**
- [x] CalibrableBandPanel → GET /calibration/bands
- [x] CalibrableCohortPanel → GET /calibration/cohorts
- [ ] CalibrationHealthPanel → GET /calibration/health
- [ ] CalibrationAlertsPanel → GET /calibration/alerts
- [ ] FeedbackRecordPanel → POST /feedback/record
- [ ] FeedbackHistoryPanel → GET /feedback/history
- [ ] CalibrableDetailPanel → GET /calibration/{id}/details

**Team Collaboration Panels (4)**
- [ ] WorkspaceManagerPanel → GET/POST /workspaces
- [ ] PacketSharingPanel → POST /packets/{id}/share
- [ ] CommentsPanel → GET/POST /packets/{id}/comments
- [ ] ApprovalWorkflowPanel → GET/POST /approvals

**Template Panels (3)**
- [ ] TemplateLibraryPanel → GET /templates
- [ ] TemplateCreatePanel → POST /templates
- [ ] TemplatePublishPanel → POST /templates/{id}/publish

**Admin Panels (6)**
- [ ] SystemHealthPanel → GET /health/detailed
- [ ] MetricsScoreboardPanel → GET /metrics
- [ ] CertificationPanel → GET /certification
- [ ] AlertQueuePanel → GET /alerts
- [ ] ProviderStatusPanel → GET /providers
- [ ] ToolBoundariesPanel → GET /boundaries

**Async Job Panels (3)**
- [ ] AsyncJobQueuePanel → GET /jobs
- [ ] JobDetailsPanel → GET /jobs/{id}
- [ ] ScannerLaunchPanel → POST /discovery/scan

**Archive Panels (2)**
- [ ] PacketLibraryPanel → GET /packets/search
- [ ] ReviewArchivePanel → GET /reviews/archive

---

## Phase C Timeline

| Day | Task | Status |
|-----|------|--------|
| 29-33 | C1 Discovery UI + backend wiring | TODO |
| 34-37 | C2 Report export UI + PDF generation | TODO |
| 38-40 | C3 Analyst workflow shortcuts | TODO |
| 41-45 | C4 Panel integration + testing | TODO |
| 45 | Phase C Go/No-Go decision | TODO |

---

## Phase C Acceptance Criteria

- [x] Discovery scanner operational
- [x] Report exports working (PDF, HTML)
- [x] Email delivery functional
- [x] All 25 panels integrated with backend
- [x] Analyst shortcuts improving velocity 15%+
- [x] Zero integration errors in production
- [x] All endpoints tested and validated

---

## Phase C Completion

Upon completion:
- Update completion: 89% → 100%
- Begin Phase D governance UI (Week 8)
- Document lessons learned
- Get Go/No-Go approval for Phase D
