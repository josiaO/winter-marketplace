from django.contrib.auth import get_user_model
User = get_user_model()

email = 'agent@example.com'
password = os.getenv('AGENT_PASSWORD', 'agentpassword')

try:
    user = User.objects.get(email=email)
    user.set_password(password)
    user.role = 'agent'
    user.save()
    print(f"Updated user {email}")
except User.DoesNotExist:
    User.objects.create_user(email=email, password=password, role='agent', first_name='John', last_name='Agent')
    print(f"Created user {email}")
