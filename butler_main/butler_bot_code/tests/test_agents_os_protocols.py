from __future__ import annotations

import sys
import unittest
from pathlib import Path


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from agents_os.governance import ApprovalTicket, ExperienceRecord
from agents_os.protocol import DecisionReceipt, HandoffReceipt, StepReceipt
from agents_os.recovery import RECOVERY_ACTIONS, RecoveryDirective
from agents_os.runtime import (
    EDGE_KINDS,
    FAILURE_CLASSES,
    PROCESS_ROLES,
    RUN_STATUSES,
    STEP_KINDS,
    StepResult,
    WorkflowEdgeSpec,
    WorkflowSpec,
    WorkflowStepSpec,
    normalize_edge_kind,
    normalize_failure_class,
    normalize_process_role,
    normalize_run_status,
    normalize_step_kind,
)
from agents_os.verification import VERIFICATION_DECISIONS, VerificationReceipt
from agents_os.workflow import WorkflowCheckpoint, WorkflowCursor, WorkflowRunProjection


class AgentsOsProtocolTests(unittest.TestCase):
    def test_runtime_normalizers_guard_known_enums(self) -> None:
        self.assertEqual(normalize_run_status('running'), 'running')
        self.assertEqual(normalize_run_status('weird'), 'pending')
        self.assertEqual(normalize_failure_class('tool_error'), 'tool_error')
        self.assertEqual(normalize_failure_class('weird'), '')
        self.assertEqual(normalize_process_role('acceptance'), 'acceptance')
        self.assertEqual(normalize_process_role('background-only'), 'executor')
        self.assertEqual(normalize_step_kind('verify'), 'verify')
        self.assertEqual(normalize_step_kind('finalize'), 'finalize')
        self.assertEqual(normalize_edge_kind('resume_from'), 'resume_from')
        self.assertEqual(normalize_step_kind('tell_user'), 'dispatch')

    def test_wave1_contract_enums_stay_generic(self) -> None:
        self.assertIn('pending', RUN_STATUSES)
        self.assertIn('executor', PROCESS_ROLES)
        self.assertIn('verify', STEP_KINDS)
        self.assertIn('approve', STEP_KINDS)
        self.assertIn('join', STEP_KINDS)
        self.assertIn('finalize', STEP_KINDS)
        self.assertIn('resume_from', EDGE_KINDS)
        self.assertIn('acceptance_failed', FAILURE_CLASSES)
        self.assertNotIn('legacy_round_only', RUN_STATUSES)
        self.assertNotIn('tell_user', STEP_KINDS)
        self.assertNotIn('feishu_sender', PROCESS_ROLES)

    def test_workflow_spec_and_step_result_defaults(self) -> None:
        spec = WorkflowSpec(
            workflow_id='maintenance_round',
            run_type='background_round',
            scenario_id='maintenance',
            steps=[
                WorkflowStepSpec(step_id='prepare', step_kind='prepare', process_role='manager'),
                WorkflowStepSpec(step_id='dispatch', step_kind='dispatch', process_role='executor', allow_parallel=True),
            ],
        )
        result = StepResult(step_id='dispatch', process_role='not-a-role', summary='done')
        self.assertEqual(spec.steps[0].step_kind, 'prepare')
        self.assertEqual(spec.steps[1].process_role, 'executor')
        self.assertEqual(result.process_role, 'executor')
        self.assertEqual(result.summary, 'done')

    def test_protocol_receipts_and_workflow_cursor_defaults(self) -> None:
        step = StepReceipt(step_id='dispatch:branch-1', workflow_id='maintenance_round')
        handoff = HandoffReceipt(workflow_id='maintenance_round', source_step_id='dispatch:branch-1', target_step_id='promote')
        decision = DecisionReceipt(workflow_id='maintenance_round', step_id='dispatch:branch-1', decision='proceed')
        cursor = WorkflowCursor(workflow_id='maintenance_round', current_step_id='dispatch')
        checkpoint = WorkflowCheckpoint(workflow_id='maintenance_round', cursor=cursor, step_receipt=step, handoff_receipt=handoff, decision_receipt=decision)
        projection = WorkflowRunProjection(spec=WorkflowSpec(workflow_id='maintenance_round'), cursor=cursor, step_receipts=[step])

        self.assertEqual(step.step_kind, 'dispatch')
        self.assertEqual(handoff.status, 'completed')
        self.assertEqual(decision.status, 'completed')
        self.assertEqual(cursor.status, 'pending')
        self.assertEqual(checkpoint.workflow_id, 'maintenance_round')
        self.assertEqual(projection.to_dict()['cursor']['current_step_id'], 'dispatch')

    def test_workflow_edges_and_projection_roundtrip(self) -> None:
        spec = WorkflowSpec(
            workflow_id='wf_roundtrip',
            steps=[
                WorkflowStepSpec(step_id='dispatch_1', step_kind='dispatch', process_role='executor'),
                WorkflowStepSpec(step_id='approve_1', step_kind='approve', process_role='approval'),
                WorkflowStepSpec(step_id='finalize_1', step_kind='finalize', process_role='manager'),
            ],
            edges=[
                WorkflowEdgeSpec(source_step_id='dispatch_1', target_step_id='approve_1', edge_kind='on_success'),
                WorkflowEdgeSpec(source_step_id='approve_1', target_step_id='finalize_1', edge_kind='resume_from'),
            ],
        )
        projection = WorkflowRunProjection(
            spec=spec,
            cursor=WorkflowCursor(workflow_id='wf_roundtrip', current_step_id='approve_1', resume_from='approve_1'),
        )

        restored = WorkflowRunProjection.from_dict(projection.to_dict())

        self.assertEqual(restored.spec.edges[0].edge_kind, 'on_success')
        self.assertEqual(restored.spec.edges[1].edge_kind, 'resume_from')
        self.assertEqual(restored.cursor.resume_from, 'approve_1')

    def test_verification_recovery_and_governance_contracts(self) -> None:
        verification = VerificationReceipt(verified=False, decision='unknown', retryable=True)
        recovery = RecoveryDirective(action='retry_step', retry_budget=2, backoff_seconds=30)
        approval = ApprovalTicket(source_run_id='run_1', requested_action='apply approved patch')
        experience = ExperienceRecord(run_type='background_round', workflow='maintenance_round', confidence=1.5)
        self.assertIn(verification.decision, VERIFICATION_DECISIONS)
        self.assertEqual(verification.decision, 'pass')
        self.assertIn(recovery.action, RECOVERY_ACTIONS)
        self.assertEqual(recovery.retry_budget, 2)
        self.assertEqual(approval.status, 'pending')
        self.assertEqual(experience.confidence, 1.0)


if __name__ == '__main__':
    unittest.main()
