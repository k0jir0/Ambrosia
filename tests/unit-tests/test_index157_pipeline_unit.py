import json
from services.api.app import coordinator, report
from services.api.app.models import MaterialClaim, SelectiveConfidence, SpecialistAgentOutput, SpecialistOutputV2, TickerIdentity
from services.api.app.providers import ProviderSelection

def provider(): return ProviderSelection(name="ollama-local",provider_type="ollama",fallback_chain=["ollama-local","deterministic-engine"],fallback_used=False,reason="test")
def test_pack_preserves_modes_and_identity(packet_factory):
    pack=coordinator.build_evidence_pack(packet_factory()); by={i["evidenceId"]:i for i in pack["evidence"]}
    assert pack["schemaVersion"]=="adversarial-evidence-pack.v2" and len(pack["contentHash"])==64
    assert by["technical-indicators"]["dataMode"]=="derived" and by["claim-input:claim-1"]["dataMode"]=="user_asserted"
def test_verifier_rejects_simulation_as_observation():
    identity=TickerIdentity(ticker="SPY",canonicalTicker="SPY",instrumentId="ticker:SPY")
    output=SpecialistOutputV2(role="marketData",instructionReferences=["I1"],materialClaims=[MaterialClaim(claimId="c",text="Observed rise",claimType="observation",materiality="high",supportingEvidenceIds=["e"],falsifier="Observed feed differs")],roleConclusion="x",confidence=SelectiveConfidence(direction="supports",evidenceStrength=.5,modelUncertainty=.5,coverage=.5,materiality="high"))
    findings=coordinator._verify(output,[{"evidenceId":"e","subjectInstrumentId":"ticker:SPY","observedAt":"2026-01-01T00:00:00Z","dataMode":"simulated"}],identity,"2026-01-02T00:00:00Z",set())
    assert findings[0].status=="policy_violation"
def test_ollama_separates_analysis_and_verification(monkeypatch,packet_factory):
    calls=[]
    def call(prompt,schema):
        calls.append(schema)
        if schema is coordinator.VERIFIER_RESPONSE_SCHEMA:return json.dumps({"findings":[{"claimId":"c","status":"entailed","evidenceIds":["technical-indicators"],"reasons":[]}]})
        return json.dumps({"schemaVersion":"specialist-output.v2","role":"bull","instructionReferences":["I1","I2","I3","I4"],"materialClaims":[{"claimId":"c","text":"Derived trend supports a conditional case","claimType":"inference","materiality":"medium","supportingEvidenceIds":["technical-indicators"],"contradictingEvidenceIds":[],"relations":[],"premiseClaimIds":[],"uncertainty":.3,"falsifier":"Trend reverses","calculationId":None,"admissionStatus":"proposed"}],"calculationIntents":[],"missingEvidence":[],"falsifiableConditions":[],"alternativeHypotheses":[],"roleConclusion":"conditional","confidence":{"direction":"supports","evidenceStrength":.7,"modelUncertainty":.3,"coverage":.8,"materiality":"medium"},"abstained":False,"abstentionReason":None})
    monkeypatch.setattr(coordinator,"_call_ollama_schema",call); packet=packet_factory(); result=coordinator._run_ollama_role("bull",packet,coordinator.build_evidence_pack(packet),provider())
    assert len(calls)==2 and result.verificationStatus=="passed" and result.materialClaims[0].admissionStatus=="admitted"
def test_report_uses_only_admitted_claims(packet_factory):
    good=MaterialClaim(claimId="good",text="Conditional verified risk",claimType="inference",materiality="high",supportingEvidenceIds=["risk-monitor"],falsifier="Liquidity passes",admissionStatus="admitted")
    bad=MaterialClaim(claimId="bad",text="Unsupported certainty",claimType="observation",materiality="high",admissionStatus="rejected")
    output=SpecialistAgentOutput(role="risk",summary="verified",keyPoints=[],timestamp="2026-01-01Z",provider="ollama",fallbackUsed=False,schemaVersion="specialist-output.v2",verificationStatus="passed",materialClaims=[good],rejectedClaims=[bad],evidencePackHash="a"*64)
    artifact=report.generate_report(packet_factory().model_copy(update={"agentOutputs":{"risk":output}})); text="\n".join(s.content for s in artifact.sections)
    assert artifact.schemaVersion=="ticker-intelligence-report.v2" and "Conditional verified risk" in text and "Unsupported certainty" not in text
