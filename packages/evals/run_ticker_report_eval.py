#!/usr/bin/env python3
import argparse,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser();parser.add_argument("--outputs",type=Path);parser.add_argument("--suite",type=Path,default=Path(__file__).with_name("ticker_report_suite.json"));parser.add_argument("--output",type=Path,default=ROOT/"artifacts"/"ticker-report-evaluation.json");parser.add_argument("--require-release-thresholds",action="store_true")
def main():
 a=parser.parse_args();suite=json.loads(a.suite.read_text());cases=suite["cases"]
 if not a.outputs:
  result={"status":"not_executed","reason":"No actual report outputs supplied","caseCount":len(cases)};a.output.parent.mkdir(exist_ok=True);a.output.write_text(json.dumps(result,indent=2));print(json.dumps(result));return 1 if a.require_release_thresholds else 0
 records={r["caseId"]:r["report"] for r in json.loads(a.outputs.read_text())}; results=[]
 for case in cases:
  report=records.get(case["id"],{});refs={x for s in report.get("sections",[]) for x in s.get("citationEvidenceIds",[])};abstained=report.get("reportValidationStatus") in {"partial","failed"}
  results.append({"identity":(report.get("tickerIdentity")or{}).get("instrumentId")==case["instrumentId"],"temporal":not refs.intersection(case["forbiddenEvidenceIds"]),"simulated":len(refs.intersection(case["simulatedEvidenceIds"])),"abstention":not case["requireAbstention"] or abstained})
 n=len(results) or 1;metrics={"identityAccuracy":sum(r["identity"] for r in results)/n,"temporalDiscipline":sum(r["temporal"] for r in results)/n,"simulatedAsObservedErrors":sum(r["simulated"] for r in results),"requiredAbstentionRecall":sum(r["abstention"] for r in results)/n};failed=[k for k,v in metrics.items() if (k=="simulatedAsObservedErrors" and v>suite["releaseThresholds"][k]) or (k!="simulatedAsObservedErrors" and v<suite["releaseThresholds"][k])];out={"status":"failed" if failed else "passed","metrics":metrics,"failures":failed};a.output.parent.mkdir(exist_ok=True);a.output.write_text(json.dumps(out,indent=2));print(json.dumps(out));return bool(failed)
if __name__=="__main__":raise SystemExit(main())
