from django.core.exceptions import FieldDoesNotExist
from django.test import TestCase
from model_bakery import baker

from apps.resume import models


class TestResumeMode(TestCase):
    def setUp(self) -> None:
        self.resume = baker.make(models.Resume)

    def test_next_step(self):
        self.resume.next_step(1)
        self.assertEqual(self.resume.steps["1"], "finished")
        self.assertEqual(self.resume.steps["2"], "started")

    def test_next_step_in_updates(self):
        self.resume.next_step(1)
        self.resume.next_step(2)
        self.resume.next_step(1)
        self.assertEqual(self.resume.steps["1"], "finished")
        self.assertEqual(self.resume.steps["2"], "finished")

    def test_invalid_step(self):
        with self.assertRaises(FieldDoesNotExist):
            self.resume.next_step(3)

    def test_finish_flow(self):
        self.resume.next_step(1)
        self.resume.next_step(2)
        self.resume.next_step(3)
        self.resume.finish_flow()
        self.assertEqual(
            self.resume.steps["5"],
            {
                "project": "started",
                "language": "started",
                "certification": "started",
                "connection_ways": "started",
            },
        )

    def test_sub_step(self):
        self.resume.next_step(1)
        self.resume.next_step(2)
        self.resume.next_step(3)
        self.resume.finish_flow()
        self.resume.finish_sub_step("project")
        self.assertEqual(self.resume.steps["5"]["project"], "finished")
