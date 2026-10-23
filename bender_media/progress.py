"""Durable processing checkpoints shared by the web app and Debian worker."""
import time


class Progress:
    def __init__(self, catalog, identifier):
        self.catalog, self.identifier = catalog, identifier
        self.value = dict(started=time.time(), completed=[], stage=None, status='running')

    def save(self):
        self.value['updated'] = time.time()
        self.catalog.update(self.identifier, progress=self.value)

    def stage(self, name, detail):
        self.value.update(stage=name, stage_started=time.time(), detail=detail,
                          current=None, total=None, status='running')
        self.save()

    def detail(self, detail, current=None, total=None):
        self.value.update(detail=detail, current=current, total=total)
        self.save()

    def complete(self, name, reused=False):
        self.value['completed'].append(dict(stage=name, time=time.time(), reused=reused))
        self.save()

    def stop(self, status, detail):
        self.value.update(status=status, detail=detail, current=None, total=None, finished=time.time())
        self.save()
