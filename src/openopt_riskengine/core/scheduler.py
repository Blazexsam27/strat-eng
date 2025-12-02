from datetime import datetime
import schedule
import time

class Scheduler:
    def __init__(self):
        self.jobs = []

    def add_job(self, job_func, trigger, *args, **kwargs):
        job = {
            'func': job_func,
            'trigger': trigger,
            'args': args,
            'kwargs': kwargs,
            'next_run': None
        }
        self.jobs.append(job)

    def start(self):
        while True:
            for job in self.jobs:
                if job['next_run'] is None or datetime.now() >= job['next_run']:
                    job['func'](*job['args'], **job['kwargs'])
                    job['next_run'] = datetime.now() + job['trigger']
            time.sleep(1)

    def clear_jobs(self):
        self.jobs = []