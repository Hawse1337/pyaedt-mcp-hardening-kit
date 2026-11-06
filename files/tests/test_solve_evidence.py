import unittest
from types import SimpleNamespace
from unittest import mock

from aedt_target import AedtTarget
from pyaedt_backend import PyAedtBackend
from solve_evidence import summarize_hfss_convergence, summarize_hfss_profile


CONVERGENCE = """Setup : Single28
Number of Passes
Completed : 4
Maximum : 12
Minimum : 2
Criterion : Max Mag. Delta S
Target : 0.01
Current : 0.0080994
Target Consecutive Passes : 2
Current Consecutive Passes : 2
Converged : Yes
Pass Number|Solved Elements|Max Mag. Delta S|
1|3740|N/A|
2|4547|0.010032|
3|5665|0.0052575|
4|7051|0.0080994|
"""


class SolveEvidenceTests(unittest.TestCase):
    def _backend(self):
        desktop = SimpleNamespace(aedt_process_id=1234, port=0)
        app = SimpleNamespace(
            get_setups=lambda: ["Setup1"],
            are_there_simulations_running=False,
            analyze_setup=mock.Mock(return_value=True),
        )
        return PyAedtBackend(desktop_factory=lambda **kwargs: desktop,
                            hfss_factory=lambda **kwargs: app)

    def test_idle_desktop_is_not_latest_solver_completion(self):
        result = self._backend().execute(AedtTarget("pid", 1234), "analysis_status", {
            "project_name": "Demo", "design_name": "HFSSDesign1"
        })
        self.assertFalse(result["running"])
        self.assertEqual(result["activity_scope"], "desktop")
        self.assertFalse(result["solver_completion_confirmed"])
        self.assertFalse(result["convergence_confirmed"])

    def test_start_api_success_is_not_latest_solver_completion(self):
        result = self._backend().execute(AedtTarget("pid", 1234), "start_analysis", {
            "project_name": "Demo", "design_name": "HFSSDesign1", "setup_name": "Setup1"
        })
        self.assertTrue(result["started"])
        self.assertFalse(result["solver_completion_confirmed"])
        self.assertFalse(result["convergence_confirmed"])

    def test_native_convergence_requires_consecutive_passes(self):
        result = summarize_hfss_convergence(CONVERGENCE)
        self.assertEqual(result["assessment"], "converged")
        self.assertEqual(result["computed_consecutive_passes"], 2)
        self.assertFalse(result["latest_submission_linked"])

    def test_normal_completion_is_not_delta_s_convergence(self):
        result = summarize_hfss_profile("Status: Normal Completion\n")
        self.assertTrue(result["normal_completion_reported"])
        self.assertFalse(result["latest_submission_linked"])
        self.assertNotIn("convergence_confirmed", result)

    def test_last_reported_status_wins(self):
        result = summarize_hfss_profile("Status: Normal Completion\nStatus: SOLVER_OUT_OF_MEMORY\n")
        self.assertEqual(result["last_reported_status"], "SOLVER_OUT_OF_MEMORY")
        self.assertFalse(result["normal_completion_reported"])

    def test_only_final_pass_below_target_is_not_converged(self):
        text = CONVERGENCE.replace("3|5665|0.0052575|", "3|5665|0.012|").replace("Converged : Yes", "Converged : No")
        self.assertEqual(summarize_hfss_convergence(text)["assessment"], "not_converged")

    def test_native_yes_does_not_override_insufficient_passes(self):
        text = CONVERGENCE.replace("3|5665|0.0052575|", "3|5665|0.012|")
        self.assertEqual(summarize_hfss_convergence(text)["assessment"], "not_converged")

    def test_native_no_does_not_override_unknown_conditions(self):
        text = CONVERGENCE.replace("Converged : Yes", "Converged : No")
        self.assertEqual(summarize_hfss_convergence(text)["assessment"], "not_converged")

    def test_native_consecutive_counter_is_required(self):
        text = CONVERGENCE.replace("Current Consecutive Passes : 2", "Current Consecutive Passes : 1")
        self.assertEqual(summarize_hfss_convergence(text)["assessment"], "not_converged")

    def test_missing_rows_or_other_criterion_remains_inconclusive(self):
        cases = [
            CONVERGENCE.replace("3|5665|0.0052575|", ""),
            CONVERGENCE.replace("Max Mag. Delta S", "Energy"),
            "localized or unknown output",
            CONVERGENCE.replace("Target : 0.01", "Target : 1e999"),
            CONVERGENCE.replace("3|5665|0.0052575|", "3|5665|-0.001|"),
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertEqual(summarize_hfss_convergence(text)["assessment"], "inconclusive")

    def test_empty_profile_is_not_success(self):
        self.assertIsNone(summarize_hfss_profile("")["normal_completion_reported"])


if __name__ == "__main__":
    unittest.main()
