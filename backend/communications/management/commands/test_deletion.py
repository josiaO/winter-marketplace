from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from communications.models import Conversation, Message
from rest_framework.test import APIRequestFactory, force_authenticate
from communications.views import ConversationViewSet

User = get_user_model()

class Command(BaseCommand):
    help = 'Test conversation deletion logic'

    def handle(self, *args, **options):
        # Setup
        user = User.objects.create_user(username='testuser', password='password')
        agent = User.objects.create_user(username='testagent', password='password')
        
        conversation = Conversation.objects.create(user=user, agent=agent)
        Message.objects.create(conversation=conversation, sender=agent, text="Hello")
        
        self.stdout.write(f"Created conversation {conversation.id} for user {user.id}")
        
        # Test Hiding
        view = ConversationViewSet.as_view({'post': 'clear_history'})
        factory = APIRequestFactory()
        request = factory.post(f'/conversations/{conversation.id}/clear_history/')
        force_authenticate(request, user=user)
        response = view(request, pk=conversation.id)
        
        self.stdout.write(f"Clear History Response: {response.status_code}")
        
        # Verify DB
        conversation.refresh_from_db()
        is_hidden = user in conversation.hidden_by.all()
        self.stdout.write(f"Is user in hidden_by? {is_hidden}")
        
        # Test Listing
        view_list = ConversationViewSet.as_view({'get': 'list'})
        request_list = factory.get('/conversations/')
        force_authenticate(request_list, user=user)
        response_list = view_list(request_list)
        
        data = response_list.data
        # Depending on pagination, data might be list or dict with results
        results = data['results'] if isinstance(data, dict) and 'results' in data else data
        
        found = any(c['id'] == conversation.id for c in results)
        self.stdout.write(f"Is conversation in list? {found}")
        
        if is_hidden and not found:
            self.stdout.write(self.style.SUCCESS("SUCCESS: Conversation is hidden and not in list"))
        else:
            self.stdout.write(self.style.ERROR("FAILURE: Persistence issue detected"))

        # Cleanup
        user.delete()
        agent.delete()
