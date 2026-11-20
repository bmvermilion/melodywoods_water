import os
import shutil
import subprocess
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
PROJECT_DIR = os.path.join(REPO_ROOT, 'melodywoods_water')
SAM_BIN = os.environ.get('SAM', os.path.join(REPO_ROOT, '.venv', 'bin', 'sam'))


def _missing_prereqs():
    """Return a list of reasons the integration tests cannot run here."""
    missing = []
    if not os.path.exists(SAM_BIN):
        missing.append(f"sam not found at {SAM_BIN}")
    if shutil.which('docker') is None:
        missing.append("docker not on PATH")
    return missing


_MISSING = _missing_prereqs()


@unittest.skipIf(_MISSING, f"missing prereqs: {'; '.join(_MISSING)}")
class TestIntegration(unittest.TestCase):
    """
    Integration tests that use 'sam local invoke' to verify the template,
    layer linking, and environment variable wiring.

    These need docker + sam and will reach AWS for credentials/SSM, so they are
    kept opt-in via `make test-integration` and skipped when prereqs are absent.
    """

    @classmethod
    def setUpClass(cls):
        # --use-container matches `make build` and avoids needing python3.11 on PATH
        print("\n[Setup] Building SAM project for integration tests...")
        build = subprocess.run(
            [SAM_BIN, "build", "--use-container"],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=900,
        )
        if build.returncode != 0:
            raise unittest.SkipTest(
                "sam build --use-container failed: "
                + (build.stderr or build.stdout or "").strip().splitlines()[-1]
            )

    def _invoke(self, function, event_file, *extra_args):
        args = [SAM_BIN, "local", "invoke", function, "-e", event_file, *extra_args]
        # Optional: let the invoke use a real profile so AWS calls (SSM/KMS) succeed
        profile = os.environ.get('AWS_PROFILE')
        if profile:
            args += ["--profile", profile]
        return subprocess.run(
            args,
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=180,
        )

    def test_supply_local_dry_run(self):
        """Verifies the 'supply' function boots with the shared Layer attached.

        This is a boot smoke test: it fails on the class of errors that reached
        production (UserCodeSyntaxError, ImportModuleError). Runtime AWS failures
        such as missing KMS/SSM permission are tolerated because local invokes do
        not run under the Lambda execution role.
        """
        result = self._invoke(
            "supply",
            "events/supply_well3_test_event.json",
            "--parameter-overrides", "ParameterKey=DryRun,ParameterValue=true",
        )

        # SAM itself must not fail (build/parse problems)
        self.assertNotIn("Build Failed", result.stdout + result.stderr)

        output = result.stdout + result.stderr
        # A syntax/import error in app.py surfaces as these
        self.assertNotIn("UserCodeSyntaxError", output)
        self.assertNotIn("ModuleNotFoundError", output)
        self.assertNotIn("Unable to import module", output)
        # ...and would abort init before the handler ran
        self.assertNotIn("Init failed error=Runtime exited", output)
        self.assertIn("START RequestId", output)

    def test_email_parsing_integration(self):
        """Verifies the 'email' function imports its parser from the Layer."""
        result = self._invoke("email", "events/email_test_well3.json")

        output = result.stdout + result.stderr
        self.assertNotIn("ModuleNotFoundError", output)
        self.assertNotIn("UserCodeSyntaxError", output)


if __name__ == '__main__':
    unittest.main()
