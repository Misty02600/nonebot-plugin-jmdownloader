import asyncio
from typing import Any, ClassVar, cast

import pytest


class DummyLogger:
    def __init__(self):
        self.warnings: list[str] = []
        self.infos: list[str] = []

    def warning(self, message: str):
        self.warnings.append(message)

    def info(self, message: str):
        self.infos.append(message)


class FakeService:
    """模拟 JMService，用于验证 warmup 调用。"""

    def __init__(self, *, warmup_results: list[bool] | None = None):
        self.warmup_calls = 0
        self._warmup_results = warmup_results or []

    async def warmup(self) -> bool:
        self.warmup_calls += 1
        if self._warmup_results:
            return self._warmup_results.pop(0)
        return True


class DummyOption:
    def __init__(self, fail_times: int = 0):
        self.fail_times = fail_times
        self.build_calls = 0
        self.client = object()

    def build_jm_client(self):
        self.build_calls += 1
        if self.build_calls <= self.fail_times:
            raise OSError("network down")
        return self.client


@pytest.fixture
def dependencies_module(monkeypatch):
    from nonebot_plugin_jmdownloader.bot import dependencies

    return dependencies


@pytest.mark.asyncio
async def test_startup_init_failure_does_not_raise(
    dependencies_module,
    monkeypatch: pytest.MonkeyPatch,
):
    dependencies = dependencies_module
    tasks: list[asyncio.Task[bool]] = []

    service = FakeService(warmup_results=[False])
    monkeypatch.setattr(dependencies, "_jm_service", service)
    monkeypatch.setattr(
        dependencies,
        "_create_background_task",
        lambda coro: tasks.append(asyncio.tasks.create_task(coro)) or tasks[-1],
    )

    await dependencies._warmup_jm_client()
    assert len(tasks) == 1
    assert await tasks[0] is False


def test_get_jm_service_returns_shared_service_without_warmup(
    dependencies_module, monkeypatch: pytest.MonkeyPatch
):
    dependencies = dependencies_module
    service = FakeService(warmup_results=[False])
    monkeypatch.setattr(dependencies, "_jm_service", service)

    assert dependencies.get_jm_service() is service
    assert service.warmup_calls == 0


@pytest.mark.asyncio
async def test_jm_service_uses_internal_option_for_download(
    monkeypatch: pytest.MonkeyPatch,
):
    from nonebot_plugin_jmdownloader.infra import jm_service as jm_service_module

    option = DummyOption()
    logger = DummyLogger()

    class FakeDownloader:
        created_options: ClassVar[list[object]] = []

        def __init__(self, received_option):
            self.option = received_option
            self.created_options.append(received_option)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def download_by_photo_detail(self, _photo):
            return None

    monkeypatch.setattr(jm_service_module, "JmDownloader", FakeDownloader)
    monkeypatch.setattr(jm_service_module, "create_jm_option", lambda _config: option)

    config = jm_service_module.JMOptionContext(cache_dir="cache")
    service = jm_service_module.JMService(config, logger=cast(Any, logger))
    photo = type("Photo", (), {"id": "123"})()

    assert option.build_jm_client() is option.client
    assert await service.download_photo(cast(Any, photo)) is None
    assert FakeDownloader.created_options == [option]
