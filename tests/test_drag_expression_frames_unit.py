"""Focused executable checks for authored drag-expression frames.

Run directly; this is intentionally independent of the legacy pytest gate.
"""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from desktop_pet.drag_expression_frames import load_drag_expression_sequence


class DragExpressionFrameTests(unittest.TestCase):
    def test_authored_sequence_has_exact_default_and_timed_hold(self):
        sequence = load_drag_expression_sequence()
        self.assertEqual(sequence.frames[0].sha256, sequence.approved_default_sha256)
        self.assertEqual(sequence.frames[-1].eye_scale, 1.20)
        self.assertEqual(sequence.hold_duration_ms, 100)
        self.assertEqual(sequence.enter_duration_ms, 150)
        self.assertEqual(sequence.exit_duration_ms, 150)
        self.assertGreaterEqual(len(sequence.frames), 5)

    def test_phase_selection_uses_authored_frames(self):
        sequence = load_drag_expression_sequence()
        self.assertEqual(sequence.for_phase(0).frame_id, "neutral")
        self.assertEqual(sequence.for_phase(3).frame_id, "hold-left")
        self.assertEqual(sequence.for_phase(5).frame_id, "hold-right")
        self.assertEqual(sequence.for_exit(150).frame_id, "neutral")


if __name__ == "__main__":
    unittest.main()
