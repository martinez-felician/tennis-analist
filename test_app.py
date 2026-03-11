"""
Tests for Tennis Analyst Flask backend.
Uses Flask's built-in test client — no external server needed.
Run with: python -m pytest test_app.py -v
"""

import json
import os
import tempfile
import unittest

import app as flask_app


class BaseTestCase(unittest.TestCase):
    def setUp(self):
        # Fresh isolated DB for every test — no lock contention
        self._db_fd, self._db_path = tempfile.mkstemp(suffix='.db')
        flask_app.DB_PATH = self._db_path
        flask_app.init_db()

        flask_app.app.config['TESTING'] = True
        flask_app.app.config['SECRET_KEY'] = 'test-secret'
        self.client = flask_app.app.test_client()

    def tearDown(self):
        try:
            os.close(self._db_fd)
        except OSError:
            pass
        try:
            os.unlink(self._db_path)
        except OSError:
            pass  # Windows may keep the file locked briefly; temp dir cleans up on reboot

    def _register(self, username='testuser', email='test@example.com', password='pass123'):
        return self.client.post('/api/auth/register', json={
            'username': username, 'email': email, 'password': password,
        })

    def _login(self, email='test@example.com', password='pass123'):
        return self.client.post('/api/auth/login', json={
            'email': email, 'password': password,
        })


# ── Auth ──────────────────────────────────────────────────────────────────────

class TestRegister(BaseTestCase):
    def test_register_success(self):
        res = self._register()
        self.assertEqual(res.status_code, 201)
        self.assertIn('created', res.get_json()['message'].lower())

    def test_register_duplicate(self):
        self._register()
        res = self._register()
        self.assertEqual(res.status_code, 409)

    def test_register_missing_fields(self):
        res = self.client.post('/api/auth/register', json={'username': 'x'})
        self.assertEqual(res.status_code, 400)

    def test_register_short_username(self):
        res = self._register(username='a')
        self.assertEqual(res.status_code, 400)

    def test_register_short_password(self):
        res = self._register(password='abc')
        self.assertEqual(res.status_code, 400)


class TestLogin(BaseTestCase):
    def setUp(self):
        super().setUp()
        self._register()

    def test_login_success(self):
        res = self._login()
        self.assertEqual(res.status_code, 200)
        self.assertIn('username', res.get_json())

    def test_login_wrong_password(self):
        res = self._login(password='wrongpass')
        self.assertEqual(res.status_code, 401)

    def test_login_unknown_email(self):
        res = self._login(email='nobody@example.com')
        self.assertEqual(res.status_code, 401)


class TestMe(BaseTestCase):
    def test_me_unauthenticated(self):
        res = self.client.get('/api/auth/me')
        self.assertEqual(res.status_code, 401)

    def test_me_authenticated(self):
        self._register()
        self._login()
        res = self.client.get('/api/auth/me')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['authenticated'])
        self.assertIn('is_premium', data)
        self.assertFalse(data['is_premium'])

    def test_me_after_logout(self):
        self._register()
        self._login()
        self.client.post('/api/auth/logout')
        res = self.client.get('/api/auth/me')
        self.assertEqual(res.status_code, 401)


# ── Matches ───────────────────────────────────────────────────────────────────

class TestMatches(BaseTestCase):
    def setUp(self):
        super().setUp()
        self._register()
        self._login()

    def _save_match(self, won=True):
        return self.client.post('/api/matches', json={
            'config': {'playerName': 'Alice', 'sets': 3},
            'stats':  {'ace': 3, 'df': 1, 'fh-win': 5, 'bh-ue': 2},
            'result': {'won': won, 'player1Sets': 2, 'player2Sets': 1},
        })

    def test_save_match(self):
        res = self._save_match()
        self.assertEqual(res.status_code, 201)

    def test_get_matches_empty(self):
        res = self.client.get('/api/matches')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json(), [])

    def test_get_matches_returns_saved(self):
        self._save_match(won=True)
        self._save_match(won=False)
        res = self.client.get('/api/matches')
        self.assertEqual(len(res.get_json()), 2)

    def test_get_matches_requires_auth(self):
        self.client.post('/api/auth/logout')
        res = self.client.get('/api/matches')
        self.assertEqual(res.status_code, 401)

    def test_save_match_requires_auth(self):
        self.client.post('/api/auth/logout')
        res = self._save_match()
        self.assertEqual(res.status_code, 401)

    def test_matches_json_fields_present(self):
        self._save_match()
        match = self.client.get('/api/matches').get_json()[0]
        for field in ('id', 'config', 'stats', 'result', 'played_at'):
            self.assertIn(field, match)

    def test_matches_ordered_newest_first(self):
        self._save_match(won=True)
        self._save_match(won=False)
        data = self.client.get('/api/matches').get_json()
        # Second saved match (won=False) should appear first (newest)
        self.assertFalse(json.loads(data[0]['result'])['won'])

    def test_matches_isolated_per_user(self):
        self._save_match()
        # Second user should see an empty history
        self._register(username='user2', email='user2@example.com')
        self._login(email='user2@example.com')
        self.assertEqual(self.client.get('/api/matches').get_json(), [])


# ── Billing (no Stripe keys configured) ──────────────────────────────────────

class TestBillingUnconfigured(BaseTestCase):
    def setUp(self):
        super().setUp()
        self._register()
        self._login()

    def test_checkout_returns_503_when_unconfigured(self):
        res = self.client.post('/api/billing/checkout')
        self.assertEqual(res.status_code, 503)

    def test_portal_returns_503_or_404_without_customer(self):
        res = self.client.post('/api/billing/portal')
        self.assertIn(res.status_code, (404, 503))

    def test_checkout_requires_auth(self):
        self.client.post('/api/auth/logout')
        res = self.client.post('/api/billing/checkout')
        self.assertEqual(res.status_code, 401)

    def test_portal_requires_auth(self):
        self.client.post('/api/auth/logout')
        res = self.client.post('/api/billing/portal')
        self.assertEqual(res.status_code, 401)


# ── DB schema — premium columns ───────────────────────────────────────────────

class TestPremiumSchema(BaseTestCase):
    def test_new_user_is_not_premium(self):
        self._register()
        self._login()
        data = self.client.get('/api/auth/me').get_json()
        self.assertFalse(data['is_premium'])
        self.assertIsNone(data['subscription_status'])

    def test_premium_flag_can_be_set(self):
        self._register()
        conn = flask_app.get_db()
        conn.execute(
            "UPDATE users SET is_premium=1, subscription_status='active' WHERE email='test@example.com'"
        )
        conn.commit()
        conn.close()
        self._login()
        data = self.client.get('/api/auth/me').get_json()
        self.assertTrue(data['is_premium'])
        self.assertEqual(data['subscription_status'], 'active')


# ── Static routes ─────────────────────────────────────────────────────────────

class TestStaticRoutes(BaseTestCase):
    def test_home(self):
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_login_page(self):
        self.assertEqual(self.client.get('/login').status_code, 200)

    def test_profile_page(self):
        self.assertEqual(self.client.get('/profile').status_code, 200)

    def test_manifest(self):
        self.assertEqual(self.client.get('/manifest.json').status_code, 200)

    def test_service_worker(self):
        self.assertEqual(self.client.get('/sw.js').status_code, 200)


if __name__ == '__main__':
    unittest.main(verbosity=2)
