#!/usr/bin/env python3
"""Locust file for TinyInsta performance testing.

Tests the /api/timeline endpoint with different numbers of concurrent users.
"""
import os
import random
import time
from locust import HttpUser, task, between, events
from datetime import datetime

# Configuration
import subprocess
try:
    PROJECT_ID = subprocess.check_output("gcloud config get-value project", shell=True).decode().strip()
    DEFAULT_URL = f"https://{PROJECT_ID}.nw.r.appspot.com/"
except:
    DEFAULT_URL = 'https://tiny-494020.nw.r.appspot.com/'
TINYINSTA_BASE_URL = os.getenv('TINYINSTA_URL', DEFAULT_URL)

class TinyInstaUser(HttpUser):
    """Simulates a TinyInsta user fetching timeline."""
    
    wait_time = between(1, 2)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_id = random.randint(1, 1000)  # Will be set dynamically
    
    @task
    def get_timeline(self):
        """Fetch timeline for the current user."""
        username = f"user{self.user_id}"
        start_time = time.time()
        try:
            response = self.client.get(
                "/api/timeline",
                params={"user": username, "limit": 20},
                timeout=30
            )
            elapsed = (time.time() - start_time) * 1000  # Convert to ms
            if response.status_code == 200:
                # Success - response will be captured by Locust
                response.elapsed.total_seconds()
            else:
                response.failure(f"Got status code {response.status_code}")
        except Exception as e:
            response.failure(str(e))

    def on_start(self):
        """Called when user session starts."""
        self.user_id = random.randint(1, 1000)


# Hooks for additional logging
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when load test starts."""
    print(f"\n[{datetime.now().isoformat()}] Load test starting...")
    print(f"Target: {environment.host}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when load test stops."""
    print(f"\n[{datetime.now().isoformat()}] Load test completed.")
