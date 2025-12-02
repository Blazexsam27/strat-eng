import pytest
from openopt_riskengine.core.automation import Automation
from openopt_riskengine.core.scheduler import Scheduler
from openopt_riskengine.core.tasks import Task

def test_automation_initialization():
    automation = Automation()
    assert automation is not None

def test_scheduler_initialization():
    scheduler = Scheduler()
    assert scheduler is not None

def test_task_creation():
    task = Task(name="Test Task", description="This is a test task.")
    assert task.name == "Test Task"
    assert task.description == "This is a test task."