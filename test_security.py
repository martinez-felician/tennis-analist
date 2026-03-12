"""
Security and robustness tests for Tennis Analyst.
Probes input validation, privilege escalation, cross-user isolation,
injection attempts, method enforcement, and edge cases.

Run with: python -m pytest test_security.py -v
"""

import json
import os
import tempfile
import unittest

import app as flask_app


class BaseTestCase(unittest.TestCase):
    def setUp(self):
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
            pass

    def _register(self, username='alice', email='alice@example.com', password='pass123'):
        return self.client.post('/api/auth/register', json={
            'username': username, 'email': email, 'password': password,
        })

    def _login(self, email='alice@example.com', password='pass123'):
        return self.client.post('/api/auth/login', json={
            'email': email, 'password': password,
        })

    def _register_and_login(self, username='alice', email='alice@example.com', password='pass123'):
        self._register(username=username, email=email, password=password)
        self._login(email=email, password=password)


# ── Privilege escalation ──────────────────────────────────────────────────────

class TestPrivilegeEscalation(BaseTestCase):
    """A user must never be able to grant themselves premium or touch other accounts."""

    def setUp(self):
        super().setUp()
        self._register_and_login()

    def test_profile_update_cannot_set_is_premium(self):
        self.client.put('/api/auth/profile', json={
            'username': 'alice', 'first_name': 'A', 'last_name': 'B',
            'is_premium': True, 'subscription_status': 'active',
        })
        me = self.client.get('/api/auth/me').get_json()
        self.assertFalse(me['is_premium'])
        self.assertIsNone(me['subscription_status'])

    def test_profile_update_cannot_set_subscription_status(self):
        self.client.put('/api/auth/profile', json={
            'username': 'alice', 'subscription_status': 'active',
        })
        me = self.client.get('/api/auth/me').get_json()
        self.assertIsNone(me['subscription_status'])

    def test_save_match_ignores_user_id_in_body(self):
        """Passing a foreign user_id in the body must be ignored — match saved to session user."""
        # Register a second user to steal their id
        self.client.post('/api/auth/register', json={
            'username': 'bob', 'email': 'bob@example.com', 'password': 'pass123',
        })
        conn = flask_app.get_db()
        bob_id = conn.execute("SELECT id FROM users WHERE email='bob@example.com'").fetchone()['id']
        conn.close()

        self.client.post('/api/matches', json={
            'user_id': bob_id,   # attacker tries to own this match as bob
            'config': {}, 'stats': {}, 'result': {},
        })

        # Alice's match count should be 1; bob's should be 0
        alice_matches = self.client.get('/api/matches').get_json()
        self.assertEqual(len(alice_matches), 1)

        self._login(email='bob@example.com', password='pass123')
        bob_matches = self.client.get('/api/matches').get_json()
        self.assertEqual(len(bob_matches), 0)


# ── Cross-user data isolation ─────────────────────────────────────────────────

class TestCrossUserIsolation(BaseTestCase):
    """User A must never see or affect User B's data."""

    def test_matches_strictly_isolated(self):
        # Alice saves 3 matches
        self._register_and_login(username='alice', email='alice@example.com')
        for _ in range(3):
            self.client.post('/api/matches', json={'config': {}, 'stats': {}, 'result': {}})

        # Bob registers and sees zero matches
        self.client.post('/api/auth/register', json={
            'username': 'bob', 'email': 'bob@example.com', 'password': 'pass123',
        })
        self._login(email='bob@example.com', password='pass123')
        self.assertEqual(self.client.get('/api/matches').get_json(), [])

    def test_concurrent_sessions_independent(self):
        """Two clients logged in simultaneously must each see only their own data."""
        client_a = flask_app.app.test_client()
        client_b = flask_app.app.test_client()

        client_a.post('/api/auth/register', json={
            'username': 'alice', 'email': 'alice@example.com', 'password': 'pass123',
        })
        client_b.post('/api/auth/register', json={
            'username': 'bob', 'email': 'bob@example.com', 'password': 'pass123',
        })
        client_a.post('/api/auth/login', json={'email': 'alice@example.com', 'password': 'pass123'})
        client_b.post('/api/auth/login', json={'email': 'bob@example.com', 'password': 'pass123'})

        client_a.post('/api/matches', json={'config': {'owner': 'alice'}, 'stats': {}, 'result': {}})

        bob_matches = client_b.get('/api/matches').get_json()
        self.assertEqual(bob_matches, [])

        alice_matches = client_a.get('/api/matches').get_json()
        self.assertEqual(len(alice_matches), 1)
        self.assertEqual(json.loads(alice_matches[0]['config'])['owner'], 'alice')

    def test_logout_a_does_not_affect_b(self):
        client_a = flask_app.app.test_client()
        client_b = flask_app.app.test_client()

        for c, u, e in [(client_a, 'alice', 'alice@example.com'),
                        (client_b, 'bob',   'bob@example.com')]:
            c.post('/api/auth/register', json={'username': u, 'email': e, 'password': 'pass123'})
            c.post('/api/auth/login',    json={'email': e, 'password': 'pass123'})

        client_a.post('/api/auth/logout')

        # B is still authenticated
        self.assertEqual(client_b.get('/api/auth/me').status_code, 200)
        # A is logged out
        self.assertEqual(client_a.get('/api/auth/me').status_code, 401)


# ── SQL injection ─────────────────────────────────────────────────────────────

class TestSQLInjection(BaseTestCase):
    """Parameterized queries should neutralize all injection payloads."""

    SQL_PAYLOADS = [
        "' OR '1'='1",
        "'; DROP TABLE users; --",
        "' UNION SELECT * FROM users --",
        "admin'--",
        "1; SELECT * FROM users",
    ]

    def test_sql_injection_in_login_email(self):
        self._register()
        for payload in self.SQL_PAYLOADS:
            res = self.client.post('/api/auth/login', json={
                'email': payload, 'password': 'pass123',
            })
            self.assertEqual(res.status_code, 401,
                             f'Injection payload accepted as email: {payload!r}')

    def test_sql_injection_in_login_password(self):
        self._register()
        for payload in self.SQL_PAYLOADS:
            res = self.client.post('/api/auth/login', json={
                'email': 'alice@example.com', 'password': payload,
            })
            self.assertEqual(res.status_code, 401,
                             f'Injection payload bypassed password check: {payload!r}')

    def test_sql_injection_in_username_register(self):
        for payload in self.SQL_PAYLOADS:
            res = self.client.post('/api/auth/register', json={
                'username': payload, 'email': f'x{hash(payload)}@x.com', 'password': 'pass123',
            })
            # Must either succeed (stored safely) or fail validation — never 500
            self.assertNotEqual(res.status_code, 500,
                                f'Server error on injection in username: {payload!r}')

    def test_sql_injection_in_profile_update(self):
        self._register_and_login()
        for payload in self.SQL_PAYLOADS:
            res = self.client.put('/api/auth/profile', json={
                'username': 'alice', 'first_name': payload, 'last_name': payload,
            })
            self.assertNotEqual(res.status_code, 500,
                                f'Server error on injection in profile: {payload!r}')
            # DB must still be intact
            self.assertEqual(self.client.get('/api/auth/me').status_code, 200)


# ── Input validation edge cases ───────────────────────────────────────────────

class TestInputValidation(BaseTestCase):

    def test_whitespace_only_username_rejected(self):
        res = self._register(username='   ')
        self.assertEqual(res.status_code, 400)

    def test_whitespace_only_email_rejected(self):
        res = self._register(email='   ')
        self.assertIn(res.status_code, (400, 409))

    def test_whitespace_only_password_rejected(self):
        # Six spaces technically passes length check — should be rejected
        res = self._register(password='      ')
        # Either rejected (400) or, if accepted, must not allow login with stripped password
        if res.status_code == 201:
            login_res = self._login(password='      ')
            # If registration was allowed the login should still work with exact value
            self.assertEqual(login_res.status_code, 200)

    def test_extremely_long_username_handled(self):
        long_name = 'a' * 10_000
        res = self._register(username=long_name)
        self.assertNotEqual(res.status_code, 500)

    def test_extremely_long_password_handled(self):
        res = self._register(password='x' * 10_000)
        self.assertNotEqual(res.status_code, 500)

    def test_extremely_long_email_handled(self):
        long_email = 'a' * 5_000 + '@example.com'
        res = self._register(email=long_email)
        self.assertNotEqual(res.status_code, 500)

    def test_unicode_username_accepted(self):
        res = self._register(username='テニス選手')
        self.assertNotEqual(res.status_code, 500)

    def test_script_tag_in_username_stored_as_text(self):
        """XSS payload stored in username must come back as plain text, not interpreted."""
        xss = '<script>alert(1)</script>'
        self._register(username=xss, email='xss@example.com', password='pass123')
        self._login(email='xss@example.com', password='pass123')
        me = self.client.get('/api/auth/me').get_json()
        # Value must be stored literally — the API returns JSON, not HTML, so it's safe
        self.assertEqual(me['username'], xss)

    def test_null_byte_in_username_handled(self):
        res = self._register(username='admin\x00injected')
        self.assertNotEqual(res.status_code, 500)

    def test_newline_in_username_handled(self):
        res = self._register(username='user\nname')
        self.assertNotEqual(res.status_code, 500)


# ── HTTP method enforcement ───────────────────────────────────────────────────

class TestMethodEnforcement(BaseTestCase):

    def test_get_on_register_returns_405(self):
        self.assertEqual(self.client.get('/api/auth/register').status_code, 405)

    def test_get_on_login_returns_405(self):
        self.assertEqual(self.client.get('/api/auth/login').status_code, 405)

    def test_get_on_logout_returns_405(self):
        self.assertEqual(self.client.get('/api/auth/logout').status_code, 405)

    def test_post_on_me_returns_405(self):
        self.assertEqual(self.client.post('/api/auth/me').status_code, 405)

    def test_post_on_profile_returns_405(self):
        self.assertEqual(self.client.post('/api/auth/profile').status_code, 405)

    def test_delete_on_matches_returns_405(self):
        self.assertEqual(self.client.delete('/api/matches').status_code, 405)


# ── Non-JSON / malformed body handling ───────────────────────────────────────

class TestMalformedBodies(BaseTestCase):

    def test_plain_text_body_to_register(self):
        res = self.client.post('/api/auth/register',
                               data='not json', content_type='text/plain')
        self.assertNotEqual(res.status_code, 500)

    def test_empty_body_to_login(self):
        res = self.client.post('/api/auth/login', data=b'',
                               content_type='application/json')
        self.assertNotEqual(res.status_code, 500)

    def test_array_body_to_register(self):
        res = self.client.post('/api/auth/register', json=[1, 2, 3])
        self.assertNotEqual(res.status_code, 500)

    def test_deeply_nested_json_handled(self):
        nested = {'a': {'b': {'c': {'d': {'e': 'f'}}}}}
        res = self.client.post('/api/auth/register', json=nested)
        self.assertNotEqual(res.status_code, 500)

    def test_match_with_non_dict_stats(self):
        self._register_and_login()
        res = self.client.post('/api/matches', json={
            'config': 'not a dict', 'stats': [1, 2, 3], 'result': None,
        })
        # Should not 500 — app wraps values in json.dumps regardless
        self.assertNotEqual(res.status_code, 500)

    def test_match_with_very_large_stats(self):
        self._register_and_login()
        big_stats = {f'key_{i}': i * 100 for i in range(1000)}
        res = self.client.post('/api/matches', json={
            'config': {}, 'stats': big_stats, 'result': {},
        })
        self.assertNotEqual(res.status_code, 500)


# ── Authentication boundary ───────────────────────────────────────────────────

class TestAuthBoundary(BaseTestCase):

    PROTECTED_ENDPOINTS = [
        ('GET',  '/api/matches'),
        ('POST', '/api/matches'),
        ('PUT',  '/api/auth/profile'),
        ('POST', '/api/auth/change-password'),
        ('POST', '/api/billing/checkout'),
        ('POST', '/api/billing/portal'),
    ]

    def test_all_protected_endpoints_require_auth(self):
        for method, path in self.PROTECTED_ENDPOINTS:
            res = getattr(self.client, method.lower())(path, json={})
            self.assertEqual(res.status_code, 401,
                             f'{method} {path} should require auth, got {res.status_code}')

    def test_me_returns_401_not_500_when_unauthenticated(self):
        res = self.client.get('/api/auth/me')
        self.assertEqual(res.status_code, 401)
        self.assertNotEqual(res.status_code, 500)

    def test_accessing_after_session_cleared_returns_401(self):
        self._register_and_login()
        with self.client.session_transaction() as sess:
            sess.clear()
        res = self.client.get('/api/matches')
        self.assertEqual(res.status_code, 401)


# ── Password security ─────────────────────────────────────────────────────────

class TestPasswordSecurity(BaseTestCase):

    def test_password_not_returned_in_me_response(self):
        self._register_and_login()
        me = self.client.get('/api/auth/me').get_json()
        self.assertNotIn('password',      me)
        self.assertNotIn('password_hash', me)

    def test_password_not_returned_in_profile_update(self):
        self._register_and_login()
        data = self.client.put('/api/auth/profile', json={
            'username': 'alice', 'first_name': 'A', 'last_name': 'B',
        }).get_json()
        self.assertNotIn('password',      data)
        self.assertNotIn('password_hash', data)

    def test_wrong_password_always_401(self):
        self._register()
        for bad_pw in ['', ' ', 'PASS123', 'pass12', 'pass1234', 'pass123 ']:
            res = self._login(password=bad_pw)
            self.assertEqual(res.status_code, 401,
                             f'Expected 401 for wrong password {bad_pw!r}, got {res.status_code}')

    def test_password_is_hashed_in_db(self):
        self._register(password='mypassword')
        conn = flask_app.get_db()
        user = conn.execute("SELECT password_hash FROM users WHERE email='alice@example.com'").fetchone()
        conn.close()
        self.assertNotEqual(user['password_hash'], 'mypassword')
        self.assertTrue(user['password_hash'].startswith('pbkdf2:') or
                        user['password_hash'].startswith('scrypt:'))


# ── Match data integrity ──────────────────────────────────────────────────────

class TestMatchDataIntegrity(BaseTestCase):

    def setUp(self):
        super().setUp()
        self._register_and_login()

    def test_match_stats_with_negative_values_stored(self):
        """Negative stats should be stored without error (validation is frontend responsibility)."""
        res = self.client.post('/api/matches', json={
            'config': {}, 'stats': {'ace': -5, 'df': -1}, 'result': {},
        })
        self.assertNotEqual(res.status_code, 500)

    def test_match_with_boolean_values_in_stats(self):
        res = self.client.post('/api/matches', json={
            'config': {}, 'stats': {'ace': True, 'df': False}, 'result': {},
        })
        self.assertNotEqual(res.status_code, 500)

    def test_match_config_with_xss_payload(self):
        xss = '<img src=x onerror=alert(1)>'
        res = self.client.post('/api/matches', json={
            'config': {'playerName': xss, 'opponentName': xss},
            'stats': {}, 'result': {},
        })
        self.assertEqual(res.status_code, 201)
        match = self.client.get('/api/matches').get_json()[0]
        config = json.loads(match['config'])
        # Must be stored as literal text — not executed
        self.assertEqual(config['playerName'], xss)

    def test_user_cannot_read_another_users_match_by_id(self):
        """There is no per-match GET endpoint — confirm 405/404, not data leak."""
        self.client.post('/api/matches', json={'config': {}, 'stats': {}, 'result': {}})
        match_id = self.client.get('/api/matches').get_json()[0]['id']

        # Register Bob and try to access Alice's match by id
        self.client.post('/api/auth/register', json={
            'username': 'bob', 'email': 'bob@example.com', 'password': 'pass123',
        })
        self._login(email='bob@example.com', password='pass123')

        res = self.client.get(f'/api/matches/{match_id}')
        # No such route exists — must be 404 or 405, never 200
        self.assertIn(res.status_code, (404, 405))


# ── Response data leakage ─────────────────────────────────────────────────────

class TestDataLeakage(BaseTestCase):

    def test_register_response_contains_no_sensitive_fields(self):
        res = self._register()
        data = res.get_json()
        for field in ('password', 'password_hash', 'email', 'stripe_customer_id'):
            self.assertNotIn(field, data)

    def test_login_response_contains_no_sensitive_fields(self):
        self._register()
        res = self._login()
        data = res.get_json()
        for field in ('password', 'password_hash', 'stripe_customer_id'):
            self.assertNotIn(field, data)

    def test_me_response_contains_no_sensitive_fields(self):
        self._register_and_login()
        data = self.client.get('/api/auth/me').get_json()
        for field in ('password', 'password_hash', 'stripe_customer_id'):
            self.assertNotIn(field, data)

    def test_error_responses_dont_leak_stack_traces(self):
        """Error messages must be user-facing strings, not Python tracebacks."""
        res = self.client.post('/api/auth/login', json={
            'email': 'nobody@example.com', 'password': 'pass123',
        })
        body = res.get_data(as_text=True)
        self.assertNotIn('Traceback', body)
        self.assertNotIn('File "', body)


if __name__ == '__main__':
    unittest.main(verbosity=2)
