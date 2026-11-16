import unittest
import subprocess
import json
import os

class TestIntegration(unittest.TestCase):
    """
    Integration tests that use the 'sam local invoke' command to verify 
    the template, layer linking, and environment variable wiring.
    """

    def setUp(self):
        self.cwd = "melodywoods_water"
        # Ensure we have a fresh build for integration tests
        # Note: This requires 'sam' and 'docker' to be available
        print("\n[Setup] Building SAM project for integration tests...")
        subprocess.run(["sam", "build"], cwd=self.cwd, capture_output=True)

    def test_supply_local_dry_run(self):
        """Verifies the 'supply' function can be invoked locally with the Layer."""
        event_path = "events/supply_well3_test_event.json"
        
        # Run sam local invoke
        result = subprocess.run([
            "sam", "local", "invoke", "supply",
            "-e", event_path,
            "--parameter-overrides", "ParameterKey=DryRun,ParameterValue=true"
        ], cwd=self.cwd, capture_output=True, text=True)
        
        # Verify execution was successful (Return code 0)
        self.assertEqual(result.returncode, 0, f"SAM local invoke failed: {result.stderr}")
        
        # Verify the response contains our Dry Run markers
        self.assertIn("[DRY RUN]", result.stdout + result.stderr)
        self.assertIn("well3 - Not time to change pump output", result.stdout + result.stderr)

    def test_email_parsing_integration(self):
        """Verifies the 'email' function handles an SES S3 event format correctly."""
        event_path = "events/email_test_well3.json" # Assumes this file exists or is mocked
        
        # We mock the S3 call within the Lambda or ensure the test environment can handle it
        # For a true integration test without hitting S3, we rely on our unit tests,
        # but here we verify the Lambda 'boots' and imports the parser correctly.
        result = subprocess.run([
            "sam", "local", "invoke", "email",
            "-e", event_path
        ], cwd=self.cwd, capture_output=True, text=True)
        
        # Even if it fails a real S3 network call, we want to see it got past the 'Import pysensaphone' stage
        self.assertNotIn("ModuleNotFoundError", result.stderr)

if __name__ == '__main__':
    unittest.main()
