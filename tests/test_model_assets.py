import tempfile
import unittest
from pathlib import Path

import httpx

from app.ai.readiness import (
    ModelAssetState,
    ModelInferenceState,
    ModelRegistrationState,
    OllamaServerState,
)
from app.core.config import PROJECT_ROOT, Settings
from app.services.model_assets import (
    inspect_local_model_assets,
    inspect_local_model_readiness,
)


class ModelAssetTests(unittest.TestCase):
    def setUp(self):
        models_root = PROJECT_ROOT / "models"
        models_root.mkdir(exist_ok=True)

        self.temporary_directory = tempfile.TemporaryDirectory(dir=models_root)
        self.model_directory = Path(self.temporary_directory.name)
        relative_directory = self.model_directory.relative_to(PROJECT_ROOT)
        self.settings = Settings(
            finetuned_model_dir=relative_directory,
            finetuned_model_file="test-model.gguf",
            ollama_model="test-model:latest",
            _env_file=None,
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _write_model(self):
        (self.model_directory / "test-model.gguf").write_bytes(b"small-test-model")

    def _write_modelfile(
        self,
        source: str = "./test-model.gguf",
    ):
        (self.model_directory / "Modelfile").write_text(
            f"FROM {source}\nPARAMETER temperature 0.0\n",
            encoding="utf-8",
        )

    def test_missing_and_partial_assets_are_distinct(self):
        missing = inspect_local_model_assets(self.settings)

        self.assertEqual(
            missing.state,
            ModelAssetState.MISSING,
        )

        self._write_model()
        only_model = inspect_local_model_assets(self.settings)

        self.assertEqual(
            only_model.state,
            ModelAssetState.INCOMPLETE,
        )

        (self.model_directory / "test-model.gguf").unlink()
        self._write_modelfile()
        only_modelfile = inspect_local_model_assets(self.settings)

        self.assertEqual(
            only_modelfile.state,
            ModelAssetState.INCOMPLETE,
        )

    def test_modelfile_source_must_match_configured_file(self):
        self._write_model()
        self._write_modelfile("./wrong-model.gguf")

        invalid = inspect_local_model_assets(self.settings)

        self.assertEqual(
            invalid.state,
            ModelAssetState.INVALID,
        )

        (self.model_directory / "Modelfile").write_text(
            "PARAMETER temperature 0.0\n",
            encoding="utf-8",
        )

        no_source = inspect_local_model_assets(self.settings)

        self.assertEqual(
            no_source.state,
            ModelAssetState.INVALID,
        )

    def test_complete_assets_return_only_relative_path(self):
        self._write_model()
        self._write_modelfile()

        result = inspect_local_model_assets(self.settings)

        self.assertEqual(result.state, ModelAssetState.READY)
        self.assertFalse(Path(result.relative_directory).is_absolute())
        self.assertNotIn(
            str(PROJECT_ROOT),
            result.relative_directory,
        )
        self.assertEqual(result.model_file, "test-model.gguf")


class ModelReadinessTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        models_root = PROJECT_ROOT / "models"
        models_root.mkdir(exist_ok=True)

        self.temporary_directory = tempfile.TemporaryDirectory(dir=models_root)
        relative_directory = Path(self.temporary_directory.name).relative_to(
            PROJECT_ROOT
        )
        self.settings = Settings(
            finetuned_model_dir=relative_directory,
            finetuned_model_file="test-model.gguf",
            ollama_base_url="http://ollama.test",
            ollama_model="test-model:latest",
            _env_file=None,
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    async def test_unavailable_server_stops_later_checks(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError(
                "private connection detail",
                request=request,
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await inspect_local_model_readiness(
                self.settings,
                http_client=client,
            )

        self.assertEqual(
            result.server_status.state,
            OllamaServerState.UNAVAILABLE,
        )
        self.assertEqual(
            result.registration_status.state,
            ModelRegistrationState.NOT_CHECKED,
        )
        self.assertEqual(
            result.inference_status.state,
            ModelInferenceState.NOT_CHECKED,
        )

    async def test_reachable_server_reports_unregistered_model(self):
        transport = httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={"models": [{"name": "other:latest"}]},
            )
        )

        async with httpx.AsyncClient(transport=transport) as client:
            result = await inspect_local_model_readiness(
                self.settings,
                http_client=client,
                run_inference=True,
            )

        self.assertEqual(
            result.server_status.state,
            OllamaServerState.READY,
        )
        self.assertEqual(
            result.registration_status.state,
            ModelRegistrationState.UNREGISTERED,
        )
        self.assertEqual(
            result.inference_status.state,
            ModelInferenceState.NOT_CHECKED,
        )

    async def test_registered_model_does_not_infer_by_default(self):
        request_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal request_count
            request_count += 1

            return httpx.Response(
                200,
                json={
                    "models": [
                        {"name": "test-model:latest"},
                    ]
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await inspect_local_model_readiness(
                self.settings,
                http_client=client,
            )

        self.assertEqual(request_count, 1)
        self.assertEqual(
            result.registration_status.state,
            ModelRegistrationState.REGISTERED,
        )
        self.assertEqual(
            result.inference_status.state,
            ModelInferenceState.NOT_CHECKED,
        )

    async def test_explicit_inference_uses_fixed_minimal_prompt(self):
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)

            if request.url.path == "/api/tags":
                return httpx.Response(
                    200,
                    json={
                        "models": [
                            {"name": "test-model:latest"},
                        ]
                    },
                )

            return httpx.Response(
                200,
                json={
                    "message": {"content": "READY"},
                    "done": True,
                    "done_reason": "stop",
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await inspect_local_model_readiness(
                self.settings,
                http_client=client,
                run_inference=True,
            )

        self.assertEqual(len(requests), 2)
        inference_body = requests[1].content.decode("utf-8")
        self.assertIn("Reply with one short word", inference_body)
        self.assertNotIn("student", inference_body.casefold())
        self.assertEqual(
            result.inference_status.state,
            ModelInferenceState.READY,
        )

    async def test_explicit_inference_failure_is_a_status(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/tags":
                return httpx.Response(
                    200,
                    json={
                        "models": [
                            {"name": "test-model:latest"},
                        ]
                    },
                )

            return httpx.Response(503)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await inspect_local_model_readiness(
                self.settings,
                http_client=client,
                run_inference=True,
            )

        self.assertEqual(
            result.inference_status.state,
            ModelInferenceState.FAILED,
        )


if __name__ == "__main__":
    unittest.main()
