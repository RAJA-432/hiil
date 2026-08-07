from __future__ import annotations

from vajra_gate.crons import _CRON_NAMESPACE, CronJob, CronScheduler
from vajra_gate.store import KVStore


def _scheduler(store: KVStore) -> CronScheduler:
    return CronScheduler(store=store)


def test_add_persists_job(tmp_path):
    store = KVStore(tmp_path)
    sched = _scheduler(store)

    job = sched.add(3600, "daily digest", thread_id="thread_1", agent_config={"name": "digest"})

    stored = store.get(_CRON_NAMESPACE, job.id)
    assert stored is not None
    value = stored["value"]
    assert value["task_input"] == "daily digest"
    assert value["thread_id"] == "thread_1"
    assert value["agent_config"] == {"name": "digest"}
    assert value["schedule_seconds"] == 3600


def test_new_scheduler_restores_jobs(tmp_path):
    store = KVStore(tmp_path)
    first = _scheduler(store)
    job = first.add(7200, "weekly report")

    second = _scheduler(store)
    restored = second.get_job(job.id)
    assert restored is not None
    assert restored.task_input == "weekly report"
    assert restored.schedule_seconds == 7200


def test_full_task_input_survives_roundtrip(tmp_path):
    store = KVStore(tmp_path)
    long_input = "x" * 500
    job = _scheduler(store).add(60, long_input)

    restored = _scheduler(store).get_job(job.id)
    assert restored is not None
    assert restored.task_input == long_input
    assert restored.to_dict()["task_input"] == "x" * 100


def test_remove_deletes_persisted_job(tmp_path):
    store = KVStore(tmp_path)
    sched = _scheduler(store)
    job = sched.add(60, "delete me")

    assert sched.remove(job.id) is True
    assert store.get(_CRON_NAMESPACE, job.id) is None
    assert _scheduler(store).get_job(job.id) is None


def test_list_jobs_includes_restored(tmp_path):
    store = KVStore(tmp_path)
    _scheduler(store).add(60, "one")
    _scheduler(store).add(120, "two")

    fresh = _scheduler(store)
    assert {j.task_input for j in fresh.list_jobs()} == {"one", "two"}


def test_cronjob_from_dict_defaults():
    job = CronJob.from_dict({"id": "cron_1", "schedule_seconds": 60, "task_input": "hi"})
    assert job.thread_id is None
    assert job.enabled is True
    assert job.run_count == 0
