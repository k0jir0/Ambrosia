from __future__ import annotations

import logging
import os
from datetime import datetime
from uuid import uuid4

from .models import (
    AuditEvent,
    AuditEventCreate,
    DecisionPacket,
    DecisionState,
    JobRecord,
    JobState,
    OutcomeUpdate,
    PacketApproval,
    PacketApprovalCreate,
    PacketComment,
    PacketCommentCreate,
    ReviewStatus,
    TradeReview,
    AlertQueueRecord,
    WorkspaceMember,
    WorkspaceMemberRole,
    WorkspaceRecord,
    WorkspaceCreateRequest,
    WorkflowTemplate,
    WorkflowTemplateCreate,
    WorkflowTemplateStatus,
)
from .db import PacketQuery, PostgresPacketStore, PostgresReviewStore
from .feedback import (
    FeedbackRecord,
    CalibrationBand,
    CohortCalibration,
    CalibrationAlert,
    CalibrationSummary,
    compute_confidence_band,
    compute_calibration_band,
)

logger = logging.getLogger(__name__)


class ReviewStore:
    def __init__(self) -> None:
        self._reviews: dict[str, TradeReview] = {}
        self._packets: dict[str, DecisionPacket] = {}
        self._alerts: list[AlertQueueRecord] = []
        self._jobs: dict[str, JobRecord] = {}
        self._workspaces: dict[str, WorkspaceRecord] = {}
        self._packet_comments: dict[str, list[PacketComment]] = {}
        self._packet_approvals: dict[str, PacketApproval] = {}
        self._workflow_templates: dict[str, WorkflowTemplate] = {}
        self._trial_count = 0
        self._db_enabled = False
        self._review_db: PostgresReviewStore | None = None
        self._packet_db: PostgresPacketStore | None = None
        
        # Feedback storage (from FeedbackStorageMixin)
        self._feedback_records: dict[str, FeedbackRecord] = {}
        self._cohort_calibrations: dict[tuple[str, str, str], CohortCalibration] = {}
        self._calibration_alerts: list[CalibrationAlert] = []

        database_url = os.getenv("DATABASE_URL")
        if database_url:
            try:
                review_db = PostgresReviewStore(database_url)
                packet_db = PostgresPacketStore(database_url)
                review_db.healthcheck()
                packet_db.healthcheck()
                self._review_db = review_db
                self._packet_db = packet_db
                self._db_enabled = True
            except Exception as exc:  # pragma: no cover - environment dependent
                logger.warning("Falling back to in-memory review/packet store: %s", exc)

    def _disable_db(self, exc: Exception) -> None:
        if self._db_enabled:
            logger.warning("Disabling Postgres review/packet stores and using in-memory fallback: %s", exc)
        self._db_enabled = False
        self._review_db = None
        self._packet_db = None

    @property
    def next_trial_count(self) -> int:
        if self._db_enabled and self._review_db is not None:
            try:
                return self._review_db.count_reviews() + 1
            except Exception as exc:  # pragma: no cover - environment dependent
                self._disable_db(exc)
        self._trial_count += 1
        return self._trial_count

    def list_reviews(self) -> list[TradeReview]:
        if self._db_enabled and self._review_db is not None:
            try:
                return self._review_db.list_reviews()
            except Exception as exc:  # pragma: no cover - environment dependent
                self._disable_db(exc)
        return sorted(self._reviews.values(), key=lambda review: review.createdAt, reverse=True)

    def get_review(self, review_id: str) -> TradeReview | None:
        if self._db_enabled and self._review_db is not None:
            try:
                return self._review_db.get_review(review_id)
            except Exception as exc:  # pragma: no cover - environment dependent
                self._disable_db(exc)
        return self._reviews.get(review_id)

    def save_review(self, review: TradeReview) -> TradeReview:
        if self._db_enabled and self._review_db is not None:
            try:
                return self._review_db.save_review(review)
            except Exception as exc:  # pragma: no cover - environment dependent
                self._disable_db(exc)
        self._reviews[review.id] = review
        return review

    def record_decision(self, review_id: str, decision_state: DecisionState) -> TradeReview | None:
        if self._db_enabled and self._review_db is not None:
            try:
                return self._review_db.record_decision(review_id, decision_state)
            except Exception as exc:  # pragma: no cover - environment dependent
                self._disable_db(exc)

        review = self._reviews.get(review_id)
        if review is None:
            return None
        updated = review.model_copy(
            update={
                "decisionState": decision_state,
                "status": ReviewStatus.decision_recorded,
                "audit": [
                    *review.audit,
                    AuditEvent(
                        id=f"audit-{len(review.audit) + 1}",
                        timestamp=datetime.now().strftime("%H:%M:%S"),
                        eventType="decision.recorded",
                        detail=f"Human decision captured: {decision_state.value}",
                    ),
                ],
            }
        )
        self._reviews[review_id] = updated
        return updated

    def record_outcome(self, review_id: str, outcome: OutcomeUpdate) -> TradeReview | None:
        if self._db_enabled and self._review_db is not None:
            try:
                return self._review_db.record_outcome(review_id, outcome.outcome, outcome.outcome_date)
            except Exception as exc:  # pragma: no cover - environment dependent
                self._disable_db(exc)

        review = self._reviews.get(review_id)
        if review is None:
            return None
        updated = review.model_copy(
            update={
                "audit": [
                    *review.audit,
                    AuditEvent(
                        id=f"audit-{len(review.audit) + 1}",
                        timestamp=datetime.now().strftime("%H:%M:%S"),
                        eventType="outcome.recorded",
                        detail=f"{outcome.outcome_date}: {outcome.outcome}",
                    ),
                ]
            }
        )
        self._reviews[review_id] = updated
        return updated

    def list_packets(
        self,
        search: str | None = None,
        ticker: str | None = None,
        decision_state: DecisionState | None = None,
    ) -> list[DecisionPacket]:
        if self._db_enabled and self._packet_db is not None:
            try:
                return self._packet_db.list_packets(
                    PacketQuery(search=search, ticker=ticker, decision_state=decision_state)
                )
            except Exception as exc:  # pragma: no cover - environment dependent
                self._disable_db(exc)

        packets = list(self._packets.values())
        if search:
            search_lower = search.lower()
            packets = [
                packet
                for packet in packets
                if search_lower in packet.title.lower() or search_lower in packet.thesis.lower()
            ]
        if ticker:
            ticker_lower = ticker.lower()
            packets = [packet for packet in packets if packet.ticker.lower() == ticker_lower]
        if decision_state is not None:
            packets = [packet for packet in packets if packet.decisionState == decision_state]
        return sorted(packets, key=lambda packet: packet.createdAt, reverse=True)

    def get_packet(self, packet_id: str) -> DecisionPacket | None:
        if self._db_enabled and self._packet_db is not None:
            try:
                return self._packet_db.get_packet(packet_id)
            except Exception as exc:  # pragma: no cover - environment dependent
                self._disable_db(exc)
        return self._packets.get(packet_id)

    def save_packet(self, packet: DecisionPacket) -> DecisionPacket:
        if self._db_enabled and self._packet_db is not None:
            try:
                return self._packet_db.save_packet(packet)
            except Exception as exc:  # pragma: no cover - environment dependent
                self._disable_db(exc)
        self._packets[packet.id] = packet
        return packet

    def add_packet_audit_event(
        self,
        packet_id: str,
        event: AuditEventCreate,
    ) -> DecisionPacket | None:
        if self._db_enabled and self._packet_db is not None:
            try:
                return self._packet_db.add_packet_audit_event(packet_id, event)
            except Exception as exc:  # pragma: no cover - environment dependent
                self._disable_db(exc)

        packet = self._packets.get(packet_id)
        if packet is None:
            return None
        updated = packet.model_copy(
            update={
                "audit": [
                    *packet.audit,
                    AuditEvent(
                        id=f"packet-audit-{len(packet.audit) + 1}",
                        timestamp=datetime.now().strftime("%H:%M:%S"),
                        eventType=event.eventType,
                        detail=event.detail,
                    ),
                ]
            }
        )
        self._packets[packet_id] = updated
        return updated

    def get_packet_audit(self, packet_id: str) -> list[AuditEvent] | None:
        if self._db_enabled and self._packet_db is not None:
            try:
                return self._packet_db.get_packet_audit(packet_id)
            except Exception as exc:  # pragma: no cover - environment dependent
                self._disable_db(exc)

        packet = self._packets.get(packet_id)
        if packet is None:
            return None
        return packet.audit

    def record_metric_snapshot(self, packet_id: str, metric_type: str, metric_payload: dict) -> None:
        if self._db_enabled and self._packet_db is not None:
            try:
                self._packet_db.add_metric_snapshot(packet_id, metric_type, metric_payload)
            except Exception as exc:  # pragma: no cover - environment dependent
                self._disable_db(exc)

    def record_packet_outcome(self, packet_id: str, outcome: str, outcome_date: str, payload: dict) -> None:
        if self._db_enabled and self._packet_db is not None:
            try:
                self._packet_db.add_outcome_record(packet_id, outcome, outcome_date, payload)
            except Exception as exc:  # pragma: no cover - environment dependent
                self._disable_db(exc)

    def record_retrieval_event(self, packet_id: str, query_text: str, result_count: int, payload: dict) -> None:
        if self._db_enabled and self._packet_db is not None:
            try:
                self._packet_db.add_retrieval_event(packet_id, query_text, result_count, payload)
            except Exception as exc:  # pragma: no cover - environment dependent
                self._disable_db(exc)

    def enqueue_alert(
        self,
        source: str,
        symbol: str,
        message: str,
        payload: dict[str, object],
        signature_verified: bool,
        prompt_injection_detected: bool,
    ) -> AlertQueueRecord:
        alert = AlertQueueRecord(
            id=f"alert-{uuid4().hex[:10]}",
            source=source,
            symbol=symbol,
            message=message,
            receivedAt=datetime.now().isoformat(),
            signatureVerified=signature_verified,
            promptInjectionDetected=prompt_injection_detected,
            payload=payload,
        )
        self._alerts.insert(0, alert)
        self._alerts = self._alerts[:200]
        return alert

    def list_alerts(self) -> list[AlertQueueRecord]:
        return list(self._alerts)

    def record_workflow_run(
        self,
        review_id: str | None,
        idempotency_key: str,
        status: str,
        workflow_version: str,
        error: str | None = None,
    ) -> None:
        if review_id is None or not self._db_enabled or self._review_db is None:
            return
        try:
            self._review_db.add_workflow_run(review_id, idempotency_key, status, workflow_version, error)
        except Exception as exc:  # pragma: no cover - environment dependent
            self._disable_db(exc)

    # ------------------------------------------------------------------
    # Job queue
    # ------------------------------------------------------------------

    def enqueue_job(self, job_type: str, input_summary: str) -> JobRecord:
        job = JobRecord(
            id=f"job-{uuid4().hex[:10]}",
            jobType=job_type,
            state=JobState.queued,
            queuedAt=datetime.now().isoformat(),
            inputSummary=input_summary,
        )
        self._jobs[job.id] = job
        return job

    def get_job(self, job_id: str) -> JobRecord | None:
        return self._jobs.get(job_id)

    def list_jobs(self, job_type: str | None = None) -> list[JobRecord]:
        jobs = list(self._jobs.values())
        if job_type:
            jobs = [j for j in jobs if j.jobType == job_type]
        return sorted(jobs, key=lambda j: j.queuedAt, reverse=True)

    def start_job(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if job is not None:
            self._jobs[job_id] = job.model_copy(
                update={"state": JobState.running, "startedAt": datetime.now().isoformat()}
            )

    def complete_job(self, job_id: str, result: dict) -> None:
        job = self._jobs.get(job_id)
        if job is not None:
            self._jobs[job_id] = job.model_copy(
                update={
                    "state": JobState.completed,
                    "completedAt": datetime.now().isoformat(),
                    "result": result,
                }
            )

    def fail_job(self, job_id: str, error: str) -> None:
        job = self._jobs.get(job_id)
        if job is not None:
            self._jobs[job_id] = job.model_copy(
                update={
                    "state": JobState.failed,
                    "completedAt": datetime.now().isoformat(),
                    "error": error,
                }
            )

    # ------------------------------------------------------------------
    # Phase 4: Collaboration — workspaces
    # ------------------------------------------------------------------

    def create_workspace(self, req: WorkspaceCreateRequest) -> WorkspaceRecord:
        workspace = WorkspaceRecord(
            id=f"ws-{uuid4().hex[:10]}",
            name=req.name,
            description=req.description,
            createdAt=datetime.now().isoformat(),
            ownerId=req.ownerId,
            members=[
                WorkspaceMember(
                    userId=req.ownerId,
                    role=WorkspaceMemberRole.owner,
                    addedAt=datetime.now().isoformat(),
                )
            ],
            packetIds=[],
        )
        self._workspaces[workspace.id] = workspace
        return workspace

    def get_workspace(self, workspace_id: str) -> WorkspaceRecord | None:
        return self._workspaces.get(workspace_id)

    def list_workspaces(self, owner_id: str | None = None) -> list[WorkspaceRecord]:
        workspaces = list(self._workspaces.values())
        if owner_id:
            workspaces = [w for w in workspaces if w.ownerId == owner_id or any(m.userId == owner_id for m in w.members)]
        return sorted(workspaces, key=lambda w: w.createdAt, reverse=True)

    def add_packet_to_workspace(self, workspace_id: str, packet_id: str) -> WorkspaceRecord | None:
        workspace = self._workspaces.get(workspace_id)
        if workspace is None:
            return None
        if packet_id not in workspace.packetIds:
            updated = workspace.model_copy(update={"packetIds": [*workspace.packetIds, packet_id]})
            self._workspaces[workspace_id] = updated
            return updated
        return workspace

    # ------------------------------------------------------------------
    # Phase 4: Collaboration — comments
    # ------------------------------------------------------------------

    def add_packet_comment(self, packet_id: str, create: PacketCommentCreate) -> PacketComment:
        comment = PacketComment(
            id=f"cmt-{uuid4().hex[:10]}",
            packetId=packet_id,
            authorId=create.authorId,
            content=create.content,
            createdAt=datetime.now().isoformat(),
            commentType=create.commentType,
        )
        if packet_id not in self._packet_comments:
            self._packet_comments[packet_id] = []
        self._packet_comments[packet_id].append(comment)
        return comment

    def list_packet_comments(self, packet_id: str) -> list[PacketComment]:
        return list(self._packet_comments.get(packet_id, []))

    # ------------------------------------------------------------------
    # Phase 4: Collaboration — approval flows
    # ------------------------------------------------------------------

    def set_packet_approval(self, packet_id: str, create: PacketApprovalCreate) -> PacketApproval:
        approval = PacketApproval(
            id=f"apv-{uuid4().hex[:10]}",
            packetId=packet_id,
            reviewerId=create.reviewerId,
            decision=create.decision,
            note=create.note,
            decidedAt=datetime.now().isoformat(),
        )
        self._packet_approvals[packet_id] = approval
        return approval

    def get_packet_approval(self, packet_id: str) -> PacketApproval | None:
        return self._packet_approvals.get(packet_id)

    # ------------------------------------------------------------------
    # Phase 5: Workflow templates
    # ------------------------------------------------------------------

    def create_workflow_template(self, create: WorkflowTemplateCreate) -> WorkflowTemplate:
        template = WorkflowTemplate(
            id=f"wft-{uuid4().hex[:10]}",
            name=create.name,
            version=create.version,
            description=create.description,
            category=create.category,
            steps=create.steps,
            createdAt=datetime.now().isoformat(),
            publishedAt=None,
            status=WorkflowTemplateStatus.draft,
            authorId=create.authorId,
        )
        self._workflow_templates[template.id] = template
        return template

    def get_workflow_template(self, template_id: str) -> WorkflowTemplate | None:
        return self._workflow_templates.get(template_id)

    def list_workflow_templates(self, status: str | None = None) -> list[WorkflowTemplate]:
        templates = list(self._workflow_templates.values())
        if status:
            templates = [t for t in templates if t.status.value == status]
        return sorted(templates, key=lambda t: t.createdAt, reverse=True)

    def publish_workflow_template(self, template_id: str) -> WorkflowTemplate | None:
        template = self._workflow_templates.get(template_id)
        if template is None:
            return None
        published = template.model_copy(
            update={
                "status": WorkflowTemplateStatus.published,
                "publishedAt": datetime.now().isoformat(),
            }
        )
        self._workflow_templates[template_id] = published
        return published

    def archive_workflow_template(self, template_id: str) -> WorkflowTemplate | None:
        template = self._workflow_templates.get(template_id)
        if template is None:
            return None
        archived = template.model_copy(update={"status": WorkflowTemplateStatus.archived})
        self._workflow_templates[template_id] = archived
        return archived

    # ---------------------------------------------------------------
    # Feedback Storage Methods (from FeedbackStorageMixin)
    # ---------------------------------------------------------------

    def save_feedback_record(self, feedback: FeedbackRecord) -> FeedbackRecord:
        """Save a feedback record (in-memory; TODO: Postgres persistence)."""
        self._feedback_records[feedback.id] = feedback
        return feedback

    def get_feedback_record(self, feedback_id: str) -> FeedbackRecord | None:
        """Retrieve a feedback record by ID."""
        return self._feedback_records.get(feedback_id)

    def list_feedback_records(
        self,
        ticker: str | None = None,
        decision_state: str | None = None,
        outcome: str | None = None,
        limit: int = 100,
    ) -> list[FeedbackRecord]:
        """List feedback records with optional filtering."""
        records = list(self._feedback_records.values())
        
        if ticker:
            ticker_lower = ticker.lower()
            records = [r for r in records if r.ticker.lower() == ticker_lower]
        if decision_state:
            records = [r for r in records if r.decision_state.lower() == decision_state.lower()]
        if outcome:
            records = [r for r in records if r.outcome.value.lower() == outcome.lower()]
        
        return sorted(records, key=lambda r: r.recorded_at, reverse=True)[:limit]

    def get_cohort_calibration(
        self, ticker: str, asset_class: str, time_horizon: str
    ) -> CohortCalibration | None:
        """Get calibration for a cohort (ticker, asset_class, time_horizon)."""
        key = (ticker.lower(), asset_class.lower(), time_horizon.lower())
        return self._cohort_calibrations.get(key)

    def recompute_cohort_calibration(
        self, ticker: str, asset_class: str, time_horizon: str
    ) -> CohortCalibration:
        """
        Recompute calibration for a cohort by aggregating feedback records.
        
        Returns CohortCalibration with:
        - Aggregated accuracy by confidence band
        - Overall platform accuracy
        - Calibration alerts for miscalibrated bands
        """
        from collections import defaultdict
        from .feedback import OutcomeResult
        
        key = (ticker.lower(), asset_class.lower(), time_horizon.lower())
        
        # Filter feedback for this cohort
        cohort_feedback = [
            r for r in self._feedback_records.values()
            if r.ticker.lower() == key[0]
            and r.asset_class.lower() == key[1]
            and r.time_horizon.lower() == key[2]
        ]
        
        if not cohort_feedback:
            # Return empty calibration
            return CohortCalibration(
                ticker=ticker,
                asset_class=asset_class,
                time_horizon=time_horizon,
                bands={},
                total_decisions=0,
                overall_accuracy=0.0,
                flags={},
            )
        
        # Group by confidence band
        bands_dict = defaultdict(lambda: {
            "decisions": [],
            "wins": 0,
            "losses": 0,
            "whipsaws": 0,
            "partials": 0,
        })
        
        for feedback in cohort_feedback:
            band = compute_confidence_band(feedback.confidence)
            bands_dict[band]["decisions"].append(feedback)
            
            if feedback.outcome == OutcomeResult.won:
                bands_dict[band]["wins"] += 1
            elif feedback.outcome == OutcomeResult.lost:
                bands_dict[band]["losses"] += 1
            elif feedback.outcome == OutcomeResult.whipsaw:
                bands_dict[band]["whipsaws"] += 1
            elif feedback.outcome == OutcomeResult.partial:
                bands_dict[band]["partials"] += 1
        
        # Compute band calibrations
        bands: dict[str, CalibrationBand] = {}
        over_confident = False
        under_confident = False
        
        for band_name, band_data in bands_dict.items():
            confidence_level = int(band_name.split("-")[0])
            cal_band = compute_calibration_band(
                decisions=len(band_data["decisions"]),
                wins=band_data["wins"],
                losses=band_data["losses"],
                whipsaws=band_data["whipsaws"],
                partials=band_data["partials"],
                confidence_level=confidence_level,
            )
            bands[band_name] = cal_band
            
            if cal_band.calibration_status == "over-confident":
                over_confident = True
            elif cal_band.calibration_status == "under-confident":
                under_confident = True
        
        # Compute overall accuracy
        total_decisions = len(cohort_feedback)
        total_wins = sum(1 for f in cohort_feedback if f.outcome == OutcomeResult.won)
        total_partials = sum(1 for f in cohort_feedback if f.outcome == OutcomeResult.partial)
        overall_accuracy = (total_wins + 0.5 * total_partials) / total_decisions if total_decisions > 0 else 0.0
        
        cohort_cal = CohortCalibration(
            ticker=ticker,
            asset_class=asset_class,
            time_horizon=time_horizon,
            bands=bands,
            total_decisions=total_decisions,
            overall_accuracy=overall_accuracy,
            flags={"any_over_confident": over_confident, "any_under_confident": under_confident},
        )
        
        # Update calibration alerts
        self._update_calibration_alerts(cohort_cal)
        
        # Store in cache
        self._cohort_calibrations[key] = cohort_cal
        
        return cohort_cal

    def get_band_calibration(self, ticker: str, confidence_band: str) -> CalibrationBand | None:
        """Get calibration for a specific confidence band across all time horizons."""
        # Aggregate across all cohorts for this ticker + band
        from collections import defaultdict
        from .feedback import OutcomeResult
        
        band_data = {
            "decisions": [],
            "wins": 0,
            "losses": 0,
            "whipsaws": 0,
            "partials": 0,
        }
        
        ticker_lower = ticker.lower()
        for feedback in self._feedback_records.values():
            if feedback.ticker.lower() == ticker_lower:
                band = compute_confidence_band(feedback.confidence)
                if band == confidence_band:
                    band_data["decisions"].append(feedback)
                    if feedback.outcome == OutcomeResult.won:
                        band_data["wins"] += 1
                    elif feedback.outcome == OutcomeResult.lost:
                        band_data["losses"] += 1
                    elif feedback.outcome == OutcomeResult.whipsaw:
                        band_data["whipsaws"] += 1
                    elif feedback.outcome == OutcomeResult.partial:
                        band_data["partials"] += 1
        
        if not band_data["decisions"]:
            return None
        
        confidence_level = int(confidence_band.split("-")[0])
        return compute_calibration_band(
            decisions=len(band_data["decisions"]),
            wins=band_data["wins"],
            losses=band_data["losses"],
            whipsaws=band_data["whipsaws"],
            partials=band_data["partials"],
            confidence_level=confidence_level,
        )

    def get_calibration_summary(self) -> CalibrationSummary:
        """Get platform-wide calibration health snapshot."""
        from .feedback import OutcomeResult
        
        if not self._feedback_records:
            return CalibrationSummary(
                total_decisions=0,
                overall_accuracy=0.0,
                total_alerts=0,
                over_confident_count=0,
                under_confident_count=0,
                well_calibrated_count=0,
            )
        
        total_decisions = len(self._feedback_records)
        total_wins = sum(1 for f in self._feedback_records.values() if f.outcome == OutcomeResult.won)
        total_partials = sum(1 for f in self._feedback_records.values() if f.outcome == OutcomeResult.partial)
        overall_accuracy = (total_wins + 0.5 * total_partials) / total_decisions if total_decisions > 0 else 0.0
        
        over_confident = sum(1 for alert in self._calibration_alerts if alert.alert_type == "over-confident")
        under_confident = sum(1 for alert in self._calibration_alerts if alert.alert_type == "under-confident")
        well_calibrated = len(self._cohort_calibrations) - (over_confident + under_confident)
        
        return CalibrationSummary(
            total_decisions=total_decisions,
            overall_accuracy=overall_accuracy,
            total_alerts=len(self._calibration_alerts),
            over_confident_count=over_confident,
            under_confident_count=under_confident,
            well_calibrated_count=max(0, well_calibrated),
        )

    def list_calibration_alerts(
        self, severity: str | None = None, ticker: str | None = None
    ) -> list[CalibrationAlert]:
        """List calibration alerts with optional filtering."""
        alerts = self._calibration_alerts
        
        if severity:
            alerts = [a for a in alerts if a.severity.lower() == severity.lower()]
        if ticker:
            ticker_lower = ticker.lower()
            alerts = [a for a in alerts if a.ticker.lower() == ticker_lower]
        
        return sorted(alerts, key=lambda a: a.generated_at, reverse=True)

    def _update_calibration_alerts(self, cohort: CohortCalibration) -> None:
        """Generate or update alerts for a cohort based on calibration status."""
        # Remove old alerts for this cohort
        self._calibration_alerts = [
            a for a in self._calibration_alerts
            if not (
                a.ticker == cohort.ticker
                and a.asset_class == cohort.asset_class
                and a.time_horizon == cohort.time_horizon
            )
        ]
        
        # Create new alerts for miscalibrated bands
        for band_name, band_cal in cohort.bands.items():
            if band_cal.is_well_calibrated:
                continue
            
            severity = "warning" if abs(band_cal.calibration_error) < 0.10 else "critical"
            alert = CalibrationAlert(
                id=f"alert-{uuid4().hex[:10]}",
                ticker=cohort.ticker,
                asset_class=cohort.asset_class,
                time_horizon=cohort.time_horizon,
                confidence_band=band_name,
                alert_type=band_cal.calibration_status,
                severity=severity,
                target_accuracy=band_cal.target_accuracy,
                actual_accuracy=band_cal.accuracy,
                calibration_error=band_cal.calibration_error,
                decision_count=band_cal.decisions,
                generated_at=datetime.now().isoformat(),
            )
            self._calibration_alerts.append(alert)

    def get_calibration_metrics(self):
        """Compute and return all 8 calibration metrics."""
        from .calibration_metrics import compute_all_metrics
        return compute_all_metrics(self)

    def get_operational_scorecard(self):
        """Generate Index39 certification scorecard."""
        from .operational_scorecard import compute_scorecard_index39
        return compute_scorecard_index39(self)


store = ReviewStore()