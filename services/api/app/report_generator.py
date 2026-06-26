#!/usr/bin/env python3
"""
Phase C2: Report Generation Layer
Auto-generated decision reports tied to packet history.
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path


@dataclass
class DecisionReport:
    """Auto-generated decision report"""
    report_id: str
    created_at: str
    packet_id: str
    ticker: str
    decision: str  # "buy", "sell", "hold"
    thesis_summary: str
    supporting_evidence: list[dict]
    risk_factors: list[str]
    position_target: dict  # entry, target, stop
    exportable: bool


class ReportGenerator:
    """Generates reports tied to decision packets"""
    
    def __init__(self):
        self.reports: dict[str, DecisionReport] = {}
    
    def generate_report_for_packet(self, packet_id: str, ticker: str, decision: str,
                                   thesis: str, evidence: list[dict]) -> DecisionReport:
        """Generate a report for a decision packet"""
        report_id = f"rpt_{len(self.reports) + 1:06d}"
        
        # Determine risk factors based on decision
        risk_factors = []
        if decision == "buy":
            risk_factors = [
                "Market volatility spike",
                "Negative earnings surprise",
                "Technical breakdown below support",
            ]
        elif decision == "sell":
            risk_factors = [
                "Unexpected positive catalyst",
                "Short squeeze opportunity",
                "Fundamental catalyst reversal",
            ]
        
        # Determine position target
        position_target = {
            "entry": "current_price",
            "target": "+15%" if decision == "buy" else "-10%",
            "stop": "-8%" if decision == "buy" else "+5%",
        }
        
        report = DecisionReport(
            report_id=report_id,
            created_at=datetime.now().isoformat(),
            packet_id=packet_id,
            ticker=ticker,
            decision=decision,
            thesis_summary=thesis,
            supporting_evidence=evidence,
            risk_factors=risk_factors,
            position_target=position_target,
            exportable=True,
        )
        
        self.reports[report_id] = report
        return report
    
    def generate_html_export(self, report: DecisionReport) -> str:
        """Generate exportable HTML report"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{report.ticker} Decision Report - {report.report_id}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto; margin: 20px; }}
        .header {{ border-bottom: 2px solid #333; padding-bottom: 10px; }}
        .decision {{ font-size: 24px; font-weight: bold; color: {'green' if report.decision == 'buy' else 'red'}; }}
        .section {{ margin-top: 20px; }}
        .risk-factors {{ background: #fff3cd; padding: 10px; border-radius: 4px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{report.ticker} Decision Report</h1>
        <div class="decision">Decision: {report.decision.upper()}</div>
        <p>Generated: {report.created_at}</p>
    </div>
    
    <div class="section">
        <h2>Thesis</h2>
        <p>{report.thesis_summary}</p>
    </div>
    
    <div class="section">
        <h2>Supporting Evidence</h2>
        <ul>
"""
        for evidence in report.supporting_evidence:
            html += f"<li>{evidence.get('description', 'Evidence item')}</li>\n"
        html += """
        </ul>
    </div>
    
    <div class="section risk-factors">
        <h2>Risk Factors</h2>
        <ul>
"""
        for risk in report.risk_factors:
            html += f"<li>{risk}</li>\n"
        html += """
        </ul>
    </div>
    
    <div class="section">
        <h2>Position Target</h2>
        <ul>
"""
        for key, value in report.position_target.items():
            html += f"<li>{key.capitalize()}: {value}</li>\n"
        html += """
        </ul>
    </div>
</body>
</html>
"""
        return html
    
    def to_dict(self) -> dict:
        """Convert to dict"""
        return {
            "timestamp": datetime.now().isoformat(),
            "reports_generated": len(self.reports),
            "reports": [asdict(r) for r in self.reports.values()],
        }


if __name__ == "__main__":
    # Create report generator
    generator = ReportGenerator()
    
    # Generate sample reports
    for i, (ticker, decision) in enumerate([("NVDA", "buy"), ("TSLA", "hold"), ("SPY", "sell")]):
        evidence = [
            {"description": f"Signal {j+1} supports {decision}", "confidence": 75 + j*5}
            for j in range(2)
        ]
        report = generator.generate_report_for_packet(
            packet_id=f"pkt_{i+1:04d}",
            ticker=ticker,
            decision=decision,
            thesis=f"{ticker} showing strong {decision} signals based on technical and fundamental analysis.",
            evidence=evidence,
        )
    
    # Save JSON artifact
    artifact_path = Path("artifacts/generated-reports.json")
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    
    output = generator.to_dict()
    with open(artifact_path, "w") as f:
        json.dump(output, f, indent=2)
    
    # Export sample report to HTML
    if generator.reports:
        sample_report = list(generator.reports.values())[0]
        html_content = generator.generate_html_export(sample_report)
        html_path = artifact_path.parent / f"{sample_report.report_id}.html"
        
        with open(html_path, "w") as f:
            f.write(html_content)
        
        print(f"Sample HTML report exported to: {html_path}")
    
    print("Report Generation Module")
    print("=" * 70)
    print(f"Reports Generated: {output['reports_generated']}")
    
    for report in generator.reports.values():
        print(f"\n  {report.report_id}: {report.ticker} ({report.decision.upper()})")
        print(f"    Risk Factors: {len(report.risk_factors)}")
        print(f"    Exportable: {report.exportable}")
    
    print(f"\nReports saved to: {artifact_path}")
