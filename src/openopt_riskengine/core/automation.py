# OpenOpt-RiskEngine/src/openopt_riskengine/core/automation.py

"""
This file includes core automation functionalities for the risk engine, such as task scheduling and execution.
"""

class Automation:
    def __init__(self):
        self.tasks = []

    def add_task(self, task):
        self.tasks.append(task)

    def execute_tasks(self):
        for task in self.tasks:
            task.run()

class Task:
    def __init__(self, name, action):
        self.name = name
        self.action = action

    def run(self):
        print(f"Executing task: {self.name}")
        self.action()