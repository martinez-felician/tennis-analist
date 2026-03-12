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


# ── Profile update ────────────────────────────────────────────────────────────

class TestProfileUpdate(BaseTestCase):
    def setUp(self):
        super().setUp()
        self._register()
        self._login()

    def test_update_username(self):
        res = self.client.put('/api/auth/profile', json={
            'username': 'newname', 'first_name': 'John', 'last_name': 'Doe',
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['username'], 'newname')
        self.assertEqual(data['first_name'], 'John')
        self.assertEqual(data['last_name'], 'Doe')

    def test_update_reflects_in_me(self):
        self.client.put('/api/auth/profile', json={
            'username': 'updated', 'first_name': 'Jane', 'last_name': 'Smith',
        })
        me = self.client.get('/api/auth/me').get_json()
        self.assertEqual(me['username'], 'updated')
        self.assertEqual(me['first_name'], 'Jane')
        self.assertEqual(me['last_name'], 'Smith')

    def test_update_requires_auth(self):
        self.client.post('/api/auth/logout')
        res = self.client.put('/api/auth/profile', json={'username': 'x'})
        self.assertEqual(res.status_code, 401)

    def test_update_duplicate_username(self):
        self._register(username='other', email='other@example.com')
        res = self.client.put('/api/auth/profile', json={'username': 'other'})
        self.assertEqual(res.status_code, 409)

    def test_update_short_username(self):
        res = self.client.put('/api/auth/profile', json={'username': 'x'})
        self.assertEqual(res.status_code, 400)

    def test_update_keeps_username_when_omitted(self):
        res = self.client.put('/api/auth/profile', json={
            'username': '', 'first_name': 'Only', 'last_name': 'Name',
        })
        self.assertEqual(res.status_code, 200)
        me = self.client.get('/api/auth/me').get_json()
        self.assertEqual(me['username'], 'testuser')  # original username kept

    def test_me_returns_first_last_name_fields(self):
        me = self.client.get('/api/auth/me').get_json()
        self.assertIn('first_name', me)
        self.assertIn('last_name', me)


# ── Change password ───────────────────────────────────────────────────────────

class TestChangePassword(BaseTestCase):
    def setUp(self):
        super().setUp()
        self._register()
        self._login()

    def test_change_password_success(self):
        res = self.client.post('/api/auth/change-password', json={
            'current_password': 'pass123', 'new_password': 'newpass456',
        })
        self.assertEqual(res.status_code, 200)

    def test_new_password_works_for_login(self):
        self.client.post('/api/auth/change-password', json={
            'current_password': 'pass123', 'new_password': 'newpass456',
        })
        self.client.post('/api/auth/logout')
        res = self._login(password='newpass456')
        self.assertEqual(res.status_code, 200)

    def test_old_password_rejected_after_change(self):
        self.client.post('/api/auth/change-password', json={
            'current_password': 'pass123', 'new_password': 'newpass456',
        })
        self.client.post('/api/auth/logout')
        res = self._login(password='pass123')
        self.assertEqual(res.status_code, 401)

    def test_change_password_wrong_current(self):
        res = self.client.post('/api/auth/change-password', json={
            'current_password': 'wrongpass', 'new_password': 'newpass456',
        })
        self.assertEqual(res.status_code, 401)

    def test_change_password_too_short(self):
        res = self.client.post('/api/auth/change-password', json={
            'current_password': 'pass123', 'new_password': 'abc',
        })
        self.assertEqual(res.status_code, 400)

    def test_change_password_missing_fields(self):
        res = self.client.post('/api/auth/change-password', json={
            'current_password': 'pass123',
        })
        self.assertEqual(res.status_code, 400)

    def test_change_password_requires_auth(self):
        self.client.post('/api/auth/logout')
        res = self.client.post('/api/auth/change-password', json={
            'current_password': 'pass123', 'new_password': 'newpass456',
        })
        self.assertEqual(res.status_code, 401)


# ── Match content & new fields ────────────────────────────────────────────────

class TestMatchContent(BaseTestCase):
    def setUp(self):
        super().setUp()
        self._register()
        self._login()

    def _save_full_match(self):
        return self.client.post('/api/matches', json={
            'config': {
                'playerName':   'Alice',
                'opponentName': 'Rafael',
                'clubName':     'Royal TC',
                'phase':        'semis',
                'sets':         3,
            },
            'stats':  {'ace': 5, 'df': 2, 'fh-win': 8, 'bh-ue': 3, 'fh-ue': 1},
            'result': {'won': True, 'player1Sets': 2, 'player2Sets': 0},
        })

    def test_new_config_fields_persisted(self):
        self._save_full_match()
        match = self.client.get('/api/matches').get_json()[0]
        config = json.loads(match['config'])
        self.assertEqual(config['opponentName'], 'Rafael')
        self.assertEqual(config['clubName'],     'Royal TC')
        self.assertEqual(config['phase'],        'semis')

    def test_stats_values_persisted(self):
        self._save_full_match()
        match = self.client.get('/api/matches').get_json()[0]
        stats = json.loads(match['stats'])
        self.assertEqual(stats['ace'],   5)
        self.assertEqual(stats['df'],    2)
        self.assertEqual(stats['fh-win'], 8)

    def test_result_won_flag_persisted(self):
        self.client.post('/api/matches', json={
            'config': {}, 'stats': {},
            'result': {'won': False, 'player1Sets': 0, 'player2Sets': 2},
        })
        match = self.client.get('/api/matches').get_json()[0]
        result = json.loads(match['result'])
        self.assertFalse(result['won'])

    def test_save_match_with_empty_stats(self):
        res = self.client.post('/api/matches', json={
            'config': {}, 'stats': {}, 'result': {},
        })
        self.assertEqual(res.status_code, 201)

    def test_config_and_stats_are_valid_json_strings(self):
        self._save_full_match()
        match = self.client.get('/api/matches').get_json()[0]
        # Should not raise
        self.assertIsInstance(json.loads(match['config']), dict)
        self.assertIsInstance(json.loads(match['stats']),  dict)
        self.assertIsInstance(json.loads(match['result']), dict)

    def test_played_at_is_present(self):
        self._save_full_match()
        match = self.client.get('/api/matches').get_json()[0]
        self.assertIsNotNone(match['played_at'])
        self.assertNotEqual(match['played_at'], '')

    def test_multiple_matches_all_returned(self):
        for i in range(5):
            self.client.post('/api/matches', json={
                'config': {'playerName': f'Player{i}'},
                'stats':  {'ace': i},
                'result': {'won': i % 2 == 0},
            })
        matches = self.client.get('/api/matches').get_json()
        self.assertEqual(len(matches), 5)

    def test_match_id_increments(self):
        self._save_full_match()
        self._save_full_match()
        matches = self.client.get('/api/matches').get_json()
        self.assertGreater(matches[0]['id'], matches[1]['id'])  # newest first


# ── Register edge cases ───────────────────────────────────────────────────────

class TestRegisterEdgeCases(BaseTestCase):
    def test_duplicate_email_rejected(self):
        self._register(username='user1', email='same@example.com')
        res = self._register(username='user2', email='same@example.com')
        self.assertEqual(res.status_code, 409)

    def test_duplicate_username_rejected(self):
        self._register(username='same', email='email1@example.com')
        res = self._register(username='same', email='email2@example.com')
        self.assertEqual(res.status_code, 409)

    def test_email_stored_lowercase(self):
        self._register(email='Upper@Example.COM')
        res = self._login(email='upper@example.com')
        self.assertEqual(res.status_code, 200)

    def test_register_empty_body(self):
        res = self.client.post('/api/auth/register', json={})
        self.assertEqual(res.status_code, 400)

    def test_new_user_has_empty_name_fields(self):
        self._register()
        self._login()
        me = self.client.get('/api/auth/me').get_json()
        self.assertEqual(me['first_name'], '')
        self.assertEqual(me['last_name'],  '')


# ── Logout & session ──────────────────────────────────────────────────────────

class TestSession(BaseTestCase):
    def test_logout_clears_session(self):
        self._register()
        self._login()
        self.client.post('/api/auth/logout')
        res = self.client.get('/api/auth/me')
        self.assertEqual(res.status_code, 401)

    def test_logout_always_200(self):
        # Logging out without being logged in should still succeed
        res = self.client.post('/api/auth/logout')
        self.assertEqual(res.status_code, 200)

    def test_matches_blocked_after_logout(self):
        self._register()
        self._login()
        self.client.post('/api/matches', json={'config': {}, 'stats': {}, 'result': {}})
        self.client.post('/api/auth/logout')
        res = self.client.get('/api/matches')
        self.assertEqual(res.status_code, 401)


# ── Webhook ───────────────────────────────────────────────────────────────────

class TestWebhook(BaseTestCase):
    def test_webhook_invalid_signature_returns_400(self):
        res = self.client.post(
            '/api/billing/webhook',
            data=b'{"type":"customer.subscription.created"}',
            headers={'Content-Type': 'application/json', 'Stripe-Signature': 'bad-sig'},
        )
        self.assertEqual(res.status_code, 400)

    def test_webhook_no_signature_returns_400(self):
        res = self.client.post(
            '/api/billing/webhook',
            data=b'{}',
            headers={'Content-Type': 'application/json'},
        )
        self.assertEqual(res.status_code, 400)


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

    def test_home_page_route(self):
        self.assertEqual(self.client.get('/home').status_code, 200)

    def test_css_served(self):
        self.assertEqual(self.client.get('/style.css').status_code, 200)

    def test_js_served(self):
        self.assertEqual(self.client.get('/script.js').status_code, 200)

    def test_icon_served(self):
        self.assertEqual(self.client.get('/icon.svg').status_code, 200)

    def test_unknown_route_returns_404(self):
        self.assertEqual(self.client.get('/does-not-exist').status_code, 404)


if __name__ == '__main__':
    unittest.main(verbosity=2)
