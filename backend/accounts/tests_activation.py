from rest_framework.test import APITestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.core import mail
from django.test import override_settings


class RegistrationActivationTest(APITestCase):
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_register_sends_activation_and_activate_via_api(self):
        url = '/api/v1/accounts/auth/register/'
        payload = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'phone_number': '0755123456',
            'password': 'strongpassword123',
            'password_confirm': 'strongpassword123',
        }
        resp = self.client.post(url, payload, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertIn('message', resp.data)

        # Verify user exists and is active (auto-activation enabled)
        user = User.objects.get(username='newuser')
        self.assertTrue(user.is_active)

        # Ensure email was sent with activation code/link
        self.assertEqual(len(mail.outbox), 1)
        email_body = mail.outbox[0].body
        self.assertIn('Activate', mail.outbox[0].subject)

        # Activate via API using the profile code that's created by signal
        profile = user.profile
        activate_url = f'/api/v1/accounts/auth/{user.username}/activate/'
        resp2 = self.client.post(activate_url, {'code': profile.code}, format='json')
        self.assertEqual(resp2.status_code, 200)

        user.refresh_from_db()
        self.assertTrue(user.is_active)
