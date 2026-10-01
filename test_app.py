import os
import tempfile
import unittest

from app import create_app

KEY = "test-key"
HEADERS = {"X-API-Key": KEY}


class TaskApiTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.environ["TASKFLOW_API_KEY"] = KEY
        self.client = create_app(self.path).test_client()

    def tearDown(self):
        os.remove(self.path)

    def test_health_is_public(self):
        self.assertEqual(self.client.get("/health").status_code, 200)

    def test_missing_key_is_rejected(self):
        self.assertEqual(self.client.get("/tasks").status_code, 401)

    def test_wrong_key_is_rejected(self):
        res = self.client.get("/tasks", headers={"X-API-Key": "nope"})
        self.assertEqual(res.status_code, 401)

    def test_create_and_list(self):
        res = self.client.post(
            "/tasks", json={"title": "Write report"}, headers=HEADERS
        )
        self.assertEqual(res.status_code, 201)
        listed = self.client.get("/tasks", headers=HEADERS).get_json()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["title"], "Write report")

    def test_empty_title_is_rejected(self):
        res = self.client.post("/tasks", json={"title": "   "}, headers=HEADERS)
        self.assertEqual(res.status_code, 400)

    def test_overlong_title_is_rejected(self):
        long_title = "x" * 101
        res = self.client.post(
            "/tasks", json={"title": long_title}, headers=HEADERS
        )
        self.assertEqual(res.status_code, 400)

    def test_sql_injection_payload_is_treated_as_data(self):
        self.client.post("/tasks", json={"title": "alpha"}, headers=HEADERS)
        res = self.client.get("/tasks?q=' OR '1'='1", headers=HEADERS)
        self.assertEqual(res.get_json(), [])

    def _new_task(self):
        res = self.client.post("/tasks", json={"title": "t"}, headers=HEADERS)
        return res.get_json()["id"]

    def test_update_and_delete(self):
        url = f"/tasks/{self._new_task()}"
        res = self.client.patch(url, json={"done": True}, headers=HEADERS)
        self.assertEqual(res.status_code, 200)
        first = self.client.delete(url, headers=HEADERS)
        second = self.client.delete(url, headers=HEADERS)
        self.assertEqual((first.status_code, second.status_code), (204, 404))

    def test_update_requires_boolean(self):
        url = f"/tasks/{self._new_task()}"
        res = self.client.patch(url, json={"done": "yes"}, headers=HEADERS)
        self.assertEqual(res.status_code, 400)


if __name__ == "__main__":
    unittest.main()

